"""Updates canonical KML file and imports GPX if provided."""

import argparse
import gpxpy
import io
import os
import pprint
import shutil
import sys
import traceback
import yaml
from datetime import date, time, datetime, timedelta, timezone
from dateutil.parser import parse, isoparse
from lxml import etree
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from pykml.helpers import set_max_decimal_places
from simplify_gpx import rdp_spherical
from trim_gpx import trim_start
from zipfile import ZipFile, ZIP_DEFLATED

# This script will generate both a KML file (to act as the canonical
# storage for driving data in a human readable format) and a KMZ file
# with additional processing (e.g. merging tracks in folders). The KML
# file will be read when merging new data.

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
CANONICAL_KML_FILE = AUTO_ROOT / CONFIG['files']['canonical_kml']
CANONICAL_BACKUP_FILE = AUTO_ROOT / CONFIG['files']['canonical_backup']
OUTPUT_KMZ_FILE = AUTO_ROOT / CONFIG['files']['output_kmz']

NSMAP = {None: "http://www.opengis.net/kml/2.2"}


class DrivingLog:
    """Manages a collection of driving tracks."""
    def __init__(self) -> None:
        self.tracks = []
        self.CANONICAL_BACKUP_FILE = CANONICAL_BACKUP_FILE
        self.CANONICAL_KML_FILE = CANONICAL_KML_FILE
        self.OUTPUT_KMZ_FILE = OUTPUT_KMZ_FILE

    def backup(self):
        """Backs up the canonical logfile."""
        shutil.copy(self.CANONICAL_KML_FILE, self.CANONICAL_BACKUP_FILE)
        print(f"Backed up canonical data to \"{CANONICAL_BACKUP_FILE}\".")

    def export_kml(self, output_file, zipped=False, merge_folder_tracks=False):
        """
        Exports KML data to a KML (if zipped=False) or KMZ file located
        at output_file. Will merge LineStrings within a Folder into a
        single root-level LineString if merge_folder_tracks is set.
        """

        def dict_to_placemark(track):
            """Converts a timestamp and coordinates to a Placemark."""
            pm_desc = (
                KML.description(track.description) if track.description
                else None
            )
            coord_str = " ".join(
                ",".join(
                    str(t) for t in coord[0:2] # Remove altitude if present
                ) for coord in track.coords
            )
            pm_name = track.timestamp.strftime(CONFIG['timestamps']['kml_name'])
            if track.creator:
                pm_extdata = KML.ExtendedData(
                    KML.Data(
                        KML.displayName("Creator"),
                        KML.value(track.creator),
                        name='creator',
                    )
                )
            else:
                pm_extdata = None
            if track.is_new:
                pm_name += " (new)"
            pm = KML.Placemark(
                KML.name(pm_name),
                pm_desc,
                pm_extdata,
                KML.TimeStamp(
                    KML.when(track.timestamp.isoformat())
                ),
                KML.styleUrl("#1"),
                KML.altitudeMode("clampToGround"),
                KML.tessellate(1),
                KML.LineString(
                    KML.coordinates(coord_str),
                ),
            )
            return pm

        filetype = "KMZ" if zipped else "KML"
        print(f"Creating {filetype} file...")

        style = KML.Style(
            KML.LineStyle(
                KML.color("ff0000ff" if zipped else "ffff00ff"),
                KML.colorMode("normal"),
                KML.width(4),
            ),
            id='1',
        )

        time_range = self.get_time_range()
        timespan = KML.TimeSpan(
            KML.begin(time_range[0].isoformat()),
            KML.end(time_range[1].isoformat()),
        )

        # Create Folders and Placemarks.
        log_data = []
        for log_element in self.tracks:
            if isinstance(log_element, list):
                # This is a folder.
                folder_tracks = log_element     
                if merge_folder_tracks:
                    # Merge all folder tracks into a single LineString.
                    track = DrivingTrack(folder_tracks[0].timestamp)
                    track.coords = [
                        track_coords
                        for f in folder_tracks
                        for track_coords in f.coords
                    ]
                    track.creator = folder_tracks[0].creator
                    track.description = folder_tracks[0].description
                    log_data.append(dict_to_placemark(track))
                else:
                    # Create a folder of LineStrings.
                    folder_linestrings = [
                        dict_to_placemark(track)
                        for track in folder_tracks
                    ]
                    folder = KML.Folder(
                        KML.name(folder_tracks[0].timestamp.strftime(
                            CONFIG['timestamps']['kml_name']
                        )),
                        *folder_linestrings
                    )
                    log_data.append(folder)
            else:
                # This is a track; create a LineString.
                log_data.append(dict_to_placemark(log_element))

        kml_doc = KML.kml(
            KML.Document(
                KML.name("Driving" if zipped else "driving_canonical"),
                timespan,
                style,
                *log_data,
            ),
        )

        set_max_decimal_places(
            kml_doc,
            max_decimals={'longitude': 6, 'latitude': 6}
        )

        output_params = {
            'pretty_print': True,
            'xml_declaration': True,
            'encoding': "utf-8",
        }
        if zipped:
            archive = ZipFile(output_file, 'w', compression=ZIP_DEFLATED)
            output = io.BytesIO() 
            etree.ElementTree(kml_doc).write(output, **output_params)
            archive.writestr("doc.kml", output.getvalue())
        else:
            etree.ElementTree(kml_doc).write(str(output_file), **output_params)
        print(f"Saved {filetype} to \"{output_file}\"!")

    def get_time_range(self):
        """Returns a (start, end) tuple covering all tracks."""
        # Get all timestamps.
        timestamps = []
        for track in self.tracks:
            if isinstance(track, list):
                for subtrack in track:
                    timestamps.append(subtrack.timestamp)
            else:
                timestamps.append(track.timestamp)
        
        # Set document timespan to the midnight prior to earliest
        # timestamp and the midnight following the latest timestamp, so
        # the Google Earth time slider doesn't exclude the first or last
        # track in some situations.
        min_time = datetime.combine(
            min(timestamps), time(0,0,0), tzinfo=timezone.utc
        )
        max_time = datetime.combine(
            max(timestamps), time(0,0,0), tzinfo=timezone.utc
        ) + timedelta(days=1)
        return (min_time, max_time)
    
    def load_canonical(self):
        """Parses the canonical KML file."""
        print(f"Reading KML from \"{CANONICAL_KML_FILE}\"...")

        def placemarks_to_tracks(node):
            """
            Parses all Placemark children of the node into a list of
            DrivingTracks.
            """
            output_tracks = []
            for p in node.findall('Placemark', NSMAP):
                timestamp = parse(p.find('TimeStamp/when', NSMAP).text)
                timestamp = timestamp.astimezone(timezone.utc)
                track = DrivingTrack(timestamp)
                creator = p.find("ExtendedData/Data[@name='creator']", NSMAP)
                if creator is not None:
                    track.creator = creator.find("value", NSMAP).text.strip()
                coords = p.find('LineString/coordinates', NSMAP).text.strip()
                track.coords = list(
                    tuple(
                        float(n) for n in c.split(",")[0:2] # Remove altitude
                    ) for c in coords.split(" ")
                )
                desc = p.find("description", NSMAP)
                if desc is not None:
                    desc = desc.text.strip()
                    track.description = desc
                if len(track.coords) >= CONFIG['import']['min_points']:
                    output_tracks.append(track)
            return output_tracks

        root = etree.parse(str(CANONICAL_KML_FILE)).getroot()
        document = root.find('Document', NSMAP)

        # Parse Document-level Placemarks.
        track_list = placemarks_to_tracks(document)
        
        # Parse Placemarks in Folders.
        folders = document.findall('Folder', NSMAP)
        for folder in folders:
            folder_tracks = placemarks_to_tracks(folder)
            if len(folder_tracks) > 0:
                track_list.append(folder_tracks)

        self.tracks.extend(track_list)

    def sort_tracks(self):
        """Sorts tracks by date (including subfolders)."""
        
        # Sort individual subfolders.
        for i,t in enumerate(self.tracks):
            if isinstance(t, list):
                self.tracks[i] = sorted(t, key=lambda x:x.timestamp)

        # Sort root track list.
        self.tracks = sorted(
            self.tracks,
            key=lambda x:DrivingLog.__get_key(x)
        )

    @classmethod
    def __get_key(cls, log_element):
        if isinstance(log_element, list):
            timestamps = [le.timestamp for le in log_element]
            return min(timestamps)
        else:
            return log_element.timestamp


