"""Classes for working with GPX files."""

import gpxpy
from pathlib import Path

from gpx_utilities import gpx_profile


class GPXFile():
    """A generic GPX file."""
    def __init__(self, gpx) -> None:
        self.unmodified_gpx = gpx
        self.gpx = gpx
    
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
        return classes[profile](gpx)


class BadElfGPXFile(GPXFile):
    """A GPX file created by a Bad Elf GPS device."""
    def __init__(self, gpx) -> None:
        super().__init__(gpx)


class GarminGPXFile(GPXFile):
    """A GPX file created by a Garmin DriveSmart automotive GPS."""
    def __init__(self, gpx) -> None:
        super().__init__(gpx)


class MyTracksGPXFile(GPXFile):
    """A GPX file created by the myTracks iOS app."""
    def __init__(self, gpx) -> None:
        super().__init__(gpx)


if __name__ == "__main__":
    bad_elf = Path(
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/20221118T222956Z.gpx"
    ).expanduser()
    garmin = Path(
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/garmin/20220616T2124Z_55LM.gpx"
    ).expanduser()
    mytracks = Path(
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221117T140648Z.gpx"
    ).expanduser()
    print(GPXFile.new(bad_elf))
    print(GPXFile.new(garmin))
    print(GPXFile.new(mytracks))