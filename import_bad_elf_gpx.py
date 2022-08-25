"""Imports GPX files from an input folder."""
import colorama
import os
import sys
import traceback
import yaml
from pathlib import Path
from zipfile import ZipFile
from rename_bad_elf_gpx import rename_bad_elf_gpx
from update_kml import update_kml

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)
AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
IMPORT_ROOT = Path(CONFIG['folders']['import_root']).expanduser()

def main():
    print(
        colorama.Style.BRIGHT +
        f"Importing Bad Elf GPX files from {IMPORT_ROOT}." +
        colorama.Style.RESET_ALL
    )
    # Unzip and delete zip files.
    
    print(
        colorama.Style.BRIGHT +
        "Extracting and deleting zip files..." +
        colorama.Style.RESET_ALL
    )
    zip_files = list(IMPORT_ROOT.glob("????-??-??-??????-GPX-export.zip"))
    for z in zip_files:
        with ZipFile(z, 'r') as zf:
            zf.extractall(IMPORT_ROOT)
        z.unlink() # Delete zipfile
    
    # Select GPX files.
    gpx_files = list(IMPORT_ROOT.glob("*.gpx"))
    
    # Import GPX files.
    print(
        colorama.Style.BRIGHT +
        "Updating KML with imported files..." +
        colorama.Style.RESET_ALL
    )
    update_kml(gpx_files)

    # Move GPX files to raw and rename if needed.
    destination = (AUTO_ROOT / CONFIG['folders']['raw']['bad_elf'])
    print(
        colorama.Style.BRIGHT +
        f"Moving GPX files to {destination}..." +
        colorama.Style.RESET_ALL
    )
    for gpx_file in gpx_files:
        rename_bad_elf_gpx(gpx_file, dest_folder_path=destination)

    print(
        colorama.Style.BRIGHT +
        "Bad Elf GPX Import done!" +
        colorama.Style.RESET_ALL
    )

if __name__ == "__main__":
    try:
        main()
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        input("Press Enter to continue... ")