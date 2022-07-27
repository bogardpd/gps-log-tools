"""Imports GPX files from an input folder."""
import gpxpy
import os
import sys
import traceback
import yaml
from datetime import timezone
from pathlib import Path
from zipfile import ZipFile
from update_kml import update_kml

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)

AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
IMPORT_ROOT = Path(CONFIG['folders']['import_root']).expanduser()
TIME_FORMAT = CONFIG['timestamps']['raw']['mytracks']

def main():
    print(f"Importing myTracks GPX files from {IMPORT_ROOT}.")
    # Unzip and delete zip files.
    
    print("Extracting and deleting zip files...")
    zip_files = list(IMPORT_ROOT.glob("myTracks*.zip"))
    for z in zip_files:
        with ZipFile(z, 'r') as zf:
            zf.extractall(IMPORT_ROOT)
        z.unlink() # Delete zipfile
     
    # Select GPX files.
    gpx_files = list(IMPORT_ROOT.glob("*.gpx"))
    
    # Import GPX files.
    print("Updating KML with imported files...")
    update_kml(gpx_files)

    # Move GPX files to raw and rename if needed.
    destination = (AUTO_ROOT / CONFIG['folders']['raw']['mytracks'])
    print(f"Moving GPX files to {destination}...")
    for gpx_file in gpx_files:
        # Get the timestamp for the earliest waypoint in the GPX file.
        with open(gpx_file, 'r') as gf:
            gpx = gpxpy.parse(gf)
        first_point_time = min([
            segment.points[0].time.astimezone(timezone.utc)
            for track in gpx.tracks
            for segment in track.segments
        ]).strftime(TIME_FORMAT)

        new_filename = (first_point_time + gpx_file.suffix)
        new_filepath = destination / new_filename
        gpx_file.rename(new_filepath)

    print("myTracks GPX Import done!")

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        input("Press Enter to continue... ")