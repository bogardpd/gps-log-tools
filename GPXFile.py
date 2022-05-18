"""
Represents an instance of a GPX file's data.
"""

import gpxpy
import json
from datetime import timezone
from dateutil.parser import isoparse

class GPXFile:

    ISO_8601_BASIC = "%Y%m%dT%H%M%SZ"
    SUFFIX = "gpx"
    IGNORE_FILE = "ignore.json"

    def __init__(self, input_gpx_file) -> None:
        with open(input_gpx_file, 'r') as f:
            self.gpx = gpxpy.parse(f)
        self.start_time = self.__get_start_time()
        self.timestamp_filename = self.__get_timestamp_filename()
        self.creator = self.__get_creator()
        self.__load_ignored()
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

    def __load_ignored(self):
        try:
            with open(Path(__file__).parent / GPXFile.IGNORE_FILE, 'r') as f:
                ignored = json.load(f)
            self.ignored_trk = [isoparse(dt) for dt in ignored['trk']]
            self.ignored_trkseg = [isoparse(dt) for dt in ignored['trkseg']]
        except FileNotFoundError:
            return {'trk': [], 'trkseg': []}

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
        """Creates a list of Tracks."""
        self.tracks = []
        for trk in self.gpx.tracks:
            if GPXFile.trk_start(trk) in self.ignored_trk:
                continue
            for trkseg in trk.segments:
                if GPXFile.trkseg_start(trkseg) in self.ignored_trkseg:
                    continue
                self.tracks.append(Track(trkseg, self.creator))

    def trk_start(trk):
        """Gets the time of the first point of a GPX trk."""
        return trk.segments[0].points[0].time.astimezone(timezone.utc)

    def trkseg_start(trkseg):
        """Gets the time of the first point of a GPX trkseg."""
        return trkseg.points[0].time.astimezone(timezone.utc)


class Track:
    """A collection of GPS trackpoints forming a line."""
    SPEED_TAGS = {
        'garmin': [
            '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}speed',
        ],
        'mytracks': [
            '{http://mytracks.stichling.info/myTracksGPX/1/0}speed',
        ],
        'bad_elf': [
            '{http://bad-elf.com/xmlschemas/GpxExtensionsV1}speed',
            '{http://bad-elf.com/xmlschemas}speed',
        ],
    }

    def __init__(self, trkseg, creator) -> None:
        """Converts a gpxpy trkseg into a common Track object."""
        self.creator = creator
        self.start_time = trkseg.points[0].time.astimezone(timezone.utc)
        self.points = [self.__parse_gpx_trkpt(p) for p in trkseg.points]

    def __repr__(self) -> str:
        return f"Track(start_time={self.start_time.isoformat()})"

    def __parse_gpx_trkpt(self, trkpt):
        """Converts GPX trkpt into dict of point attributes."""

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
        if self.creator == 'garmin':
            speed = extensions[0].find(Track.SPEED_TAGS['garmin'][0])
        elif self.creator == 'mytracks':
            speed = next((
                e for e in extensions
                if e.tag == Track.SPEED_TAGS['mytracks'][0]
            ), None)
        elif self.creator == 'bad_elf':
            speed = next((
                e for e in extensions
                if e.tag in Track.SPEED_TAGS['bad_elf']
            ), None)
        else:
            return None
        
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
    # gf = GPXFile(sample['garmin'])
    gf = GPXFile(sample['mytracks'])
    pprint(gf)
    # pprint(gf.tracks[0].points[0:5])
    # pprint(gf.ignored_trk)
    # pprint(gf.ignored_trkseg)