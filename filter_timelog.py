import argparse
import gpxpy
import pandas as pd
from pathlib import Path
import pytz
import tomli

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)


def main(args):
    print(f"Filtering by timelog for {args.gpx_file}.")

    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)

    # Filter GPX.
    gpx_filtered = filter_gpx_by_timelog(gpx)
    
    # Write to new GPX file.
    output_path = (
        input_path.parent
        / f"{input_path.stem}_timelog_filtered{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_filtered.to_xml())
    print(f"Saved timelog filtered GPX to {output_path}.")

def filter_gpx_by_timelog(gpx):
    """Filters a GPX file against the timelog."""

    # Get timelog segments.
    timesegs = get_timelog_segments()

    for track in gpx.tracks:
        track = filter_track_by_timelog(track, timesegs=timesegs)

    return gpx

def filter_track_by_timelog(track, timesegs=None):
    """Filters a GPX track against the timelog."""
    if timesegs is None:
        timesegs = get_timelog_segments()
    
    filtered_segments = []
    for segment in track.segments:
        filtered_segments.append(filter_segment_by_timelog(segment))
    
    # Flatten list of list of segments:
    track.segments = [
        item
        for sublist in filtered_segments
        for item in sublist
    ]

    return track

def filter_segment_by_timelog(segment, timesegs=None):
    """Filters a GPX segment against the timelog.
    
    Returns a list of segments.
    """
    if timesegs is None:
        timesegs = get_timelog_segments()

    # Get earliest and latest point time.
    first_time = segment.points[0].time
    last_time = segment.points[-1].time
    
    # Get timesegs that overlap the segment.
    timesegs_within_segment = timesegs[
        (timesegs['stop_utc'] > first_time)
        & (timesegs['start_utc'] < last_time)
    ]
    if len(timesegs_within_segment) == 0:
        raise ValueError("Timelog has no overlap with trkseg.")

    # Create a new segment for each timeseg
    segments = []
    for timeseg in timesegs.itertuples():
        points = [
            point for point in segment.points
            if (
                point.time >= timeseg.start_utc
                and point.time <= timeseg.stop_utc
            )
        ]
        if len(points) > 0:
            new_segment = gpxpy.gpx.GPXTrackSegment()
            new_segment.points = points
            segments.append(new_segment)
    
    return segments



def get_timelog_segments():
    """Parses the timelog and returns a dataframe."""
    LOG_PATH = Path(CONFIG['files']['absolute']['timelog']).expanduser()
    df = pd.read_csv(LOG_PATH, parse_dates=['time'])

    # Convert to UTC.
    df['time_utc'] = df['time'].dt.tz_convert(pytz.utc)
    df = df.sort_values('time_utc')

    # Create a new segment whenever non '+' status changes to '+'. This
    # means if there are duplicate starts or stops, the earliest start
    # and the latest stop will be used.
    df['segment'] = (
        (df['status'] == "+")
        & (df['status'].shift() != "+")
    ).astype(int).cumsum()

    # Group by segment.
    grouped = df.groupby('segment').agg(
        start_utc=('time_utc', min),
        stop_utc=('time_utc', max),
    )

    # If first entry was a stop (start_utc == stop_utc), then set start
    # to none.
    if grouped.iloc[0]['start_utc'] == grouped.iloc[0]['stop_utc']:
        grouped.iloc[0, grouped.columns.get_loc('start_utc')] = None

    # If last entry was a start (start_utc == stop_utc), then set stop
    # to none.
    if grouped.iloc[-1]['start_utc'] == grouped.iloc[-1]['stop_utc']:
        grouped.iloc[-1, grouped.columns.get_loc('stop_utc')] = None
    
    grouped['duration'] = grouped['stop_utc'] - grouped['start_utc']
    return grouped

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Filter GPX track into segments by when car was running"
    )
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to filter",
    )
    args = parser.parse_args()
    main(args)