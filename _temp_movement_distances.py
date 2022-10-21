import gpxpy
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from pathlib import Path
from geopy.distance import distance

BE_PATH = Path("~/OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/")
TEST_GPX = BE_PATH / "20221012T125530Z.gpx"

def main(gpx_file):
    with open(gpx_file, 'r') as f:
        gpx = gpxpy.parse(f)

    for track in gpx.tracks:
        for segment in track.segments:
            points = pd.DataFrame.from_records([
                {'lat': point.latitude, 'lon': point.longitude}
                for point in segment.points
            ])
            points['prev_lat'] = points['lat'].shift(1)
            points['prev_lon'] = points['lon'].shift(1)
            points['dist_prev_m'] = points.apply(lambda r: distance_m(r), axis=1)
            points['dist_next_m'] = points['dist_prev_m'].shift(-1)
            print(points)
            # print(points.sort_values('dist_prev_m').tail(30))

def distance_m(row):
    if np.isnan(row['prev_lat']) or np.isnan(row['prev_lon']):
        return np.nan
    return distance(
        (row['lat'], row['lon']), (row['prev_lat'], row['prev_lon'])
    ).meters

if __name__ == "__main__":
    be_path = Path.home() / "OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/"
    test_gpx = be_path / "20221012T125530Z.gpx"
    main(test_gpx)