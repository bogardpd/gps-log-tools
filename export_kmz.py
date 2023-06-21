"""Exports a GeoPackage driving log to a KMZ file."""

import geopandas as gpd
import pandas as pd
import io
import tomli
from datetime import datetime, time, timezone, timedelta
from lxml import etree
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from pykml.helpers import set_max_decimal_places
from zipfile import ZipFile, ZIP_DEFLATED

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)
ROOT = Path(CONFIG['folders']['auto_root']).expanduser()
EXT_DATA_ATTRIBUTES = {
    'creator':       "Creator",
    'role':          "Role",
    'vehicle_owner': "Vehicle Owner",
}

def export_kmz():
    print("Exporting driving log to KMZ.")
    gpkg_source = ROOT / CONFIG['files']['canonical_gpkg']
    kmz_output = ROOT / CONFIG['files']['output_kmz']
    # Read source file.
    print(f"Reading {gpkg_source}…")
    gdf = gpd.read_file(gpkg_source, layer='driving_tracks')
    gdf = gdf.sort_values('utc_start')

    # Generate KML.
    print("Generating KML…")
    print("- Creating Placemarks…")
    gdf['placemark'] = gdf.apply(lambda r: row_to_placemark(r), axis=1)

    print("- Creating document structure…")
    style = KML.Style(
        KML.LineStyle(
            KML.color("ff0000ff"),
            KML.colorMode("normal"),
            KML.width(4),
        ),
        id='1',
    )

    time_range = gdf_time_range(gdf)
    timespan = KML.TimeSpan(
        KML.begin(time_range[0].isoformat()),
        KML.end(time_range[1].isoformat()),
    )

    kml_doc = KML.kml(
        KML.Document(
            KML.name("Driving"),
            timespan,
            style,
            *(gdf['placemark'].to_list())
        )
    )

    set_max_decimal_places(
        kml_doc,
        max_decimals={'longitude': 6, 'latitude': 6}
    )

    # Export to KMZ file.
    output_params = {
        'pretty_print': True,
        'xml_declaration': True,
        'encoding': "utf-8",
    }
    archive = ZipFile(kmz_output, 'w', compression=ZIP_DEFLATED)
    output = io.BytesIO() 
    etree.ElementTree(kml_doc).write(output, **output_params)
    archive.writestr("doc.kml", output.getvalue())
    print(f"Wrote KMZ to {kmz_output}.")


def gdf_time_range(gdf):
    """Returns a (start, end) tuple covering all tracks."""
    
    # Set document timespan to the midnight prior to earliest
    # timestamp and the midnight following the latest timestamp, so
    # the Google Earth time slider doesn't exclude the first or last
    # track in some situations.
    min_time = datetime.combine(
        gdf['utc_start'].min(), time(0,0,0), tzinfo=timezone.utc
    )
    max_time = datetime.combine(
        gdf['utc_start'].max(), time(0,0,0), tzinfo=timezone.utc
    ) + timedelta(days=1)
    return (min_time, max_time)

def kml_linestring(geom):
    """Converts a shapely linestring to a KML LineString."""
    coord_str = " ".join(
        [",".join(
            str(f) for f in coord
        ) for coord in geom.coords]
    )
    return KML.LineString(KML.coordinates(coord_str))

def row_to_placemark(row):
    """Converts a GeoPandas row to a KML Placemark."""
    pm_name = row.utc_start.strftime(CONFIG['timestamps']['kml_name'])
    pm_desc = (
        KML.description(row.comments) if pd.notnull(row.comments)
        else None
    )

    # Build geometry.
    linestrings = [kml_linestring(geom) for geom in row.geometry.geoms]

    # Build ExtendedData.
    ext_data_elements = [
        KML.Data(
            KML.displayName(display_name),
            KML.value(row[attr_name]),
            name=attr_name,
        )
        for attr_name, display_name in EXT_DATA_ATTRIBUTES.items()
        if pd.notnull(row[attr_name])
    ]

    pm = KML.Placemark(
        KML.name(pm_name),
        pm_desc,
        KML.ExtendedData(*ext_data_elements),
        KML.TimeStamp(
            KML.when(row.utc_start.isoformat())
        ),
        KML.styleUrl("#1"),
        KML.altitudeMode("clampToGround"),
        KML.tessellate(1),
        KML.MultiGeometry(*linestrings),
    )
    return pm


if __name__ == "__main__":
    export_kmz()