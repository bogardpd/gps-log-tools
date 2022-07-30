"""
Removes excess points from beginning of a GPX file's track segments
before significant movement starts.
"""
import argparse
import gpxpy
import math
import pandas as pd

from pathlib import Path

from gpx_utilities import gpx_profile

ROLLING_WINDOW = 5
# SPEED_THRESHOLD = 0.4 # m/s
SPEED_THRESHOLD = { # m/s
    '_default': 0.4,
    'garmin':   0.4,
    'mytracks': 4.0,
    'bad_elf':  0.4,
}
SPEED_TAGS = {
    'garmin': [
        '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}speed',
    ],
    'mytracks': [
        '{http://mytracks.stichling.info/myTracksGPX/1/0}speed',
    ],
    'bad_elf': [
        '{http://bad-elf.com/xmlschemas/GpxExtensionsV1}speed',
        '{http://bad-elf.com/xmlschemas}speed',
    ],
}

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
    profile = gpx_profile(gpx.creator)

    for tn, track in enumerate(gpx.tracks):
        for sn, segment in enumerate(track.segments):
            original_point_count = len(segment.points)
            print(f"\tTrimming segment {sn+1}/{len(track.segments)}.")
            if len(segment.points) < ROLLING_WINDOW:
                print("\tNot enough points to perform a trim.")
            else:
                segment.points = trim(segment.points, profile)
                diff = original_point_count - len(segment.points)
                print(
                    f"\tRemoved {diff} excess points from ends of segment."
                )
    
    return gpx


def trim(trackpoints, profile='_default'):
    """Removes no-motion points at start or end of a segment."""

    # Build dataframe.
    speed_list = [get_speed(point, profile) for point in trackpoints]
    speed_df = pd.DataFrame(speed_list, columns=['speed'])
    speed_df['rolling'] = speed_df['speed'] \
        .rolling(ROLLING_WINDOW).median()
    
    # Find the first row where the rolling median exceeds the threshold.
    start = speed_df[speed_df['rolling'] >= SPEED_THRESHOLD[profile]].index[0]
    # Move half the median earlier to find where movement started.
    start = max(start - math.floor(ROLLING_WINDOW/2), 0)
    
    # Find the last row where the rolling median exceeds the threshold.
    end = speed_df[speed_df['rolling'] >= SPEED_THRESHOLD[profile]].index[-1]
    # Move half the median earlier to find where movement ended.
    end = max(end - math.floor(ROLLING_WINDOW/2), 0)

    return trackpoints[start:end]


def get_speed(point, profile):
    """Gets a waypoint's speed. Returns None if no speed."""
    
    extensions = point.extensions

    if profile == 'garmin':
        speed = extensions[0].find(SPEED_TAGS['garmin'][0])
    elif profile in ['bad_elf', 'mytracks']:
        speed = next((
            e for e in extensions
            if e.tag in SPEED_TAGS[profile]
        ), None)
    else:
        return None
    
    if speed is not None and speed.text is not None:
        return float(speed.text)
    return None


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trim GPX")
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to trim",
    )
    args = parser.parse_args()
    main(args)