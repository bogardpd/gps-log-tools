from pathlib import Path
import gpxpy
import pandas as pd
import matplotlib.pyplot as plt

TEST_FILE = Path(
    "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221110T155308Z.gpx"
).expanduser()

def test_acceleration():
    with open(TEST_FILE, 'r') as f:
        gpx = gpxpy.parse(f)
    for track in gpx.tracks:
        for trkseg in track.segments:
            points = [
                {
                    'time': point.time,
                    'lat': point.latitude,
                    'lon': point.longitude,
                    'speed': get_speed(point),
                }
                for point in trkseg.points
            ]
            df = pd.DataFrame.from_records(points)
            df['speed'] = df['speed'] * 0.277778
            df['speed_diff'] = (df['speed'] - df['speed'].shift())
            df['time_diff'] = (
                df['time'] - df['time'].shift()
            ).dt.total_seconds()
            df['accel'] = df['speed_diff'] / df['time_diff']
            
            print(df.sort_values('accel'))
            # df['accel'].plot()
            # plt.show()

def get_speed(point):
    return next((
        float(e.text) for e in point.extensions
        if e.tag == '{http://mytracks.stichling.info/myTracksGPX/1/0}speed' 
    ), None)

if __name__ == "__main__":
    test_acceleration()