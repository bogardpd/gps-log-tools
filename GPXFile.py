"""Classes for working with GPX files."""

from datetime import timezone
from dateutil.parser import parse
import gpxpy
from pathlib import Path
import tomli

from gpx_utilities import gpx_profile
from update_kml import DrivingTrack

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

class GPXFile():
    """A generic GPX file."""
    def __init__(self, gpx_path, gpx=None) -> None:
        if gpx is None:
            with open(gpx_path, 'r') as f:
                gpx = gpxpy.parse(f)
        self.gpx_path = gpx_path
        self.gpx = gpx
        self.ignore = CONFIG['import']['ignore']
        self.is_processed = False
        self.driving_tracks = []
    
    @staticmethod
    def new(gpx_path):
        """Parses a GPX file and returns a GPXFile instance.
        
        If appropriate, returns a child class of GPXFile instead.
        """
        with open(gpx_path, 'r') as f:
            gpx = gpxpy.parse(f)
        profile = gpx_profile(gpx.creator)
        classes = {
            'bad_elf':  BadElfGPXFile,
            'garmin':   GarminGPXFile,
            'mytracks': MyTracksGPXFile,
            '_default': GPXFile,
        }
        return classes[profile](gpx_path, gpx)

    def process(self):
        """Processes GPX file for insertion into the driving log."""
        print(f"Processing \"{self.gpx_path}\"...")
        if self.is_processed:
            print("This file has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Filter out ignored track segments.
            trk.segments = self.__remove_ignored_trksegs(trk.segments)

            for trkseg_n, trkseg in enumerate(trk.segments):
                # Get timestamp before any trimming or simplification.
                timestamp = self.__get_trkseg_timestamp(trk, trkseg)

                # Append processed trkseg to driving tracks list.
                self.__append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True

    def __append_driving_track(self, trk, trkseg, timestamp):
        """Appends a trkseg as a new DrivingTrack."""
        coords = list(
            (p.longitude, p.latitude) for p in trkseg.points
        )
    
        if len(coords) >= CONFIG['import']['min_points']:
            new_track = DrivingTrack(timestamp)
            new_track.coords = coords
            new_track.description = trk.description
            new_track.creator = self.gpx.creator
            new_track.is_new = True

        self.driving_tracks.append(new_track)
    
    def __get_trkseg_timestamp(self, trk, trkseg):
        """Gets the time of the first trkpt of a trkseg."""
        try:
            return trkseg.points[0].time.astimezone(timezone.utc)
        except AttributeError:
            return parse(trk.name).astimezone(timezone.utc)
    
    def __remove_ignored_trksegs(self, trksegs):
        """Removes segments whose first point matches ignore list."""
        try:
            return [
                trkseg for trkseg in trksegs
                if trkseg.points[0].time not in self.ignore['trkseg']
            ]
        except AttributeError:
            return trksegs


class BadElfGPXFile(GPXFile):
    """A GPX file created by a Bad Elf GPS device."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)


class GarminGPXFile(GPXFile):
    """A GPX file created by a Garmin DriveSmart automotive GPS."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)


class MyTracksGPXFile(GPXFile):
    """A GPX file created by the myTracks iOS app."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)


if __name__ == "__main__":
    sample_paths = [
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/20221118T222956Z.gpx",
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/garmin/20220616T2124Z_55LM.gpx",
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221117T140648Z.gpx",
    ]
    for path in sample_paths:
        gpx_file = GPXFile.new(Path(path).expanduser())
        print(gpx_file)
        gpx_file.process()