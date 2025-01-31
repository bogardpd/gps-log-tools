"""Class for interacting with a driving log."""

import tomli
import sqlite3
import pytz
from datetime import datetime, timezone
from pathlib import Path

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
DRIVING_LOG_PATH = (
    Path(CONFIG['folders']['auto_root']).expanduser()
    / CONFIG['files']['canonical_gpkg']
)

class DrivingLog:
    def __init__(self, gpkg_path=DRIVING_LOG_PATH) -> None:
        self.gpkg_path = gpkg_path
        self.ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
        self.ISO_FORMAT_LIKE = "____-__-__T__:__:__Z"
        sqlite3.register_adapter(
            datetime,
            lambda dt: dt.strftime(self.ISO_FORMAT),
        )

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
        with sqlite3.connect(self.gpkg_path) as conn:
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
        
if __name__ == '__main__':
    dl = DrivingLog()
    dl.normalize_times()