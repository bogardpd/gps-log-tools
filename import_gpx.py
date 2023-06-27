"""Imports GPX files into a GeoPackage."""

import argparse
import geopandas as gpd
import pandas as pd
import sqlite3
import os
import shutil
import sys
import traceback
import tomli

from dateutil.parser import parse
from pathlib import Path

from GPXFile import GPXFile

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)


class DrivingLog:
    """Manages a collection of driving tracks."""
    def __init__(self) -> None:
        root = Path(CONFIG['folders']['auto_root']).expanduser()
        script_root = Path(__file__).parent
        self.CANONICAL_GPKG_FILE = root / CONFIG['files']['canonical_gpkg']
        self.CANONICAL_BACKUP_FILE = (
            root / CONFIG['files']['canonical_backup']
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

    def existing_trk_timestamps(self):
        """Gets a set of existing source track timestamps."""
        gpkg_file = (
            Path(CONFIG['folders']['auto_root']).expanduser()
            / CONFIG['files']['canonical_gpkg']
        )
        con = sqlite3.connect(gpkg_file)
        query = """
            SELECT DISTINCT source_track_timestamp
            FROM driving_tracks
        """
        df = pd.read_sql(query, con)
        con.close()
        return set(parse(d) for d in df['source_track_timestamp'].to_list())

    def import_gpx_files(self, gpx_files):
        """Imports GPX files into the GeoPackage driving log."""
        if len(gpx_files) == 0:
            print("No GPX file was provided.")
            return
        
        # Get a set of existing source track timestamps. These will be
        # used to ensure tracks which are already imported will not be
        # imported again.
        existing_ts = self.existing_trk_timestamps()

        new_gpx_tracks = [] 
        for f in gpx_files:
            # Process GPX file and append processed tracks to list.
            # Tracks with timestamps matching those in existing_ts will
            # not be processed or appended to the list.
            gpx_file = GPXFile.load(f)
            gpx_file.process(existing_timestamps=existing_ts)
            file_tracks = gpx_file.driving_tracks
            new_gpx_tracks.extend(file_tracks)

            # Get the timestamps from the new tracks, and include them
            # in the set of existing track timestamps. This allows us to
            # excluded these tracks if they show up in file in a future
            # loop iteration.
            added_ts = set(t.timestamp for t in file_tracks)
            existing_ts.update(added_ts)

        # Add new tracks to GeoPackage.
        self.append_tracks_to_gpkg(new_gpx_tracks)
    
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
