import sqlite3
import tomli
from pathlib import Path
from datetime import datetime
from dateutil import parser
from zoneinfo import ZoneInfo

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
DRIVING_LOG_PATH = AUTO_ROOT / CONFIG['files']['canonical_gpkg']

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
sqlite3.register_adapter(
    datetime,
    lambda dt: dt.strftime(ISO_FORMAT),
)

def update_rental_times():
    fid = int(input("Enter the feature ID of the rental to update: "))

    with sqlite3.connect(DRIVING_LOG_PATH) as conn:
        cur = conn.cursor()
        sql_select = """
            SELECT
                pickup_date_local,
                return_date_local,
                pickup.time_zone AS pickup_tz,
                return.time_zone AS return_tz,
                pickup.agency AS pickup_agency,
                return.agency AS return_agency,
                pickup.location_name AS pickup_location,
                return.location_name AS return_location,
                pickup.discriminator AS pickup_discriminator,
                return.discriminator AS return_discriminator,
                pickup_time_utc,
                return_time_utc
            FROM rentals
            LEFT OUTER JOIN rental_locations AS pickup
                ON rentals.pickup_rental_location_fid = pickup.fid
            LEFT OUTER JOIN rental_locations AS return
                ON rentals.return_rental_location_fid = return.fid
            WHERE rentals.fid = ?
        """
        cur.execute(sql_select, (fid,))
        rental = cur.fetchone()
        if rental is None:
            print(f"Rental with feature ID {fid} not found.")
            return
        pickup_date = (
            datetime.strptime(rental[0], "%Y-%m-%d").date()
            if rental[0] else None
        )
        return_date = (
            datetime.strptime(rental[1], "%Y-%m-%d").date()
            if rental[1] else None
        )
        pickup_tz = rental[2]
        return_tz = rental[3]
        pickup_location = format_loc_name(rental[4], rental[6], rental[8])
        return_location = format_loc_name(rental[5], rental[7], rental[9])
        pickup_new_time_utc = rental[10]
        return_new_time_utc = rental[11]
        print(f"Pickup: {pickup_date} @ {pickup_location}")
        print(f"Return: {return_date} @ {return_location}")
        
        pickup_new_time_utc, pickup_unchanged = request_time(
            "pickup", pickup_date, pickup_tz, pickup_new_time_utc
        )

        return_new_time_utc, return_unchanged = request_time(
            "return", return_date, return_tz, return_new_time_utc
        )        

        if pickup_unchanged and return_unchanged:
            print("No changes made.")
            return
        
        proceed = input("Proceed with updating the rental times? (y/n): ")
        if proceed.lower() == 'y':
            if (not pickup_unchanged) and return_unchanged:
                # Only pickup time changed
                cur.execute(
                    "UPDATE rentals set pickup_time_utc = ? WHERE fid = ?",
                    (pickup_new_time_utc, fid),
                )
            elif pickup_unchanged and (not return_unchanged):
                # Only return time changed
                cur.execute(
                    "UPDATE rentals set return_time_utc = ? WHERE fid = ?",
                    (return_new_time_utc, fid),
                )
            else:
                # Both times changed
                cur.execute(
                    """
                        UPDATE rentals
                        SET pickup_time_utc = ?, return_time_utc = ?
                        WHERE fid = ?
                    """,
                    (pickup_new_time_utc, return_new_time_utc, fid)
                )
            conn.commit()
            print(f"Updated rental with feature ID {fid}.")
        else:
            print("Aborted.")

def format_loc_name(agency, location, discriminator):
    output = f"{agency} {location}"
    if discriminator:
        output += f" [{discriminator}]"
    return output

def request_time(type, date, tz, time_utc_str):
    """Request a time from the user and return a datetime object."""
    def input_time(type, date, tz):
        time = input(
            f"Enter the {type} time on {date} in {tz} (HH:MM): "
        )
        if len(time) == 0:
            return None
        hour, minute = [int(t) for t in time.split(":")]
        return datetime(
            date.year, date.month, date.day,
            hour, minute, tzinfo=ZoneInfo(tz)
        ).astimezone(ZoneInfo("UTC"))
    
    if time_utc_str is None:
        cur_time_utc = None
    else:
        cur_time_utc = parser.isoparse(time_utc_str)

    if tz is None:
        print(f"No {type} time zone, skipping.")
        new_time_utc = None
        unchanged = True
    else:
        if cur_time_utc is not None:
            print(f"Current {type} time: {cur_time_utc.strftime(ISO_FORMAT)}")
            update = input(f"Change {type} time? (y/N): ")
            if update.lower() == 'y':
                new_time_utc = input_time(type, date, tz)
            else:
                new_time_utc = cur_time_utc
        else:
            new_time_utc = input_time(type, date, tz)
        if new_time_utc is None:
            print(f"No {type} time", end="")
        else:
            print(new_time_utc.strftime(ISO_FORMAT), end="")
        unchanged = (cur_time_utc == new_time_utc)
        if unchanged:
            print(" (Unchanged)")
        else:
            print() # newline
    return (new_time_utc, unchanged)


if __name__ == '__main__':
    update_rental_times()