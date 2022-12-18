"""
Removes points from a GPX file below a speed threshold.
"""
import argparse
import gpxpy
import pandas as pd
import tomli

from pathlib import Path

from gpx_utilities import gpx_profile

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

DEFAULT_MIN_SPEED_M_S = 2.2352 # 2.2352 m/s = 5 MPH
DEFAULT_ROLLING_WINDOW = 25
DEFAULT_METHOD = 'center'
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
    print(f"Filtering low speeds from {args.gpx_file}.")

    # Open and parse GPX.
    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)

    # Trim GPX.
    gpx_filtered = gpx_filter_speed(gpx,
        min_speed_m_s=float(args.min_speed),
        rolling_window=int(args.rolling_window),
        method=args.method,
    )

    # Write to new GPX file.
    output_path = (
        input_path.parent
        / f"{input_path.stem}_speed_filtered{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_filtered.to_xml())
    print(f"Saved speed filtered GPX to {output_path}.")


def gpx_filter_speed(gpx,
    min_speed_m_s=DEFAULT_MIN_SPEED_M_S,
    rolling_window=DEFAULT_ROLLING_WINDOW,
    method=DEFAULT_METHOD,
):
    """Trims points from all track segments in GPX data."""
    profile = gpx_profile(gpx.creator)

    for tn, track in enumerate(gpx.tracks):
        trk_filter_speed(track,
            min_speed_m_s,
            rolling_window,
            method,
            profile,
        )
    return gpx

def trk_filter_speed(trk,
    min_speed_m_s=DEFAULT_MIN_SPEED_M_S,
    rolling_window=DEFAULT_ROLLING_WINDOW,
    method=DEFAULT_METHOD,
    profile='_default'
):
    for sn, segment in enumerate(trk.segments):
        original_point_count = len(segment.points)
        print(f"  Speed filtering segment {sn+1}/{len(trk.segments)}.")
        if len(segment.points) < rolling_window:
            print("    Not enough points to perform a filter.")
        else:
            segment.points = filter_speed(
                segment.points,
                min_speed_m_s,
                rolling_window,
                method,
                profile,
            )
            diff = original_point_count - len(segment.points)
            print(
                f"    Removed {diff} points below {min_speed_m_s} m/s."
            )
    return trk

def filter_speed(trackpoints,
    min_speed_m_s=DEFAULT_MIN_SPEED_M_S,
    rolling_window=DEFAULT_ROLLING_WINDOW,
    method=DEFAULT_METHOD,
    profile='_default'
):
    """Removes no-motion points at start or end of a segment."""

    # Build dataframe.
    speed_list = [get_speed(point, profile) for point in trackpoints]
    speed_df = pd.DataFrame(speed_list, columns=['speed'])
    speed_df['speed'] = speed_df['speed'] * CONFIG['speed_multiplier'][profile]
    
    # Calculate rolling medians.
    if method == 'center':
    
        speed_df['rolling'] = speed_df['speed'] \
            .rolling(rolling_window, center=True).median()

        above_threshold = speed_df[speed_df['rolling'] >= min_speed_m_s]

    elif method == 'extended':
        # To avoid cutting off too many points during low speed turns
        # after a stop, look at both forward and backward rolling median
        # and keep point if either exceeds speed threshold.
        speed_df['rolling_forward'] = speed_df['speed'] \
            .rolling(rolling_window).median()
        speed_df['rolling_backward'] = speed_df['speed'][::-1] \
            .rolling(rolling_window).median()[::1]

        above_threshold = speed_df[
            (speed_df['rolling_forward'] >= min_speed_m_s)
            | (speed_df['rolling_backward'] >= min_speed_m_s)
        ]

    filtered_trackpoints = [
        trackpoints[at]
        for at in list(above_threshold.index)
    ]
    return filtered_trackpoints
    
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
    parser = argparse.ArgumentParser(description="Filter Low Speeds from GPX")
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to filter low speeds from",
    )
    parser.add_argument("--min_speed",
        dest='min_speed',
        help="Minimum speed to allow (m/s)",
        nargs='?',
        default=DEFAULT_MIN_SPEED_M_S,
    )
    parser.add_argument("--rolling_window",
        dest='rolling_window',
        help="Length of rolling median window",
        nargs='?',
        default=DEFAULT_ROLLING_WINDOW,
    )
    parser.add_argument("--method",
        dest='method',
        help="Rolling average method (center or extended)",
        choices=['center', 'extended'],
        nargs='?',
        default=DEFAULT_METHOD,
    )
    args = parser.parse_args()
    main(args)