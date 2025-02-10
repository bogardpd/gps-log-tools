"""Imports GPX files into a GeoPackage."""

import argparse
import sys
import traceback
import tomli
from pathlib import Path
from DrivingLog import DrivingLog

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)


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
