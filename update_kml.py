"""Updates canonical KML file and imports GPX if provided."""

import argparse
import gpxpy
import io
import os
import shutil
import sys
import traceback
import yaml
from datetime import timedelta, timezone
from dateutil.parser import parse, isoparse
from lxml import etree
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from pykml.helpers import set_max_decimal_places
from simplify_gpx import rdp_spherical
from trim_gpx import trim_start
from zipfile import ZipFile, ZIP_DEFLATED

# This script will generate both a KML file (to act as the canonical
# storage for driving data in a human readible format) and a KMZ file
# with additional processing (e.g. merging tracks in folders). The KML
# file will be read when merging new data.

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
CANONICAL_KML_FILE = AUTO_ROOT / CONFIG['files']['canonical_kml']
CANONICAL_BACKUP_FILE = AUTO_ROOT / CONFIG['files']['canonical_backup']
OUTPUT_KMZ_FILE = AUTO_ROOT / CONFIG['files']['output_kmz']

NSMAP = {None: "http://www.opengis.net/kml/2.2"}

def update_kml(gpx_files = []):
    shutil.copy(CANONICAL_KML_FILE, CANONICAL_BACKUP_FILE)
    print(f"Backed up canonical data to {CANONICAL_BACKUP_FILE}.")

    kml_dict = kml_to_dict(CANONICAL_KML_FILE)

    if len(gpx_files) > 0:
        # GPX files were provided; parse and merge them.
        gpx_dicts = [gpx_to_dict(gpx_file) for gpx_file in gpx_files]
        gpx_flattened = {}
        for gd in gpx_dicts:
            gpx_flattened.update(gd)
        tracks_dict = merge_tracks(kml_dict, gpx_flattened)
    else:
        # No GPX file was provided; just refresh canonical KML.
        print("No GPX file was provided. Refreshing canonical KML…")
        tracks_dict = kml_dict
    
    export_kml(tracks_dict, CANONICAL_KML_FILE, False, False)
    export_kml(tracks_dict, OUTPUT_KMZ_FILE, True, True)


