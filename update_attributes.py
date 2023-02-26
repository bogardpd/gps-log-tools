"""Updates ExtendedData within the canonical driving log KML file."""
import argparse
import shutil
import tomli
from dateutil.parser import parse as date_parse
from dateutil.parser import ParserError
from lxml import etree
from pathlib import Path
from tabulate import tabulate

NSMAP = {None: "http://www.opengis.net/kml/2.2"}
DISPLAY_NAMES = {
    'creator':       "Creator",
    'role':          "Role",
    'vehicle_owner': "Vehicle Owner",
}

def update_attributes(start_time, thru_time, attribute, value):
    # Load config and determine file paths.
    with open(Path(__file__).parent / "config.toml", 'rb') as f:
        CONFIG = tomli.load(f)
    root = Path(CONFIG['folders']['auto_root']).expanduser()
    CANONICAL_KML_FILE = root / CONFIG['files']['canonical_kml']
    CANONICAL_BACKUP_FILE = root / CONFIG['files']['canonical_backup']

    # Parse existing canonical KML file.
    parser = etree.XMLParser(remove_blank_text=True)
    root = etree.parse(str(CANONICAL_KML_FILE), parser).getroot()
    et = etree.ElementTree(root)
    
    # Find Placemarks within the provided time range and update them,
    # returning a list of (old_value, placemark) tuples.
    placemarks_in_range = [
        (
            get_data(placemark, attribute),
            update_placemark(placemark, attribute, value),
        )
        for placemark in et.iterfind(".//Placemark", NSMAP)
        if is_in_range(placemark, start_time, thru_time)
    ]

    if len(placemarks_in_range) == 0:
        print("No tracks fall in the provided time range.")
        quit()

    print("Proposed changes:")
    placemark_changes_table = [
        [
            placemark[1].find("./name", NSMAP).text,
            placemark[0],
            value
        ]
        for placemark in placemarks_in_range
    ]
    print(tabulate(placemark_changes_table, headers=["Track","Current","New"]))
    print(f"{len(placemarks_in_range)} track(s)")

    proceed = input("Write changes to file? (y/n) ")
    if proceed.lower() != "y":
        # Do not write changes to file.
        print("No changes made.")
        quit()

    # Run backup.
    shutil.copy(CANONICAL_KML_FILE, CANONICAL_BACKUP_FILE)
    print(f"Backed up canonical data to {CANONICAL_BACKUP_FILE}.")

    # Write changes to file.
    output_params = {
        'pretty_print': True,
        'xml_declaration': True,
        'encoding': "utf-8",
    }
    et.write(str(CANONICAL_KML_FILE), **output_params)
    print(f"Saved updates to {CANONICAL_KML_FILE}.")

def get_data(placemark, attribute):
    data_elem = placemark.find(
        f"./ExtendedData/Data[@name='{attribute}']/value",
        NSMAP
    )
    if data_elem is None:
        return None
    else:
        return data_elem.text

def is_in_range(placemark, start_time, thru_time):
    when = placemark.find("./TimeStamp/when", NSMAP)
    if when is None:
        return False
    try:
        ts = date_parse(when.text)
    except (ParserError, TypeError):
        return False
    return (start_time <= ts <= thru_time)

def is_timezone_aware(d):
    return (d.tzinfo is not None and d.tzinfo.utcoffset(d) is not None)

def update_placemark(placemark, attribute, value):
    """Updates and returns a placemark."""
    existing_data = placemark.find(
        f"./ExtendedData/Data[@name='{attribute}']/value",
        NSMAP
    )
    if existing_data is None:
        ext_data = placemark.find("./ExtendedData", NSMAP)
        if ext_data is None:
            ext_data = etree.SubElement(placemark, "ExtendedData")
        data = etree.SubElement(ext_data, "Data", attrib={'name': attribute})
        etree.SubElement(data, "displayName").text = DISPLAY_NAMES[attribute]
        etree.SubElement(data, "value").text = value
    else:
        existing_data.text = value
    return placemark           



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
    attr_group.add_argument('--role',
        help="driver or passenger",
        type=str,
        choices=['driver', 'passenger']
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
    elif args.role is not None:
        attr_value = ['role', args.role]
    elif args.vehicle_owner is not None:
        attr_value = ['vehicle_owner', args.vehicle_owner]
    else:
        raise parser.error("No argument/value pair was provided")
    
    update_attributes(args.start, args.thru, *attr_value)
