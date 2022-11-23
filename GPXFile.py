"""Classes for working with GPX files."""

from datetime import timedelta, timezone
from dateutil.parser import parse
import gpxpy
from pathlib import Path
import tomli

from filter_speed import filter_speed_trk
from gpx_utilities import gpx_profile
from simplify_gpx import simplify_trkseg
from split_gpx_time import split_trksegs
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
        self.profile = '_default'
        self.import_config = CONFIG['import']['gpx'][self.profile]
    
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
        """Processes GPX file into a list of DrivingTracks."""
        print(f"Processing \"{self.gpx_path}\"...")
        if self.is_processed:
            print("This fi_get_trkseg_timestample has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Filter out ignored trksegs.
            trk = self._remove_ignored_trksegs(trk)

            for ts_i, trkseg in enumerate(trk.segments):
                # Get timestamp before any trkseg processing.
                timestamp = self._get_trkseg_timestamp(trk, trkseg)

                # Append processed trkseg to driving tracks list.
                self._append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True

    def _append_driving_track(self, trk, trkseg, timestamp):
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
    
    def _get_filter_speed_config(self):
        filter_speed_config = {
            v: self.import_config['filter_speed'][v]
            for v in ['min_speed_m_s','rolling_window','method']
        }
        filter_speed_config['profile'] = self.profile
        print(filter_speed_config)
        return filter_speed_config

    def _get_trkseg_timestamp(self, trk, trkseg):
        """Gets the time of the first trkpt of a trkseg."""
        try:
            return trkseg.points[0].time.astimezone(timezone.utc)
        except AttributeError:
            return parse(trk.name).astimezone(timezone.utc)
    
    def _merge_small_gap_trksegs(self, trksegs, index=0):
        """Recursively merges segments with small time gaps."""
        print("Merging segments...")
        trksegs = trksegs.copy()
        if index + 1 == len(trksegs):
            return trksegs
        a,b = trksegs[index:index+2]
        try:
            timediff = b.points[0].time - a.points[-1].time
            max_seconds = self.import_config['merge_segments']['max_seconds']
            if timediff <= timedelta(seconds=max_seconds):
                a.points.extend(b.points)
                del trksegs[index+1]
                return self._merge_small_gap_trksegs(trksegs, index=index)
            else:
                return self._merge_small_gap_trksegs(trksegs, index=index+1)
        except AttributeError:
            return trksegs

    def _remove_ignored_trksegs(self, trk):
        """Removes segments whose first point matches ignore list."""
        try:
            trk.segments = [
                trkseg for trkseg in trk.segments
                if trkseg.points[0].time not in self.ignore['trkseg']
            ]
            return trk
        except AttributeError:
            return trk


class BadElfGPXFile(GPXFile):
    """A GPX file created by a Bad Elf GPS device."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)
        self.profile = 'bad_elf'
        self.import_config = CONFIG['import']['gpx'][self.profile]

    def process(self):
        """Processes GPX file into a list of DrivingTracks."""
        print(f"Processing \"{self.gpx_path}\" as Bad Elf GPX...")
        if self.is_processed:
            print("This file has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Filter out ignored trksegs.
            trk = self._remove_ignored_trksegs(trk)

            # Split trksegs with large time gaps into multiple trksegs.
            trk.segments = split_trksegs(
                trk.segments,
                self.import_config['split_trksegs']['threshold']
            )

            for ts_i, trkseg in enumerate(trk.segments):
                # Get timestamp before any trkseg processing.
                timestamp = self._get_trkseg_timestamp(trk, trkseg)

                # Simplify trkseg.
                trkseg = simplify_trkseg(
                    trkseg,
                    self.import_config['simplify']['epsilon'],
                    ts_i,
                    len(trk.segments),
                )
                
                # Append processed trkseg to driving tracks list.
                self._append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True


class GarminGPXFile(GPXFile):
    """A GPX file created by a Garmin DriveSmart automotive GPS."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)
        self.profile = 'garmin'
        self.import_config = CONFIG['import']['gpx'][self.profile]

    def process(self):
        """Processes GPX file into a list of DrivingTracks."""
        print(f"Processing \"{self.gpx_path}\" as Garmin GPX...")
        if self.is_processed:
            print("This file has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Filter out ignored trksegs.
            trk = self._remove_ignored_trksegs(trk)

            # Merge track segments with small time gaps between them.
            trk.segments = self._merge_small_gap_trksegs(trk.segments)

            for ts_i, trkseg in enumerate(trk.segments):
                # Get timestamp before any trkseg processing.
                timestamp = self._get_trkseg_timestamp(trk, trkseg)

                # Append processed trkseg to driving tracks list.
                self._append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True


class MyTracksGPXFile(GPXFile):
    """A GPX file created by the myTracks iOS app."""
    def __init__(self, gpx_path, gpx=None) -> None:
        super().__init__(gpx_path, gpx)
        self.profile = 'mytracks'
        self.import_config = CONFIG['import']['gpx'][self.profile]

    def process(self):
        """Processes GPX file into a list of DrivingTracks."""
        print(f"Processing \"{self.gpx_path}\" as myTracks GPX...")
        if self.is_processed:
            print("This file has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Filter out ignored trksegs.
            trk = self._remove_ignored_trksegs(trk)

            # Filter out low speed points.
            trk = filter_speed_trk(trk, **self._get_filter_speed_config())

            # Split trksegs with large time gaps into multiple trksegs.
            trk.segments = split_trksegs(
                trk.segments,
                self.import_config['split_trksegs']['threshold']
            )

            for ts_i, trkseg in enumerate(trk.segments):
                # Get timestamp before any trkseg processing.
                timestamp = self._get_trkseg_timestamp(trk, trkseg)

                # Simplify trkseg.
                trkseg = simplify_trkseg(
                    trkseg,
                    self.import_config['simplify']['epsilon'],
                    ts_i,
                    len(trk.segments),
                )
                
                # Append processed trkseg to driving tracks list.
                self._append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True


if __name__ == "__main__":
    sample_paths = [
        # "~/OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/20221118T222956Z.gpx",
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/garmin/20220616T2124Z_55LM.gpx",
        # "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221117T140648Z.gpx",
    ]
    for path in sample_paths:
        gpx_file = GPXFile.new(Path(path).expanduser())
        print(gpx_file)
        gpx_file.process()
        print(gpx_file.driving_tracks)