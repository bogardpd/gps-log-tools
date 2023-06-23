"""Updates GeoPackage and imports GPX if provided."""

import argparse
import geopandas as gpd
import os
import shutil
import sys
import traceback
import tomli

from dateutil.parser import parse
from pathlib import Path
from shapely import multilinestrings

from GPXFile import GPXFile

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

NSMAP = {None: "http://www.opengis.net/kml/2.2"}


class DrivingLog:
    """Manages a collection of driving tracks."""
    def __init__(self) -> None:
        root = Path(CONFIG['folders']['auto_root']).expanduser()
        script_root = Path(__file__).parent
        self.CANONICAL_GPKG_FILE = root / CONFIG['files']['canonical_gpkg']
        self.CANONICAL_BACKUP_FILE = (
            root / CONFIG['files']['canonical_backup_gpkg']
        )
        self.GPKG_TEMPLATE = (
            script_root / CONFIG['files']['script']['gpkg_template']
        )

        self.verify_logfile()
    
    def append_tracks_to_gpkg(self, driving_tracks_list):
        """Appends a list of DrivingTracks to the GeoPackage logfile."""
        records = []
        for dt in driving_tracks_list:
            if dt.geometry is None:
                print(f"Track {dt} has no geometry (likely < 2 points).")
                continue
            records.append(dt.get_record())

        if len(records) > 0:
            gdf = gpd.GeoDataFrame(
                records,
                geometry="geometry",
                crs="EPSG:4326"
            )
            gdf.to_file(
                self.CANONICAL_GPKG_FILE,
                driver="GPKG",
                layer="driving_tracks",
                mode='a',
            )
        print(
            f"Appended {len(records)} track(s) to {self.CANONICAL_GPKG_FILE}."
        )

    def backup(self):
        """Backs up the canonical logfile."""
        shutil.copy(self.CANONICAL_GPKG_FILE, self.CANONICAL_BACKUP_FILE)
        print(
            f"Backed up canonical GPKG to {self.CANONICAL_BACKUP_FILE}."
        )

    def import_gpx_files(self, gpx_files):
        """Imports GPX files into the GeoPackage driving log."""
        if len(gpx_files) == 0:
            print("No GPX file was provided.")
            return
       
        # Use dict to ensure unique timestamps, to avoid duplicate
        # tracks among the input files.
        gpx_tracks = {} 
        for f in gpx_files:
            gpx_file = GPXFile.load(f)
            gpx_file.process()
            file_tracks = gpx_file.driving_tracks
            for ft in file_tracks:
                # Use utc_start as track identifier, since processed
                # tracks may have already been split from the same
                # DrivingTrack timestamp.
                gpx_tracks[ft.utc_start] = ft
        driving_tracks_list = list(gpx_tracks.values())

        # Add new tracks to GeoPackage.
        self.append_tracks_to_gpkg(driving_tracks_list)
    
    def verify_logfile(self):
        """Checks for logfile and copies from template if needed."""
        if os.path.exists(self.CANONICAL_GPKG_FILE):
            print(f"Logfile is present at {self.CANONICAL_GPKG_FILE}.")
        else:
            shutil.copy(self.GPKG_TEMPLATE, self.CANONICAL_GPKG_FILE)
            print(f"Copied logfile {self.CANONICAL_GPKG_FILE} from template.")


def import_gpx(gpx_files = []):
    log = DrivingLog()
    log.backup()
    log.import_gpx_files(gpx_files)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Import GPX files to Driving Log"
    )
    parser.add_argument(
        dest='gpx_files',
        nargs='+',
        help=("GPX file(s) to import.")
    )
    parser.add_argument('--nopause', dest='nopause', action='store_true')
    args = parser.parse_args()
    try:
        import_gpx(args.gpx_files)
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        if not args.nopause:
            input("Press Enter to continue... ")