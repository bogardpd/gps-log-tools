"""Splits a KMZ file into a GPX file with individual tracks."""

import os
import sys
import traceback
import gpxpy
import simplekml
import re
from datetime import datetime, timezone, timedelta
from dateutil.parser import parse
from lxml import etree
from zipfile import ZipFile

MIN_POINTS = 5 # Only keep linestrings with at least this many points
TIMEZONES = {
    "UTC": "+00:00",
    "ADT": "-03:00",
    "AST": "-04:00",
    "EDT": "-04:00",
    "EST": "-05:00",
    "CDT": "-05:00",
    "CST": "-06:00",
    "MDT": "-06:00",
    "MST": "-07:00",
    "PDT": "-07:00",
    "PST": "-08:00",
    "HST": "-10:00",
}

def main(argv):
    """Merges a GPX file into existing KML data."""
    try:
        input_kmz_file = argv[1]
    except IndexError:
        raise SystemExit(f"Usage: {argv[0]} <tracks.gpx>")
    
    print(f"Converting `{input_kmz_file}`")

    kmz = ZipFile(input_kmz_file, 'r')
    kml = kmz.read('doc.kml')

    root = etree.fromstring(kml)
    nsmap = {None: "http://www.opengis.net/kml/2.2"}

    track_dict = {}

    for placemark in root.findall('.//Placemark', nsmap):
        print()
        name_txt = placemark.find("name", nsmap).text
        linestrings = placemark.findall('.//LineString', nsmap)
        names = name_txt.replace("Active Log: ", "").split(" + ")
        names = [re.sub(r' [A-Z]{3}$', '', n) for n in names]
        start_time_str = parse(names[0]).isoformat()
        print(f"TRACK: {start_time_str}")
        # print(f"Name count: {len(names)}")
        print(f"Linestring count: {len(linestrings)}")
        offset = input("What time zone? (EST EDT etc.) ")
        offset_str = TIMEZONES[offset.upper()]
        start_time = parse(start_time_str + offset_str)
        start_time = start_time.astimezone(timezone.utc)
        
        lines = []
        for linestring in linestrings:
            # Append coords if they are at least MIN_POINTS in length.
            coords_txt = linestring.find("coordinates", nsmap).text
            coords = coords_to_list(coords_txt)
            if len(coords) >= MIN_POINTS:
                lines.append(coords)

        for i_line, line in enumerate(lines):
            # Loop through lines, assigning times by starting with
            # start_time and incrementing by 1 second intervals. (If
            # there is only one line, then it will automatically
            # get start_time anyway.)
            ls_time = start_time + timedelta(seconds=i_line)
            track_dict[ls_time] = dict(coords=line)


    # Write track_dict to GPX file, using timestamp on first wpt.

    gpx_file = input_kmz_file.replace(".kmz",".gpx")
    gpx = gpxpy.gpx.GPX()
    for timestamp, v in track_dict.items():
        track = gpxpy.gpx.GPXTrack()
        track.name = timestamp.isoformat()
        gpx.tracks.append(track)
        segment = gpxpy.gpx.GPXTrackSegment()
        track.segments.append(segment)
        for i_c, coords in enumerate(v['coords']):
            lon, lat, ele = coords
            point = gpxpy.gpx.GPXTrackPoint(lat, lon, elevation=ele)
            if i_c == 0:
                point.time = timestamp
            segment.points.append(point)

    with open(gpx_file, "w", encoding="utf-8") as f:
        f.write(gpx.to_xml())
    
    print(f"Wrote to `{gpx_file}`!")

def coords_to_list(coords_str):
    coords_str = coords_str.strip()
    coords = list(
        tuple(
            float(n) for n in c.split(",")
        ) for c in coords_str.split(" ")
    )
    return coords


if __name__ == "__main__":
    try:
        main(sys.argv)
    except BaseException:
        print(sys.exc_info()[0])
        print(traceback.format_exc())
    finally:
        os.system("pause")
