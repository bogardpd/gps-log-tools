"""Updates ExtendedData within the canonical driving log KML file."""
import argparse
import tomli
from dateutil.parser import parse as dateparse
from pathlib import Path

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

root = Path(CONFIG['folders']['auto_root']).expanduser()
CANONICAL_KML_FILE = root / CONFIG['files']['canonical_kml']

def update_attributes(start_time, thru_time, attribute, value):
    print(start_time, thru_time, attribute, value)
    print(CANONICAL_KML_FILE)

def is_timezone_aware(d):
    return (d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None)

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
    if not is_timezone_aware(args.start):
        raise parser.error("Start must be timezone aware")
    if not is_timezone_aware(args.thru):
        raise parser.error("Thru must be timezone aware")
    
    if args.Creator is not None:
        attr_value = ['Creator', args.Creator]
    elif args.VehicleOwner is not None:
        attr_value = ['VehicleOwner', args.VehicleOwner]
    else:
        raise parser.error("No argument/value pair was provided")
    
    update_attributes(args.start, args.thru, *attr_value)
