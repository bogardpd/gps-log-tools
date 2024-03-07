import geopandas as gpd
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tomli
from datetime import timedelta
from pathlib import Path
from pyproj import Geod

MILES_PER_KM = 0.621371
BIN_MI = 10 # Histogram bin size in miles

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
ROOT = Path(CONFIG['folders']['auto_root']).expanduser()

def chart_driving_range(charge_time_hours):
    gpkg_source = ROOT / CONFIG['files']['canonical_gpkg']

    print(f"Reading {gpkg_source}...")
    gdf = gpd.read_file(gpkg_source, layer='driving_tracks')

    grouped = group_drives(gdf, charge_time_hours)
    print("BY DATE")
    print(grouped)
    print("TOP DISTANCES")
    print(grouped.sort_values('length_mi', ascending=False).head(20))
    plot_histogram(grouped)
    
def group_drives(gdf, charge_time_hours):
    """Calculates lengths of driving between lengthy breaks."""
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
    print("Grouping...")
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
    grouped['length_km'] = grouped['length_m'] * 0.001
    grouped['length_mi'] = grouped['length_km'] * MILES_PER_KM
    return grouped[['utc_start', 'utc_stop', 'length_km', 'length_mi']]

def plot_histogram(grouped_drives):
    """Plots a histogram of grouped data."""
    bins = np.arange(0, max(grouped_drives['length_mi']) + BIN_MI, BIN_MI)
    fig, ax = plt.subplots(1, 1, tight_layout=True)
    ax.hist(grouped_drives['length_mi'], bins=bins)
    ax.set_xlabel("Distance (mi)")
    ax.set_ylabel("Frequency")
    plt.show()


if __name__ == "__main__":
    chart_driving_range(CONFIG['driving_range']['recharge_time_hours'])