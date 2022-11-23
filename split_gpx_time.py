"""
Splits a GPX file's track segments into multiple segments where the time
gap between points exceeds a set threshold.
"""

import argparse
import colorama
import gpxpy
from tabulate import tabulate
from pathlib import Path

DEFAULT_THRESHOLD_S = 600
TIME_FORMAT = "%Y-%m-%d %H:%MZ"
colorama.init(autoreset=True)

def main(args):
    print(
        colorama.Style.BRIGHT
        + "Splitting "
        + colorama.Fore.CYAN + args.gpx_file + colorama.Fore.RESET
        + f" with {args.threshold} second threshold."
    )

    # Open and parse GPX.
    input_path = Path(args.gpx_file)
    with open(input_path, 'r') as f:
        gpx = gpxpy.parse(f)

    # Split GPX.
    gpx_split = split_gpx(gpx, args.threshold)

    # Write to new GPX file.
    output_path = (
        input_path.parent / f"{input_path.stem}_split{input_path.suffix}"
    )
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(gpx_split.to_xml())
    print(f"Saved split GPX to {output_path}.")


def split_gpx(gpx, threshold):
    """Splits all tracks in a GPX file."""
    for tn, track in enumerate(gpx.tracks):
        print(f"Processing track {tn+1}/{len(gpx.tracks)}: `{track.name}`.")
        track.segments = trk_split_trksegs(track.segments, threshold)
    return gpx


def trk_split_trksegs(segments, threshold):
    """Splits GPX trksegs with time gaps at or above threshold."""
    updated_trksegs = []
    for sn, segment in enumerate(segments):
        print(f"  Splitting segment {sn+1}/{len(segments)}.")
        
        # Create a list of point ids just after a large gap.
        gap_enum = enumerate(zip(segment.points[:-1],segment.points[1:]))
        gaps = {
            (pn + 1): (next_p.time - cur_p.time)
            for pn, (cur_p, next_p) in gap_enum
            if (next_p.time - cur_p.time).total_seconds() >= threshold
        }

        if len(gaps) == 0:
            updated_trksegs.append(segment)
            print("    No large gaps found.")
        else:
            starts = [0,*gaps.keys()]
            ends = [*gaps.keys(),len(segment.points)+1]
            split_trksegs = []
            for s,e in zip(starts, ends):
                split_trkseg = gpxpy.gpx.GPXTrackSegment()
                split_trkseg.points = segment.points[s:e]
                split_trksegs.append(split_trkseg)
            table = []
            for stsn, sts in enumerate(split_trksegs):
                start = sts.points[0].time.strftime(TIME_FORMAT)
                end = sts.points[-1].time.strftime(TIME_FORMAT)
                duration = (sts.points[-1].time - sts.points[0].time).seconds
                drive = duration_str(duration, style=colorama.Fore.GREEN)
                if stsn < (len(split_trksegs) - 1):
                    gap = duration_str(
                        list(gaps.values())[stsn].seconds,
                        style=colorama.Fore.RED,
                    )
                else:
                    gap = None
                table.append([stsn+1, start, drive, end, gap])
            print(tabulate(table,
                headers=['Split', 'Start', 'Drive', 'End', 'Break'],
                stralign='right',
            ))
            updated_trksegs.extend(split_trksegs)
    return updated_trksegs

def duration_str(seconds, style=None):
    h, remainder = divmod(seconds, 3600)
    m, remainder = divmod(remainder, 60)
    dur_str = f"{h}h:{m:02}m"
    if style is not None:
        return style + dur_str + colorama.Style.RESET_ALL
    else:
        return dur_str


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simplify GPX")
    parser.add_argument(
        dest='gpx_file',
        help="GPX file to simplify",
    )
    parser.add_argument('--threshold', '-t',
        dest='threshold',
        default=DEFAULT_THRESHOLD_S,
        help="Minimum time gap (seconds) between points to cause split",
    )
    args = parser.parse_args()
    main(args)