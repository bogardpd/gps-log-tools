import argparse
import gpxpy
import colorama
import csv
from pathlib import Path
from geopy.distance import distance

colorama.init(autoreset=True)

# Maximum consecutive points forward or back to look for time travel.
MAX_TIME_TRAVEL_LEN = 60

# Maximum consecutive points forward or back to look for teleportation.
MAX_TELEPORT_LEN = 60

# Maximum allowable speed of travel between two consecutive points.
SPEED_THRESHOLD = 250.0 # meters per second

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
    print(f"Removing outliers from {track.name}...")
    for segment in track.segments:
        segment = trkseg_remove_time_travel(
            segment, str_gpx_filename=str_gpx_filename, log_csv=log_csv
        )
        segment = trkseg_remove_teleportation(
            segment, str_gpx_filename=str_gpx_filename, log_csv=log_csv
        )

    return track

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
                    for j, t in enumerate(
                        times[bti:max(bti+MAX_TIME_TRAVEL_LEN,len(times))]
                    )
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
    
    # Generate list of points immediately preceding a high speed.
    points_before_speeding = list(
        i
        for i, (p1, p2)
        in enumerate(zip(segment.points[:-1], segment.points[1:]))
        if speed_m_s(p1, p2) >= SPEED_THRESHOLD
    )

    # Determine if each point is the last point of the correct location,
    # or the last point of a teleported location. From this point, look
    # forward and find out how many subsequent points exceed the speed
    # threshold from it. If the count of those points is less than
    # MAX_TELEPORT_LEN, it is likely a teleportation and should be
    # removed.
    outliers_teleportation = []
    for i_pbs in points_before_speeding:
        # Determine how many outlier points in a row are present.
        try:
            # Find next point that's not teleporting.
            teleport_count = next(
                j
                for j in range(
                    1, min(MAX_TELEPORT_LEN, len(segment.points) - i_pbs)
                )
                if speed_m_s(
                    segment.points[i_pbs], segment.points[i_pbs+j]
                ) < SPEED_THRESHOLD
            ) - 1
            teleport_indexes = list(range(i_pbs+1, i_pbs+teleport_count+1))
            outliers_teleportation.extend(teleport_indexes)
        except StopIteration:
            pass

    if len(outliers_teleportation) > 0:
        # Document teleportation outliers.
        for i in outliers_teleportation:
            print(
                colorama.Back.YELLOW
                + colorama.Fore.BLACK
                + f"Teleportation: {str_gpx_filename} at {segment.points[i]}"
            )
            if log_csv is not None:
                with open(log_csv, 'a', newline='', encoding='utf-8') as lf:
                    writer = csv.writer(lf)
                    writer.writerow([
                        str_gpx_filename,
                        str(segment.points[i].time),
                        str(segment.points[i].latitude),
                        str(segment.points[i].longitude),
                        "teleportation"
                    ])

        # Remove time travel outliers.
        segment.points = list(
            p for i, p in enumerate(segment.points)
            if i not in outliers_teleportation
        )
    
    return segment

def speed_m_s(p1, p2):
    """Calculates the speed of travel between two GPX waypoints (m/s)."""
    dist = distance(
        (p1.latitude, p1.longitude), (p2.latitude, p2.longitude)
    ).meters
    timediff = (p2.time - p1.time).total_seconds()
    if timediff == 0:
        print(f"No timediff at {p1.time}.")
        return 0
    return (dist / timediff)


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