def export_kml(kml_dict, output_file, zipped=False, merge_folder_tracks=False):
    """
    Exports KML data to a KML (if zipped=False) or KMZ file located at
    output_file. Will merge LineStrings within a Folder into a single
    root-level LineString if merge_folder_tracks is set.
    """

    def dict_to_placemark(timestamp, values):
        """Converts a timestamp and coordinates to a Placemark."""
        pm_desc = (
            KML.description(values['description']) if values['description']
            else None
        )
        coord_str = " ".join(
            ",".join(
                str(t) for t in coord[0:2] # Remove altitude if present
            ) for coord in values['coords']
        )
        pm_name = timestamp.strftime(CONFIG['timestamps']['kml_name'])
        if values.get('new'):
            pm_name += " (new)"
        pm = KML.Placemark(
            KML.name(pm_name),
            pm_desc,
            KML.TimeStamp(
                KML.when(timestamp.isoformat())
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
    print(f"Creating {filetype} file…")

    style = KML.Style(
        KML.LineStyle(
            KML.color("ff0000ff" if zipped else "ffff00ff"),
            KML.colorMode("normal"),
            KML.width(4),
        ),
        id='1',
    )

    # Create Folders and Placemarks.
    log_data = []
    for timestamp, values in sorted(kml_dict.items()):
        if values.get('coords') is not None:
            # This is a track; create a LineString.
            log_data.append(dict_to_placemark(timestamp, values))
        else:
            # This is a folder.            
            if merge_folder_tracks:
                # Merge all folder tracks into a single LineString.
                coords = [
                    track_coords
                    for ft, fv in sorted(values.items())
                    for track_coords in fv['coords']
                ]
                track_values = {'coords': coords, 'description': None}
                log_data.append(dict_to_placemark(timestamp, track_values))
            else:
                # Create a folder of LineStrings.
                folder_linestrings = [
                    dict_to_placemark(ftimestamp, fvalues)
                    for ftimestamp, fvalues in sorted(values.items())
                ]
                folder = KML.Folder(
                    KML.name(timestamp.strftime(
                        CONFIG['timestamps']['kml_name']
                    )),
                    *folder_linestrings
                )
                log_data.append(folder)

    kml_doc = KML.kml(
        KML.Document(
            KML.name("Driving" if zipped else "driving_canonical"),
            style,
            *log_data,
        ),
    )

    set_max_decimal_places(
        kml_doc,
        max_decimals={
            'longitude': 6,
            'latitude': 6,
        }
    )

    if zipped:
        archive = ZipFile(output_file, 'w', compression=ZIP_DEFLATED)
        output = io.BytesIO()
        etree.ElementTree(kml_doc).write(
            output,
            pretty_print=True,
            xml_declaration=True,
            encoding='utf-8',
        )
        archive.writestr("doc.kml", output.getvalue())
    else:
        etree.ElementTree(kml_doc).write(
            str(output_file),
            pretty_print=True,
            xml_declaration=True,
            encoding='utf-8',
        )
    print(f"Saved {filetype} to {output_file}!")


def gpx_to_dict(gpx_file):
    """
    Reads the supplied GPX file and returns a dictionary with datetime
    keys and descriptions/coordinates (lists of (lon,lat,ele) tuples) as
    values. Any tracks or track segments in IGNORE_FILE will not be
    included in the dictionary.
    """
    print(f"Reading GPX from `{gpx_file}`…")
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    # Get creator:
    if "Bad Elf" in gpx.creator:
        gpx_config = CONFIG['import']['gpx']['bad_elf']
    elif "DriveSmart" in gpx.creator:
        gpx_config = CONFIG['import']['gpx']['garmin']
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
        print("Merging segments…")
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
        print(f"Converting track `{track.name}`…")
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
                print(f"Trimming segment {sn+1}/{len(track.segments)}…")
                original_point_count = len(segment.points)
                segment.points = trim_start(segment.points)
                diff = original_point_count - len(segment.points)
                print(f"\tRemoved {diff} excess points at start of segment.")

            # Simplify track segment.
            if gpx_config['simplify']['enabled']:
                print(f"Simplifying segment {sn+1}/{len(track.segments)}…")
                epsilon = gpx_config['simplify']['epsilon']
                print(f"\tOriginal: {len(segment.points)} points")
                segment.points = rdp_spherical(segment.points, epsilon)
                print(f"\tSimplilfied: {len(segment.points)} points")

            coords = list(
                (p.longitude, p.latitude) for p in segment.points
            )
           
            if len(coords) >= CONFIG['import']['min_points']:
                track_dict[timestamp] = dict(
                    coords=coords,
                    description=desc,
                    new=True,
                )

    return track_dict


def kml_to_dict(kml_file):
    """
    Reads the supplied KML file and returns a dictionary with datetime
    keys and descriptions/coordinates (lists of (lon,lat,ele) tuples) as
    values. Can contain one level of subfolders as subdictionaries.
    """
    print(f"Reading KML from {kml_file}…")

    def placemarks_to_dict(node):
        """Parses all Placemark children of the node into a dict."""
        output_dict = {}
        for p in node.findall('Placemark', NSMAP):
            timestamp = parse(p.find('TimeStamp/when', NSMAP).text)
            timestamp = timestamp.astimezone(timezone.utc)
            raw_coords = p.find('LineString/coordinates', NSMAP).text.strip()
            coords = list(
                tuple(
                    float(n) for n in c.split(",")[0:2] # Remove altitude
                ) for c in raw_coords.split(" ")
            )
            desc = p.find("description", NSMAP)
            if desc is not None:
                desc = desc.text.strip()
            if len(coords) >= CONFIG['import']['min_points']:
                output_dict[timestamp] = dict(
                    coords=coords,
                    description=desc,
                )
        return output_dict

    # The simplekml package does not parse KML files (it only creates
    # them), so use lxml etree to parse the raw XML instead.
    root = etree.parse(str(kml_file)).getroot()
    document = root.find('Document', NSMAP)

    # Parse Document-level Placemarks.
    track_dict = placemarks_to_dict(document)
    
    # Parse Placemarks in Folders.
    folders = document.findall('Folder', NSMAP)
    for folder in folders:
        folder_tracks = placemarks_to_dict(folder)
        if len(folder_tracks) > 0:
            track_dict[min(folder_tracks.keys())] = folder_tracks

    return track_dict
    

def merge_tracks(existing_tracks, new_tracks):
    """
    Merges a new track dict into an existing track dict. Tracks which
    are already in existing tracks will not be overwritten by new
    tracks.
    """
    print("Merging new tracks into existing tracks…")

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
    args = parser.parse_args()
    try:
        update_kml(args.gpx_files)
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        os.system("pause")