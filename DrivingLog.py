"""Class for interacting with a driving log."""

import os
import shutil
import pandas as pd
import geopandas as gpd
import sqlite3
import tomli
from datetime import datetime, timezone
from dateutil.parser import parse
from pathlib import Path
from GPXFile import GPXFile

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
DRIVING_LOG_PATH = (
    Path(CONFIG['folders']['auto_root']).expanduser()
    / CONFIG['files']['canonical_gpkg']
)

class DrivingLog:
    """Wrapper for interacting with a driving log geopackage."""
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
        self.ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
        self.ISO_FORMAT_LIKE = "____-__-__T__:__:__Z"

        sqlite3.register_adapter(
            datetime,
            lambda dt: dt.strftime(self.ISO_FORMAT),
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
            # Normalize against existing schema.
            # When appending, columns being in a different order from
            # the existing geopackage layer can lead to data being in
            # the wrong place. Normalizing ensures the schema of
            # appended data matches.
            existing = gpd.read_file(
                self.CANONICAL_GPKG_FILE,
                layer="driving_tracks",
                rows=0,
            )
            existing_cols = list(existing.columns)
            incoming_cols = list(gdf.columns)
            print("Existing columns:", existing_cols)
            print("Incoming columns:", incoming_cols)

            # Check that geometry column name matches.
            geom_col = gdf.geometry.name
            if geom_col not in existing_cols:
                raise ValueError(
                    f"Geometry column '{geom_col}' not found in existing "
                    "layer schema"
                )

            # Check for columns in new data not in current schema.
            extra_cols = set(incoming_cols) - set(existing_cols)
            if extra_cols:
                raise ValueError(
                    "Incoming data has columns not present in layer "
                    f"schema: {extra_cols}"
                )

            # Add missing columns from existing schema as null values.
            for col in existing_cols:
                if col not in gdf.columns:
                    gdf[col] = None

            # Reorder columns to match existing schema.
            gdf = gdf[existing_cols]


            # Append data to geopackage layer.
            gdf.to_file(
                self.CANONICAL_GPKG_FILE,
                driver="GPKG",
                engine="pyogrio",
                layer="driving_tracks",
                mode="a",
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


    def check_logfile_integrity(self):
        """Checks if number of records matches length."""
        print("Checking logfile integrity.")

        # Get GeoPackage.
        # Note: may be able to look at gpkg_ogr_contents feature_count
        # instead, which may be faster than loading entire GeoPackage.
        gdf = gpd.read_file(self.CANONICAL_GPKG_FILE, layer='driving_tracks')

        # Get count of records.
        con = sqlite3.connect(self.CANONICAL_GPKG_FILE)
        cur = con.cursor()
        res = cur.execute("SELECT COUNT(fid) FROM driving_tracks")
        record_count = res.fetchone()[0]
        con.close()

        # Check integrity.
        if len(gdf) != record_count:
            print("GeoPackage length:", len(gdf))
            print("Record count:", record_count)
            raise RuntimeError("GeoPackage length is incorrect.")


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


    def normalize_times(self):
        """Converts rental table datetimes to the ISO format."""
        sql_select_rentals = f"""
            SELECT fid, pickup_time_utc, return_time_utc
            FROM rentals
            WHERE (
                (pickup_time_utc IS NOT NULL)
                AND (pickup_time_utc NOT LIKE '{self.ISO_FORMAT_LIKE}')
            ) OR (
                (return_time_utc IS NOT NULL)
                AND (return_time_utc NOT LIKE '{self.ISO_FORMAT_LIKE}')
            )
        """
        sql_update_rentals = """
            UPDATE rentals
            SET pickup_time_utc = :pickup, return_time_utc = :return
            WHERE fid = :fid
        """
        with sqlite3.connect(self.CANONICAL_GPKG_FILE) as conn:
            cur = conn.cursor()
            cur.execute(sql_select_rentals)
            print ("Normalizing times in the rentals table.")
            res_rentals = [{
                'fid': r[0],
                'pickup': (
                    datetime.fromisoformat(r[1]).astimezone(timezone.utc)
                    if r[1] is not None else None
                ),
                'return': (
                    datetime.fromisoformat(r[2]).astimezone(timezone.utc)
                    if r[2] is not None else None
                ),
            } for r in cur.fetchall()]
            cur.executemany(sql_update_rentals, res_rentals)
            conn.commit()
            print(f"Updated {cur.rowcount} rentals.")


    def verify_logfile(self):
        """Checks for logfile and copies from template if needed."""
        if os.path.exists(self.CANONICAL_GPKG_FILE):
            print(f"Logfile is present at {self.CANONICAL_GPKG_FILE}.")
            self.check_logfile_integrity()
        else:
            shutil.copy(self.GPKG_TEMPLATE, self.CANONICAL_GPKG_FILE)
            print(f"Copied logfile {self.CANONICAL_GPKG_FILE} from template.")

if __name__ == '__main__':
    dl = DrivingLog()
    dl.normalize_times()