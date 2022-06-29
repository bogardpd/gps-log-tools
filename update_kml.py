"""Updates canonical KML file and imports GPX if provided."""

import argparse
import gpxpy
import io
import shutil
import sys
import traceback
import yaml

from datetime import time, datetime, timedelta, timezone
from dateutil.parser import parse, isoparse
from lxml import etree
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from pykml.helpers import set_max_decimal_places
from zipfile import ZipFile, ZIP_DEFLATED

from gpx_utilities import gpx_profile
from simplify_gpx import rdp_spherical
from trim_gpx import trim_start

# This script will generate both a KML file (to act as the canonical
# storage for driving data in a human readable format) and a KMZ file
# with additional processing (e.g. merging tracks in folders). The KML
# file will be read when merging new data.

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

NSMAP = {None: "http://www.opengis.net/kml/2.2"}


class DrivingLog:
    """Manages a collection of driving tracks."""
    def __init__(self) -> None:
        self.tracks = []

        root = Path(CONFIG['folders']['auto_root']).expanduser()
        self.CANONICAL_KML_FILE = root / CONFIG['files']['canonical_kml']
        self.CANONICAL_BACKUP_FILE = root / CONFIG['files']['canonical_backup']
        self.OUTPUT_KMZ_FILE = root / CONFIG['files']['output_kmz']

        self.ignore = {
            t: [isoparse(dt) for dt in CONFIG['import']['ignore'][t]]
            for t in ['trk', 'trkseg']
        }

    def backup(self):
        """Backs up the canonical logfile."""
        shutil.copy(self.CANONICAL_KML_FILE, self.CANONICAL_BACKUP_FILE)
        print(f"Backed up canonical data to \"{self.CANONICAL_BACKUP_FILE}\".")

    def export_kml(self, output_file, zipped=False, merge_folder_tracks=False):
        """
        Exports KML data to a KML (if zipped=False) or KMZ file located
        at output_file. Will merge LineStrings within a Folder into a
        single root-level LineString if merge_folder_tracks is set.
        """

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

        time_range = self.time_range()
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
                    log_data.append(track.get_kml_placemark())
                else:
                    # Create a folder of LineStrings.
                    folder_linestrings = [
                        track.get_kml_placemark()
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
                log_data.append(log_element.get_kml_placemark())

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

    def import_gpx_files(self, gpx_files):
        """Imports GPX files and merges them into tracks."""
        if len(gpx_files) == 0:
            # No GPX file was provided; just refresh canonical KML.
            print("No GPX file was provided. Refreshing canonical KML...")
            return
       
        # GPX files were provided; parse and merge them.
        gpx_tracks = {} # Use dict to ensure unique timestamps.
        for f in gpx_files:
            file_tracks = self.__convert_gpx_to_tracks(
                f, self.ignore['trkseg']
            )
            for ft in file_tracks:
                if ft.timestamp not in self.ignore['trk']:
                    gpx_tracks[ft.timestamp] = ft
                else:
                    print(f"Skipping ignored track {ft}.")
        gpx_tracks = list(gpx_tracks.values())

        # Merge GPX tracks into DrivingLog tracks, keeping original
        # DrivingLog track if two tracks have the same timestamp.
        self.__merge_tracks(gpx_tracks)
        
    def load_canonical(self):
        """Parses the canonical KML file."""
        print(f"Reading KML from \"{self.CANONICAL_KML_FILE}\"...")

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

        root = etree.parse(str(self.CANONICAL_KML_FILE)).getroot()
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
            key=lambda x:DrivingLog.__log_element_key(x)
        )

    def time_range(self):
        """Returns a (start, end) tuple covering all tracks."""
        
        timestamps = self.timestamps()
        
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

    def timestamps(self):
        """Returns a list of all track timestamps."""
        timestamps = []
        for track in self.tracks:
            if isinstance(track, list):
                for subtrack in track:
                    timestamps.append(subtrack.timestamp)
            else:
                timestamps.append(track.timestamp)
        return timestamps

    def __merge_tracks(self, new_tracks):
        """
        Merge new tracks into existing tracks, keeping original track if
        two tracks have the same timestamp.
        """

        # Get list of existing driving log track timestamps.
        log_timestamps = self.timestamps()

        # Filter out new tracks that conflict with existing tracks.
        tracks_to_merge = [
            x for x in new_tracks if x.timestamp not in log_timestamps
        ]

        self.tracks.extend(tracks_to_merge)

    @staticmethod
    def __convert_gpx_to_tracks(gpx_file, ignore_trkseg=[]):
        """Converts a GPX file to a list of Tracks."""
        print(f"Reading GPX from \"{gpx_file}\"...")
        with open(gpx_file, 'r') as f:
            gpx = gpxpy.parse(f)

        gpx_config = DrivingLog.__processing_config(gpx.creator)

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
        
        tracks = []
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
                    print(
                        f"\tRemoved {diff} excess points at start of segment."
                    )

                # Simplify track segment.
                if gpx_config['simplify']['enabled']:
                    print(
                        f"Simplifying segment {sn+1}/{len(track.segments)}..."
                    )
                    epsilon = gpx_config['simplify']['epsilon']
                    print(f"\tOriginal: {len(segment.points)} points")
                    segment.points = rdp_spherical(segment.points, epsilon)
                    print(f"\tSimplified: {len(segment.points)} points")

                coords = list(
                    (p.longitude, p.latitude) for p in segment.points
                )
            
                if len(coords) >= CONFIG['import']['min_points']:
                    track = DrivingTrack(timestamp)
                    track.coords = coords
                    track.description = desc
                    track.creator = gpx.creator
                    track.is_new = True
                    tracks.append(track)

        return tracks

    @staticmethod
    def __log_element_key(log_element):
        """
        Returns the timestamp of a DrivingTrack, or the timestamp of the
        first track in a list of DrivingTracks.
        """
        if isinstance(log_element, list):
            timestamps = [le.timestamp for le in log_element]
            return min(timestamps)
        else:
            return log_element.timestamp

    @staticmethod
    def __processing_config(creator):
        """Parses a creator to determine a processing configuration."""
        profile = gpx_profile(creator)
        return CONFIG['import']['gpx'][profile]

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

    def get_kml_placemark(self):
        """Returns a KML Placemark for the track."""
        pm_desc = (
            KML.description(self.description) if self.description
            else None
        )
        coord_str = " ".join(
            ",".join(
                str(t) for t in coord[0:2] # Remove altitude if present
            ) for coord in self.coords
        )
        pm_name = self.timestamp.strftime(CONFIG['timestamps']['kml_name'])
        if self.creator:
            pm_extdata = KML.ExtendedData(
                KML.Data(
                    KML.displayName("Creator"),
                    KML.value(self.creator),
                    name='creator',
                )
            )
        else:
            pm_extdata = None
        if self.is_new:
            pm_name += " (new)"
        pm = KML.Placemark(
            KML.name(pm_name),
            pm_desc,
            pm_extdata,
            KML.TimeStamp(
                KML.when(self.timestamp.isoformat())
            ),
            KML.styleUrl("#1"),
            KML.altitudeMode("clampToGround"),
            KML.tessellate(1),
            KML.LineString(
                KML.coordinates(coord_str),
            ),
        )
        return pm


def update_kml(gpx_files = [], skip_export=False):
    log = DrivingLog()
    log.load_canonical()
    log.import_gpx_files(gpx_files)
    log.sort_tracks()
    
    if skip_export:
        print("Skipping export.")
    else:
        log.backup()
        log.export_kml(
            log.CANONICAL_KML_FILE, zipped=False, merge_folder_tracks=False
        )
        log.export_kml(
            log.OUTPUT_KMZ_FILE, zipped=True, merge_folder_tracks=True
        )


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
    parser.add_argument('--noexport', dest='noexport', action='store_true')
    args = parser.parse_args()
    try:
        update_kml(args.gpx_files, skip_export=args.noexport)
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        if not args.nopause:
            input("Press Enter to continue... ")