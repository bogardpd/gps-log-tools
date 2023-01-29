import argparse
import gpxpy
import colorama
import csv
from datetime import datetime
from pathlib import Path

colorama.init(autoreset=True)

# Maximum consecutive points forward or back to look for time travel.
MAX_TIME_TRAVEL_LEN = 60

def main(args):
    print(f"Removing outliers from {args.gpx_file}.")

    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)
    
    str_gpx_filename = input_path.parts[-1]

    # Remove outliers from GPX.
    gpx_filtered = gpx_remove_outliers(gpx, str_gpx_filename, args.log_csv)

    # Write to new GPX file.
    output_path = (
        input_path.parent
        / f"{input_path.stem}_outliers_removed{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_filtered.to_xml())
    print(f"Saved outlier-free GPX to {output_path}.")

def gpx_remove_outliers(gpx, str_gpx_filename=None, log_csv=None):
    """Removes outliers from a GPX file."""

    for track in gpx.tracks:
        track = trk_remove_outliers(
            track, str_gpx_filename=str_gpx_filename, log_csv=log_csv
        )
    return gpx

def trk_remove_outliers(track, str_gpx_filename=None, log_csv=None):
    """Removes outliers from a GPX track."""

    for segment in track.segments:
        segment = trkseg_remove_time_travel(
            segment, str_gpx_filename=str_gpx_filename, log_csv=log_csv
        )
        segment = trkseg_remove_teleportation(
            segment, str_gpx_filename=str_gpx_filename, log_csv=log_csv
        )

def trkseg_remove_time_travel(segment, str_gpx_filename=None, log_csv=None):
    """Removes time travel outliers from a GPX track segment."""

    # Find points that are earlier than their prior point.
    times = list(p.time for p in segment.points)
    backtime_indexes = list(
        i + 1
        for i, (t1, t2)
        in enumerate(zip(times[:-1],times[1:]))
        if t1 > t2
    )
    
    outliers_time_travel = []
    
    for bti in backtime_indexes:

        # Check if we have backwards time travel.
        if (bti - 1 >= 0):
            # Determine how many outlier points in a row are present.
            try:
                # Find next point with later time than prior good point.
                print("Prior good point", times[bti-1])
                time_travel_count = next(
                    j
                    for j, t in enumerate(times[bti:bti+MAX_TIME_TRAVEL_LEN])
                    if t > times[bti-1]
                )
                time_travel_indexes = list(range(bti,bti+time_travel_count))
                outliers_time_travel.extend(time_travel_indexes)
            except StopIteration:
                pass

        # Check if we have forward time travel.
        if (bti < len(times)):
            # Determine how many outlier points in a row are present.
            try:
                # Find last point with earlier time than current good
                # point.
                print("Current good point", times[bti])
                time_travel_count = next(
                    j
                    for j, t in enumerate(reversed(
                        times[bti-MAX_TIME_TRAVEL_LEN:bti]
                    ))
                    if t < times[bti]
                )
                time_travel_indexes = list(range(bti-time_travel_count,bti))
                outliers_time_travel.extend(time_travel_indexes)
            except StopIteration:
                pass

    if len(outliers_time_travel) > 0:
        # Document time travel outliers.
        for i in outliers_time_travel:
            print(
                colorama.Back.YELLOW
                + colorama.Fore.BLACK
                + f"Time travel: {str_gpx_filename} at {segment.points[i]}"
            )
            if log_csv is not None:
                with open(log_csv, 'a', newline='', encoding='utf-8') as lf:
                    writer = csv.writer(lf)
                    writer.writerow([
                        str_gpx_filename,
                        str(segment.points[i].time),
                        str(segment.points[i].latitude),
                        str(segment.points[i].longitude),
                        "time travel"
                    ])

        # Remove time travel outliers.
        segment.points = list(
            p for i, p in enumerate(segment.points)
            if i not in outliers_time_travel
        )
    

    return segment

def trkseg_remove_teleportation(segment, str_gpx_filename=None, log_csv=None):
    """Removes position teleportation outliers from a GPX track segment."""
    return segment

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Remove outlier waypoints from GPX file"
    )
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to filter",
    )
    parser.add_argument('--log_csv',
        dest='log_csv',
        help="CSV file to log outliers to",
    )
    args = parser.parse_args()
    main(args)