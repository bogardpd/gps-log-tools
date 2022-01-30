"""
Performs a spherical Ramer-Douglas-Peucker simplification of GPX file
tracksegs.

Adapted from https://numbersmithy.com/ramer-douglas-peucker-rdp-algorithm-in-spherical-coordinate/
"""

import argparse
import gpxpy
import numpy as np
from pathlib import Path

DEFAULT_EPSILON = 0.000002
EARTH_RADIUS = 6371000.0 #m

def main(args):
    print(f"Simplifying {args.gpx_file} with ε={args.epsilon}.")

    # Open and parse GPX.
    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)
    
    # Simplify GPX.
    gpx_simplified = simplify(gpx, float(args.epsilon))
    
    # Write to new GPX file.
    output_path = (
        input_path.parent / f"{input_path.stem}_simplified{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_simplified.to_xml())
    print(f"Saved simplified GPX to {output_path}.")


def simplify(gpx, epsilon):
    """Takes GPX data and returns simplified GPX data."""
    for tn, track in enumerate(gpx.tracks):
        print(f"Processing track {tn+1}/{len(gpx.tracks)}: `{track.name}`.")
        for sn, segment in enumerate(track.segments):
            print(f"\tSimplifying segment {sn+1}/{len(track.segments)}.")
            print(f"\t\tOriginal: {len(segment.points)} points")
            
            segment.points = rdp_spherical(segment.points, epsilon)

            print(f"\t\tSimplilfied: {len(segment.points)} points")
            
    return gpx


def rdp_spherical(trackpoints, epsilon):
    """Performs a spherical Ramer-Douglas-Peucker simplification."""
    dmax = 0.0
    index = 0
    for i in range(1, len(trackpoints) - 1):
        startcoord = (trackpoints[0].longitude, trackpoints[0].latitude)
        coord = (trackpoints[i].longitude, trackpoints[i].latitude)
        endcoord = (trackpoints[-1].longitude, trackpoints[-1].latitude)
        
        d = point_line_distance(coord, [startcoord, endcoord])
        if d > dmax:
            index = i
            dmax = d
        
    if dmax > epsilon:
        results = (
            rdp_spherical(trackpoints[:index+1],epsilon)[:-1]
            + rdp_spherical(trackpoints[index:],epsilon)
        )
    else:
        results = [trackpoints[0], trackpoints[-1]]
    
    return results


def point_line_distance(point, line):
    """Distance between a point and great circle arc on a sphere."""
    start, end = line
    if start == end:
        dist = great_circle_distance(point, start, r=1)/np.pi*180
    else:
        dist = cross_track_distance(point, line, r=1)
        dist = abs(dist/np.pi*180)
    return dist


def great_circle_distance(point1, point2, r=EARTH_RADIUS):
    deg_to_rad = lambda x:x*np.pi/180
    lon1, lat1, lon2, lat2 = map(deg_to_rad,[*point1, *point2])
    delta_lon = abs(lon1 - lon2)
    numerator = np.sqrt(
        (np.cos(lat2) * np.sin(delta_lon))**2 + (
            np.cos(lat1) * np.sin(lat2)
            - np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon)
        )**2
    )
    denominator = (
        np.sin(lat1) * np.sin(lat2)
        + np.cos(lat1) * np.cos(lat2) * np.cos(delta_lon)
    )
    delta_sigma = np.arctan2(numerator,denominator)
    return (r * delta_sigma)


def cross_track_distance(point, line, r=EARTH_RADIUS):
    p1, p2 = line
    p3 = point
    delta13 = great_circle_distance(p1, p3, r=1)
    theta13 = bearing(p1, p3)*np.pi/180
    theta12 = bearing(p1, p2)*np.pi/180

    d_xt = r * (np.arcsin(np.sin(delta13) * np.sin(theta13-theta12)))
    return d_xt


def bearing(point1, point2):
    deg_to_rad = lambda x:x*np.pi/180
    lon1, lat1, lon2, lat2 = map(deg_to_rad,[*point1, *point2])
    delta_lon = lon2 - lon1
    theta = np.arctan2(
        np.sin(delta_lon) * np.cos(lat2),
        (
            np.cos(lat1) * np.sin(lat2)
            - np.sin(lat1) * np.cos(lat2) * np.cos(delta_lon)
        )
    )/np.pi*180
    theta = (theta + 360) % 360
    return theta




if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simplify GPX")
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to simplify",
    )
    # add epsilon
    parser.add_argument('--epsilon', '-e',
        dest='epsilon',
        default=DEFAULT_EPSILON,
        help="Maximum distance from the line",
    )
    args = parser.parse_args()
    main(args)