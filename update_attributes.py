"""Updates ExtendedData within the canonical driving log KML file."""
import argparse
import tomli
from dateutil.parser import parse as dateparse
from pathlib import Path

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

def update_attributes(start_time, thru_time, attribute, value):
    pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update canonical KML attributes"
    )

    parser.add_argument('--start',
        help="The earliest timestamp to update, in RFC3339 format (with 'T')",
        type=dateparse,
        required=True,
    )
    parser.add_argument('--thru',
        help="The latest timestamp to update, in RFC3339 format (with 'T')",
        type=dateparse,
        required=True,
    )
    attr_group = parser.add_mutually_exclusive_group(required=True)
    attr_group.add_argument('--Creator',
        help="Name of device or software that created the track",
        type=str,
    )
    attr_group.add_argument('--VehicleOwner',
        help="personal or rental",
        type=str,
        choices=['personal', 'rental']
    )

    args = parser.parse_args()
    print(args)
