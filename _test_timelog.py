import pandas as pd
from pathlib import Path
import pytz
import tomli

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
TIMELOG = Path(CONFIG['files']['absolute']['timelog']).expanduser()

def test_timelog():
    df = pd.read_csv(TIMELOG, parse_dates=['time'])

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
        stop_utc=('time_utc', max)
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
    print(grouped)

if __name__ == "__main__":
    test_timelog()