class DrivingTrack:
    """An instance of a driving log track."""
    def __init__(self, id_timestamp) -> None:
        self.timestamp = id_timestamp # Starting timestamp is used as id
        self.coords = []
        self.creator = None
        self.description = None
        self.is_new = False

    def __repr__(self) -> str:
        return f"DrivingTrack({self.timestamp.isoformat()})"


def update_kml(gpx_files = []):
    log = DrivingLog()
    log.backup()
    log.load_canonical()

    if len(gpx_files) > 0:
        # GPX files were provided; parse and merge them.
        gpx_dicts = [gpx_to_dict(gpx_file) for gpx_file in gpx_files]
        gpx_flattened = {}
        for gd in gpx_dicts:
            gpx_flattened.update(gd)
        tracks_dict = merge_tracks(log.tracks, gpx_flattened)
    else:
        # No GPX file was provided; just refresh canonical KML.
        print("No GPX file was provided. Refreshing canonical KML...")
        # tracks_dict = log.tracks
    
    log.sort_tracks()
    log.export_kml(
        log.CANONICAL_KML_FILE, zipped=False, merge_folder_tracks=False
    )
    log.export_kml(
        log.OUTPUT_KMZ_FILE, zipped=True, merge_folder_tracks=True
    )


def gpx_to_dict(gpx_file):
    """
    Reads the supplied GPX file and returns a dictionary with datetime
    keys and descriptions/coordinates (lists of (lon,lat,ele) tuples) as
    values. Any tracks or track segments in IGNORE_FILE will not be
    included in the dictionary.
    """
    print(f"Reading GPX from \"{gpx_file}\"...")
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    # Get creator:
    if "Bad Elf" in gpx.creator:
        gpx_config = CONFIG['import']['gpx']['bad_elf']
    elif "DriveSmart" in gpx.creator:
        gpx_config = CONFIG['import']['gpx']['garmin']
    elif "myTracks" in gpx.creator:
        gpx_config = CONFIG['import']['gpx']['mytracks']
    else:
        gpx_config = CONFIG['import']['gpx']['_default']

    ignore_trkseg = [
        isoparse(dt) for dt in CONFIG['import']['ignore']['trkseg']
    ]

    def filter_segments(segments):
        """Removes segments whose first point matches ignore list."""
        try:
            return [
                seg for seg in segments
                if seg.points[0].time not in ignore_trkseg
            ]
        except AttributeError:
            return segments

    def merge_segments(segments, index=0):
        """ Merges segments with small time gaps. """
        print("Merging segments...")
        segments = segments.copy()
        if index + 1 == len(segments):
            return segments
        a,b = segments[index:index+2]
        try:
            timediff = b.points[0].time - a.points[-1].time
            max_seconds = gpx_config['merge_segments']['max_seconds']
            if timediff <= timedelta(seconds=max_seconds):
                a.points.extend(b.points)
                del segments[index+1]
                return merge_segments(segments, index=index)
            else:
                return merge_segments(segments, index=index+1)
        except AttributeError:
            return segments

    track_dict = {}
    for track in gpx.tracks:
        print(f"Converting track \"{track.name}\"...")
        desc = track.description
        track.segments = filter_segments(track.segments)
        if gpx_config['merge_segments']['enabled']:
            track.segments = merge_segments(track.segments)
        
        for sn, segment in enumerate(track.segments):
            # Get timestamp before any trimming or simplification.
            try:
                timestamp = segment.points[0].time.astimezone(timezone.utc)
            except AttributeError:
                timestamp = parse(track.name).astimezone(timezone.utc)
            
            # Trim excess points from beginning of track segment.
            if gpx_config['trim']['enabled']:
                print(f"Trimming segment {sn+1}/{len(track.segments)}...")
                original_point_count = len(segment.points)
                segment.points = trim_start(segment.points)
                diff = original_point_count - len(segment.points)
                print(f"\tRemoved {diff} excess points at start of segment.")

            # Simplify track segment.
            if gpx_config['simplify']['enabled']:
                print(f"Simplifying segment {sn+1}/{len(track.segments)}...")
                epsilon = gpx_config['simplify']['epsilon']
                print(f"\tOriginal: {len(segment.points)} points")
                segment.points = rdp_spherical(segment.points, epsilon)
                print(f"\tSimplified: {len(segment.points)} points")

            coords = list(
                (p.longitude, p.latitude) for p in segment.points
            )
           
            if len(coords) >= CONFIG['import']['min_points']:
                track_dict[timestamp] = dict(
                    coords=coords,
                    description=desc,
                    creator=gpx.creator,
                    new=True,
                )

    return track_dict


