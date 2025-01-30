import sqlite3
import tomli
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
DRIVING_LOG_PATH = AUTO_ROOT / CONFIG['files']['canonical_gpkg']

ISO_FORMAT = "%Y-%m-%dT%H:%M:%SZ"
sqlite3.register_adapter(
    datetime,
    lambda dt: dt.strftime(ISO_FORMAT).encode('utf-8'),
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
                return.discriminator AS return_discriminator
            FROM rentals
            JOIN rental_locations AS pickup
                ON rentals.pickup_rental_location_fid = pickup.fid
            JOIN rental_locations AS return
                ON rentals.return_rental_location_fid = return.fid
            WHERE rentals.fid = ?
        """
        cur.execute(sql_select, (fid,))
        rental = cur.fetchone()
        if rental is None:
            print(f"Rental with feature ID {fid} not found.")
            return
        pickup_date = datetime.strptime(rental[0], "%Y-%m-%d").date()
        return_date = datetime.strptime(rental[1], "%Y-%m-%d").date()
        pickup_tz = rental[2]
        return_tz = rental[3]
        pickup_location = format_loc_name(rental[4], rental[6], rental[8])
        return_location = format_loc_name(rental[5], rental[7], rental[9])
        print(f"Pickup: {pickup_date} @ {pickup_location}")
        print(f"Return: {return_date} @ {return_location}")
        pickup_time = input(
            f"Enter the start time on {pickup_date} in {pickup_tz} (HH:MM): "
        )
        pickup_dt_utc = create_datetime(pickup_date, pickup_time, pickup_tz)
        if pickup_dt_utc is None:
            print("No pickup time")
        else:
            print(pickup_dt_utc.strftime(ISO_FORMAT))
        return_time = input(
            f"Enter the start time on {return_date} in {return_tz} (HH:MM): "
        )
        return_dt_utc = create_datetime(return_date, return_time, return_tz)
        if return_dt_utc is None:
            print("No return time")
        else:
            print(return_dt_utc.strftime(ISO_FORMAT))
        proceed = input("Proceed with updating the rental times? (y/n): ")
        if proceed.lower() == 'y':
            cur.execute(
                """
                    UPDATE rentals SET pickup_time_utc = ?, return_time_utc = ?
                    WHERE fid = ?
                """,
                (pickup_dt_utc, return_dt_utc, fid)
            )
            conn.commit()
            print(f"Updated rental with feature ID {fid}.")
        else:
            print("Aborted.")

def create_datetime(date, time, tz):
    if len(time) == 0:
        return None
    hour, minute = [int(t) for t in time.split(":")]
    return datetime(
        date.year, date.month, date.day,
        hour, minute, tzinfo=ZoneInfo(tz)
    ).astimezone(ZoneInfo("UTC"))

def format_loc_name(agency, location, discriminator):
    output = f"{agency} {location}"
    if discriminator:
        output += f" [{discriminator}]"
    return output


if __name__ == '__main__':
    update_rental_times()