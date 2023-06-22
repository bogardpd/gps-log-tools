"""Imports GPX files from an input folder."""
import colorama
import sys
import traceback
import tomli
from datetime import timezone
from pathlib import Path
from zipfile import ZipFile
from rename_bad_elf_gpx import rename_bad_elf_gpx
from import_gpx import import_gpx
from export_kmz import export_kmz
from GPXFile import GPXFile

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
IMPORT_ROOT = Path(CONFIG['folders']['import_root']).expanduser()
PROFILES = {
    'bad_elf': "????-??-??-??????-GPX-export.zip",
    'mytracks': "myTracks*.zip",
}

def main():
    print(
        colorama.Style.BRIGHT +
        f"Importing GPX files from {IMPORT_ROOT}." +
        colorama.Style.RESET_ALL
    )
    # Unzip and delete zip files.
    
    print(
        colorama.Style.BRIGHT +
        "Extracting and deleting zip files..." +
        colorama.Style.RESET_ALL
    )

    zip_files = {k: list(IMPORT_ROOT.glob(v)) for k, v in PROFILES.items()}
    for files in zip_files.values():
        for file in files:
            with ZipFile(file, 'r') as zf:
                zf.extractall(IMPORT_ROOT)
            file.unlink() # Delete zipfile

    # Select GPX files.
    gpx_files = list(IMPORT_ROOT.glob("*.gpx"))
    
    # Import GPX files.
    print(
        colorama.Style.BRIGHT +
        "Updating KML with imported files..." +
        colorama.Style.RESET_ALL
    )
    import_gpx(gpx_files)

    # Export an updated KMZ file.
    print(
        colorama.Style.BRIGHT +
        f"Exporting KMZ..." +
        colorama.Style.RESET_ALL
    )
    export_kmz()

    # Move GPX files to raw and rename if needed.
    print(
        colorama.Style.BRIGHT +
        f"Moving GPX files to raw data folder..." +
        colorama.Style.RESET_ALL
    )
    destinations = {
        profile: AUTO_ROOT / CONFIG['folders']['raw'][profile]
        for profile in PROFILES.keys()
    }
    for file in gpx_files:
        gpx_file_obj = GPXFile.load(file)
        destination = destinations[gpx_file_obj.profile]
        if gpx_file_obj.profile == "bad_elf":
            rename_bad_elf_gpx(file, dest_folder_path=destination)
        elif gpx_file_obj.profile == "mytracks":
            first_point_time = min([
                segment.points[0].time.astimezone(timezone.utc)
                for track in gpx_file_obj.gpx.tracks
                for segment in track.segments
            ]).strftime(CONFIG['timestamps']['raw']['mytracks'])

            new_filename = (first_point_time + file.suffix)
            new_filepath = destination / new_filename
            if new_filepath.exists():
                print(
                    colorama.Fore.YELLOW + 
                    f"`{file.name}` already exists. Skipping this file." +
                    colorama.Style.RESET_ALL
                )
            else:
                file.rename(new_filepath)

    print(
        colorama.Style.BRIGHT +
        "GPX Import done!" +
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