"""
Removes excess points from beginning of a GPX file's track segments
before significant movement starts.
"""
import argparse
import gpxpy
import math
import pandas as pd
from pathlib import Path

ROLLING_WINDOW = 5
SPEED_THRESHOLD = 0.4 # m/s
SPEED_TAGS = [
    '{http://bad-elf.com/xmlschemas/GpxExtensionsV1}speed',
    '{http://bad-elf.com/xmlschemas}speed'
]

def main(args):
    print(f"Trimming {args.gpx_file}.")

    # Open and parse GPX.
    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)

    # Trim GPX.
    gpx_trimmed = trim_gpx(gpx)

    # Write to new GPX file.
    output_path = (
        input_path.parent / f"{input_path.stem}_trimmed{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_trimmed.to_xml())
    print(f"Saved trimmed GPX to {output_path}.")


def trim_gpx(gpx):
    """Trims points from all track segments in GPX data."""
    
    for tn, track in enumerate(gpx.tracks):
        for sn, segment in enumerate(track.segments):
            original_point_count = len(segment.points)
            print(f"\tTrimming segment {sn+1}/{len(track.segments)}.")
            
            segment.points = trim_start(segment.points)
            
            difference = original_point_count - len(segment.points)
            print(f"\tRemoved {difference} excess points at start of segment.")
    
    return gpx


def trim_start(trackpoints):
    """Removes points at start of a segment before movement begins."""
    
    # Build dataframe.
    speed_list = [get_speed(point) for point in trackpoints]
    speed_df = pd.DataFrame(speed_list, columns=['speed'])
    speed_df['rolling'] = speed_df['speed'] \
        .rolling(ROLLING_WINDOW).median()
    
    # Find the row where the rolling median exceeds the threshold.
    start = speed_df[speed_df['rolling'] >= SPEED_THRESHOLD].index[0]

    # Move half the median earlier to find where movement started.
    start = max(start - math.floor(ROLLING_WINDOW/2), 0)

    return trackpoints[start:]


def get_speed(point):
    """Gets a waypoint's speed. Returns None if no speed."""
    
    # Build dictionary of extensions.
    ext_dict = {e.tag: e.text for e in point.extensions}
    
    # Search for a speed tag.
    for tag in SPEED_TAGS:
        tag_text = ext_dict.get(tag)
        if tag_text is not None:
            return float(tag_text)
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trim GPX")
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to trim",
    )
    args = parser.parse_args()
    main(args)