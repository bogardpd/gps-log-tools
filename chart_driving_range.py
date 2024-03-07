import geopandas as gpd
import pandas as pd
import tomli
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

    print(gdf)

if __name__ == "__main__":
    chart_driving_range(CONFIG['driving_range']['recharge_time_hours'])