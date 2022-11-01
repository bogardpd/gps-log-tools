"""
Removes points from a GPX file below a speed threshold.
"""
import argparse
import gpxpy
import pandas as pd

from pathlib import Path

from gpx_utilities import gpx_profile

M_S_PER_KMH = (1/3.6)
DEFAULT_SPEED_THRESHOLD_M_S = 2.2352 # 2.2352 m/s = 5 MPH

ROLLING_WINDOW = 5

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
    gpx_filtered = filter_speed_gpx(
        gpx, speed_threshold_m_s=float(args.minimum_speed)
    )

    # Write to new GPX file.
    output_path = (
        input_path.parent / f"{input_path.stem}_speed_filtered{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_filtered.to_xml())
    print(f"Saved speed filtered GPX to {output_path}.")


def filter_speed_gpx(gpx, speed_threshold_m_s=DEFAULT_SPEED_THRESHOLD_M_S):
    """Trims points from all track segments in GPX data."""
    profile = gpx_profile(gpx.creator)

    for tn, track in enumerate(gpx.tracks):
        for sn, segment in enumerate(track.segments):
            original_point_count = len(segment.points)
            print(f"\tTrimming segment {sn+1}/{len(track.segments)}.")
            if len(segment.points) < ROLLING_WINDOW:
                print("\tNot enough points to perform a trim.")
            else:
                segment.points = filter_speed(
                    segment.points, speed_threshold_m_s, profile
                )
                diff = original_point_count - len(segment.points)
                print(
                    f"\tRemoved {diff} points below {speed_threshold_m_s} m/s."
                )
    
    return gpx


def filter_speed(
    trackpoints,
    speed_threshold_m_s=DEFAULT_SPEED_THRESHOLD_M_S,
    profile='_default'
):
    """Removes no-motion points at start or end of a segment."""

    # Build dataframe.
    speed_list = [get_speed(point, profile) for point in trackpoints]
    speed_df = pd.DataFrame(speed_list, columns=['speed'])
    if profile == 'mytracks':
        speed_df['speed'] = speed_df['speed'] * M_S_PER_KMH
    speed_df['rolling'] = speed_df['speed'] \
        .rolling(ROLLING_WINDOW).median()

    above_threshold = speed_df[speed_df['rolling'] >= speed_threshold_m_s]

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
    parser.add_argument(
        dest='minimum_speed',
        help="Minimum speed to allow (m/s)",
        nargs='?',
        default=DEFAULT_SPEED_THRESHOLD_M_S,
    )
    args = parser.parse_args()
    main(args)