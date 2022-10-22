import gpxpy
import pandas as pd
import numpy as np
from pathlib import Path
from geopy.distance import distance

SPEED_THRESHOLD = 100.0 # meters per second

DISPLAY_COLS = [
    'time', 'lat', 'lon',
    'dist_prev', 'time_prev', 'speed_prev', 'speed_next',
]

def find_outliers(gpx_file):
    print(f"Finding outliers in {gpx_file}.")
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    for track in gpx.tracks:
        for segment in track.segments:
            points = pd.DataFrame.from_records([
                {
                    'time': point.time,
                    'lat': point.latitude,
                    'lon': point.longitude
                }
                for point in segment.points
            ])
            points['prev_lat'] = points['lat'].shift(1)
            points['prev_lon'] = points['lon'].shift(1)
            # Distance from previous point in meters:
            points['dist_prev'] = points.apply(lambda r: distance_m(r), axis=1)
            # Time difference from previous point in seconds:
            points['time_prev'] = points['time'].diff().dt.seconds
            # Speed from previous/to next point in meters per second:
            points['speed_prev'] = points['dist_prev'] / points['time_prev']
            points['speed_next'] = points['speed_prev'].shift(-1)
            
            # Find outliers by looking for points where speed from prior
            # point and speed to next point are both above the speed
            # threshold.
            outliers = points[
                (points['speed_prev'] > SPEED_THRESHOLD)
                & (points['speed_next'] > SPEED_THRESHOLD)
            ]

            if len(outliers) > 0:
                print(outliers[DISPLAY_COLS])

def distance_m(row):
    if np.isnan(row['prev_lat']) or np.isnan(row['prev_lon']):
        return np.nan
    return distance(
        (row['lat'], row['lon']), (row['prev_lat'], row['prev_lon'])
    ).meters

if __name__ == "__main__":
    be_path = Path.home() / "OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/"
    # test_gpx = be_path / "20221012T125530Z.gpx"
    # find_outliers(test_gpx)
    for f in list(be_path.glob("*.gpx")):
        find_outliers(f)