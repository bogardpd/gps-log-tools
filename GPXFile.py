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
    SPEED_TAGS = [
        '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}speed',
        '{http://mytracks.stichling.info/myTracksGPX/1/0}speed',
        '{http://bad-elf.com/xmlschemas/GpxExtensionsV1}speed',
        '{http://bad-elf.com/xmlschemas}speed',
    ]

    def __init__(self, trkseg) -> None:
        """Converts a gpxpy trkseg into a common Track object."""
        self.start_time = trkseg.points[0].time.astimezone(timezone.utc)
        self.points = [self.__parse_gpx_trkpt(p) for p in trkseg.points]

    def __repr__(self) -> str:
        return f"Track(start_time={self.start_time.isoformat()})"

    def __parse_gpx_trkpt(self, trkpt):
        """Converts GPX trkpt into dict of point attributes."""
        # Build dictionary of extensions.
        ext_dict = {e.tag: e.text for e in trkpt.extensions}

        return {
            'time': trkpt.time.astimezone(timezone.utc),
            'latitude': trkpt.latitude,
            'longitude': trkpt.longitude,
            'elevation': trkpt.elevation,
            'speed': self.__get_speed(trkpt.extensions),
            # 'ext': trkpt.extensions,
        }

    def __get_speed(self, extensions):
        """Finds a speed attribute in a trkpt's extensions."""
        for e in extensions:
            # Check if the extension is a speed tag.
            if e.tag in Track.SPEED_TAGS and e.text is not None:
                return float(e.text)
            # Search the extension's tree for a speed tag.
            for s in Track.SPEED_TAGS:
                speed = e.find(s)
                if speed is not None and speed.text is not None:
                    return float(speed.text)
        return None


# Test track:
if __name__ == "__main__":
    from pathlib import Path
    from pprint import pprint
    sample_loc = Path.home()/"OneDrive"/"Projects"/"Maps"/"GPS"/"Auto"/"sample"
    sample = {
        'mytracks': sample_loc/"mytracks.gpx",
        'garmin': sample_loc/"garmin-50LMTHD.gpx",
    }
    gf = GPXFile(sample['garmin'])
    # gf = GPXFile(sample['mytracks'])
    pprint(gf)
    pprint(gf.tracks[0].points[0:5])