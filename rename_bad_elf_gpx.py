"""Renames Bad Elf GPX files to a common filename timestamp format."""
import gpxpy
import yaml
from datetime import datetime, timezone
from pathlib import Path

with open(Path(__file__).parent / "config.yaml", 'r') as f:
    CONFIG = yaml.safe_load(f)
AUTO_ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
TIME_FORMAT = CONFIG['timestamps']['raw']['bad_elf']


def main():
    gpx_path = AUTO_ROOT / CONFIG['folders']['raw']['bad_elf']
    to_rename = [
        f for f in gpx_path.iterdir()
        if f.is_file() and not time_format_matches(f.stem, TIME_FORMAT)
    ]
    print(f"Correcting GPX file names in {gpx_path}...")
    for f in to_rename:
        rename_bad_elf_gpx(f)
    print(f"{len(to_rename)} file(s) renamed.")


def time_format_matches(time_str, format):
    """Returns true if time_str is in provided strptime format."""
    try:
        if time_str != datetime.strptime(time_str, format).strftime(format):
            raise ValueError
        return True
    except ValueError:
        return False


def rename_bad_elf_gpx(gpx_file, dest_folder_path = None):
    """Renames a GPX file to match the configured timestamp format."""
    
    # Get the timestamp for the earliest waypoint in the GPX file.
    with open(gpx_file, 'r') as gf:
        gpx = gpxpy.parse(gf)
    first_point_time = min([
        segment.points[0].time.astimezone(timezone.utc)
        for track in gpx.tracks
        for segment in track.segments
    ]).strftime(TIME_FORMAT)

    # Rename the file.
    new_filename = (first_point_time + gpx_file.suffix)
    if dest_folder_path is None:
        new_filepath = gpx_file.parent / new_filename
    else:
        new_filepath = dest_folder_path / new_filename

    if new_filepath.exists():
        print(f"`{gpx_file.name} already exists. Skipping this file.")
    elif new_filename == gpx_file.name and dest_folder_path is None:
        print(f"`{gpx_file.name} is already in the correct format.")
    else:
        gpx_file.rename(new_filepath)
        print(f"`{gpx_file.name}` renamed to `{new_filename}`.")
    return Path(new_filepath)


if __name__ == "__main__":
    main()