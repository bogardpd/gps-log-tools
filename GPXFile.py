"""
Represents an instance of a GPX file's data.
"""

import gpxpy
from datetime import timezone

class GPXFile:

    SUFFIX = "gpx"
    TIME_FORMAT = "%Y-%m-%dT%H-%M-%SZ"

    def __init__(self, input_gpx_file) -> None:
        with open(input_gpx_file, 'r') as f:
            self.gpx = gpxpy.parse(f)

    def timestamp_filename(self):
        """Returns a filename from the time of the first waypoint."""
        first_point_time = min([
            segment.points[0].time.astimezone(timezone.utc)
            for track in self.gpx.tracks
            for segment in track.segments
        ]).strftime(GPXFile.TIME_FORMAT)
        return f"{first_point_time}.{GPXFile.SUFFIX}"