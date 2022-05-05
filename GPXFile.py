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

    def __repr__(self) -> str:
        return f"GPXFile ({self.first_point_time().isoformat()})"

    def first_point_time(self):
        """Gets the UTC time of the first waypoint."""
        return min([
            segment.points[0].time.astimezone(timezone.utc)
            for track in self.gpx.tracks
            for segment in track.segments
        ])

    def timestamp_filename(self):
        """Gets a filename from the time of the first waypoint."""
        filename = self.first_point_time().strftime(GPXFile.TIME_FORMAT)
        return f"{filename}.{GPXFile.SUFFIX}"