def merge_tracks(existing_tracks, new_tracks):
    """
    Merges a new track dict into an existing track dict. Tracks which
    are already in existing tracks will not be overwritten by new
    tracks.
    """
    print("Merging new tracks into existing tracks...")

    def flatten_keys(tracks):
        keys = set()
        for k, v in tracks.items():
            if v.get('coords') is not None:
                keys.add(k)
            else:
                for subk in v.keys():
                    keys.add(subk)
        return keys

    existing_keys = flatten_keys(existing_tracks)
    new_keys = set(new_tracks.keys())
    keys_to_merge = new_keys - existing_keys
    tracks_to_merge = {
        k:v
        for k, v in new_tracks.items()
        if k in keys_to_merge
    }

    # Merge existing tracks with gpx tracks. Existing tracks should
    # override new tracks with same timestamp.
    merged = {**tracks_to_merge, **existing_tracks}

    # Filter out tracks with times matching ignore list.
    ignore_trk = [isoparse(dt) for dt in CONFIG['import']['ignore']['trk']]
    merged = {k:v for k,v in merged.items() if k not in ignore_trk}
 
    print(f"{len(new_keys)} imported tracks")
    print(f"{len(existing_keys)} existing tracks")
    print(f"{len(flatten_keys(merged))} merged tracks")

    return merged


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Update KML and import GPX")
    parser.add_argument(
        dest='gpx_files',
        nargs='*',
        help=(
            "GPX file(s) to import. If none are provided, the canonical KML "
            "file is refreshed without importing anything."
        )
    )
    parser.add_argument('--nopause', dest='nopause', action='store_true')
    args = parser.parse_args()
    try:
        update_kml(args.gpx_files)
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        if not args.nopause:
            input("Press Enter to continue... ")