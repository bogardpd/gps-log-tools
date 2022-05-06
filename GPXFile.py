"""
Represents an instance of a GPX file's data.
"""

import gpxpy
from datetime import timezone

class GPXFile:

    ISO_8601_BASIC = "%Y%m%dT%H%M%SZ"
    SUFFIX = "gpx"

    def __init__(self, input_gpx_file) -> None:
        with open(input_gpx_file, 'r') as f:
            self.gpx = gpxpy.parse(f)
        self.start_time = self.__get_start_time()
        self.timestamp_filename = self.__get_timestamp_filename()
        self.creator = self.__get_creator()
        self.__process_tracks()

    def __repr__(self) -> str:
        params = ",".join("=".join([k,v]) for k,v in {
            'start_time': self.start_time.isoformat(),
            'creator': self.creator,
        }.items())
        return f"GPXFile({params})"

    def __get_creator(self):
        if "Bad Elf" in self.gpx.creator:
            return 'bad_elf'
        elif "DriveSmart" in self.gpx.creator:
            return 'garmin'
        elif "myTracks" in self.gpx.creator:
            return 'mytracks'
        else:
            return None

    def __get_start_time(self):
        """Gets the UTC time of the first waypoint."""
        return min([
            segment.points[0].time.astimezone(timezone.utc)
            for track in self.gpx.tracks
            for segment in track.segments
        ])

    def __get_timestamp_filename(self):
        """Gets a filename from the time of the first waypoint."""
        filename = self.start_time.strftime(GPXFile.ISO_8601_BASIC)
        return f"{filename}.{GPXFile.SUFFIX}"

    def __process_tracks(self):
        self.tracks = []
        for trk in self.gpx.tracks:
            for trkseg in trk.segments:
                self.tracks.append(Track(trkseg))


class Track:
    """A collection of GPS trackpoints forming a line."""

    def __init__(self, trkseg) -> None:
        """Converts a gpxpy trkseg into a common Track object."""
        self.start_time = trkseg.points[0].time.astimezone(timezone.utc)
        self.points = trkseg.points

    def __repr__(self) -> str:
        return f"Track(start_time={self.start_time.isoformat()})"


# Test track:
if __name__ == "__main__":
    from pathlib import Path
    from pprint import pprint
    sample = Path.home()/"OneDrive"/"Transfer"/"2022-05-04 18_16_05.gpx"
    gf = GPXFile(sample)
    pprint(gf)
    pprint(gf.tracks)