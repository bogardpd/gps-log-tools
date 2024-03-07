import geopandas as gpd
import pandas as pd
import numpy as np
import pandas as pd
import tomli
from datetime import timedelta
from pathlib import Path
from pyproj import Geod

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
ROOT = Path(CONFIG['folders']['auto_root']).expanduser()

def chart_driving_range(charge_time_hours):
    gpkg_source = ROOT / CONFIG['files']['canonical_gpkg']

    # Read source file.
    print(f"Reading {gpkg_source}...")
    gdf = gpd.read_file(gpkg_source, layer='driving_tracks')
    
    # Filter and sort.
    gdf = gdf[gdf['vehicle_owner'] == "personal"]
    gdf = gdf[pd.notnull(gdf['utc_stop'])]
    gdf = gdf.sort_values('utc_start')
    
    # Calculate lengths.
    print("Calculating lengths...")
    geod = Geod(ellps="WGS84")
    gdf['length_m'] = gdf.apply(
        lambda x: geod.geometry_length(x.geometry),
        axis=1
    )
    
    # Create per-charge groupings.
    df = pd.DataFrame(gdf[['utc_start', 'utc_stop', 'length_m']])
    df['break_prior'] = df['utc_start'] - df.shift(1)['utc_stop']
    df['charge_group'] = np.where(
        df['break_prior'] >= timedelta(hours=charge_time_hours), 1, 0
    ).cumsum()
    grouped = df.groupby('charge_group').agg({
        'utc_start': "min",
        'utc_stop': "max",
        'length_m': "sum",
    }, numeric_only=True)
    print(grouped)
    


if __name__ == "__main__":
    chart_driving_range(CONFIG['driving_range']['recharge_time_hours'])