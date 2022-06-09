"""
Represents an instance of a GPX file's data.
"""

import profile
import gpxpy
import json
from datetime import timezone
from dateutil.parser import isoparse

class GPXFile:

    ISO_8601_BASIC = "%Y%m%dT%H%M%SZ"
    SUFFIX = "gpx"
    CONFIG_FILE = "config.json"
    IGNORE_FILE = "ignore.json"

    def __init__(self, input_gpx_file) -> None:
        with open(input_gpx_file, 'r') as f:
            self.gpx = gpxpy.parse(f)
        with open(Path(__file__).parent / GPXFile.CONFIG_FILE, 'r') as f:
            self.__config = json.load(f)
        self.start_time = self.__get_start_time()
        self.timestamp_filename = self.__get_timestamp_filename()
        self.creator = self.gpx.creator
        self.profile = self.__get_profile()
        self.__processed_tracks = None
        self.__load_ignored()

    def __repr__(self) -> str:
        params = ",".join("=".join([k,v]) for k,v in {
            'start_time': self.start_time.isoformat(),
            'profile': self.profile,
        }.items())
        return f"GPXFile({params})"

    def __get_profile(self):
        if "Bad Elf" in self.gpx.creator:
            return "Bad Elf"
        elif "DriveSmart" in self.gpx.creator:
            return "Garmin"
        elif "myTracks" in self.gpx.creator:
            return "myTracks"
        else:
            return "_default"

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
        """Attempts to clean up GPX tracks."""
        profile_config = self.__config['profiles'][self.profile]
        print(profile_config)
        self.__processed_tracks = []
        for trk in self.gpx.tracks:
            if GPXFile.trk_start(trk) in self.ignored_trk:
                continue
            if profile_config['merge_segments']['enabled']:
                print("TODO: Merge Segments")
            for trkseg in trk.segments:
                if GPXFile.trkseg_start(trkseg) in self.ignored_trkseg:
                    continue
                if profile_config['trim']['enabled']:
                    print("TODO: Trim")
                if profile_config['simplify']['enabled']:
                    print("TODO: Simplify")
                self.__processed_tracks.append(Track(trkseg, self.profile))

    def get_processed_tracks(self):
        """Returns list of processed Tracks."""
        if self.__processed_tracks is None:
            self.__process_tracks()
        return self.__processed_tracks
    
    def trk_start(trk):
        """Gets the time of the first point of a GPX trk."""
        return trk.segments[0].points[0].time.astimezone(timezone.utc)

    def trkseg_start(trkseg):
        """Gets the time of the first point of a GPX trkseg."""
        return trkseg.points[0].time.astimezone(timezone.utc)


class Track:
    """A collection of GPS trackpoints forming a line."""
    SPEED_TAGS = {
        'Garmin': [
            '{http://www.garmin.com/xmlschemas/TrackPointExtension/v2}speed',
        ],
        'myTracks': [
            '{http://mytracks.stichling.info/myTracksGPX/1/0}speed',
        ],
        'Bad Elf': [
            '{http://bad-elf.com/xmlschemas/GpxExtensionsV1}speed',
            '{http://bad-elf.com/xmlschemas}speed',
        ],
    }

    def __init__(self, trkseg, profile) -> None:
        """Converts a gpxpy trkseg into a common Track object."""
        self.profile = profile
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
        if self.profile == 'Garmin':
            speed = extensions[0].find(Track.SPEED_TAGS['Garmin'][0])
        elif self.profile == 'myTracks':
            speed = next((
                e for e in extensions
                if e.tag == Track.SPEED_TAGS['myTracks'][0]
            ), None)
        elif self.profile == 'Bad Elf':
            speed = next((
                e for e in extensions
                if e.tag in Track.SPEED_TAGS['Bad Elf']
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
        'bad_elf': sample_loc/"bad_elf.gpx",
        'mytracks': sample_loc/"mytracks.gpx",
        'garmin': sample_loc/"garmin-50LMTHD.gpx",
    }
    gf = GPXFile(sample['bad_elf'])
    # gf = GPXFile(sample['garmin'])
    # gf = GPXFile(sample['mytracks'])
    pprint(gf)
    pprint(gf.get_processed_tracks())
    # pprint(gf.tracks[0].points[0:5])
    # pprint(gf.ignored_trk)
    # pprint(gf.ignored_trkseg)