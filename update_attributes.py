"""Updates ExtendedData within the canonical driving log KML file."""
import argparse
import tomli
from dateutil.parser import parse as date_parse
from dateutil.parser import ParserError
from pathlib import Path
from pykml import parser as kml_parser
from tabulate import tabulate

NSMAP = {None: "http://www.opengis.net/kml/2.2"}
NAMES = {
    'creator': "Creator",
    'vehicle_owner': "Vehicle Owner"
}

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

root = Path(CONFIG['folders']['auto_root']).expanduser()
CANONICAL_KML_FILE = root / CONFIG['files']['canonical_kml']

def update_attributes(start_time, thru_time, attribute, value):
    print(start_time, thru_time, attribute, value)
    
    with open(CANONICAL_KML_FILE) as f:
        doc = kml_parser.parse(f)

    placemarks_in_range = [
        placemark
        for placemark in doc.iterfind(".//Placemark", NSMAP)
        if is_in_range(placemark, start_time, thru_time)
    ]

    print("Matching placemarks:")
    placemarks_current_values = [
        [placemark.name.text, get_data(placemark, attribute)]
        for placemark in placemarks_in_range
    ]
    print(tabulate(placemarks_current_values))

    # for placemark in doc.iterfind(".//Placemark", NSMAP):
    #     when = placemark.find("./TimeStamp/when", NSMAP)
    #     try:
    #         ts = date_parse(when.text)
    #     except (ParserError, TypeError):
    #         continue
    #     to_update = []
    #     if start_time <= ts <= thru_time:
    #         update_attribute(placemark, attribute, value)

def is_in_range(placemark, start_time, thru_time):
    when = placemark.find("./TimeStamp/when", NSMAP)
    if when is None:
        return False
    try:
        ts = date_parse(when.text)
    except (ParserError, TypeError):
        return False
    return (start_time <= ts <= thru_time)

def get_data(placemark, attribute):
    data_elem = placemark.find(f"./ExtendedData/Data[@name='{attribute}']/value", NSMAP)
    if data_elem is None:
        return None
    else:
        return data_elem.text

# def update_attribute(placemark, attribute, value):
#     print(placemark.name.text)
#     data_elem = placemark.find(f"./ExtendedData/{attribute}")
#     if data_elem is None:
#         print("Need to create data element")
#     else:
#         print("Need to update element")
            
def is_timezone_aware(d):
    return (d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Update canonical KML attributes"
    )

    parser.add_argument('--start',
        help="The earliest timestamp to update, in RFC3339 format (with 'T')",
        type=date_parse,
        required=True,
    )
    parser.add_argument('--thru',
        help="The latest timestamp to update, in RFC3339 format (with 'T')",
        type=date_parse,
        required=True,
    )
    attr_group = parser.add_mutually_exclusive_group(required=True)
    attr_group.add_argument('--creator',
        help="Name of device or software that created the track",
        type=str,
    )
    attr_group.add_argument('--vehicle_owner',
        help="personal or rental",
        type=str,
        choices=['personal', 'rental']
    )
    
    args = parser.parse_args()
    if not is_timezone_aware(args.start):
        raise parser.error("Start must be timezone aware")
    if not is_timezone_aware(args.thru):
        raise parser.error("Thru must be timezone aware")
    
    if args.creator is not None:
        attr_value = ['creator', args.creator]
    elif args.vehicle_owner is not None:
        attr_value = ['vehicle_owner', args.vehicle_owner]
    else:
        raise parser.error("No argument/value pair was provided")
    
    update_attributes(args.start, args.thru, *attr_value)
