"""Classes for working with GPX files."""

import gpxpy
import pandas as pd
import sqlite3
import tomli

from datetime import timedelta, timezone
from dateutil.parser import parse
from pathlib import Path

from DrivingTrack import DrivingTrack
from filter_speed import trk_filter_speed
from filter_timelog import (
    get_timelog_segments,
    timelog_overlaps_range,
    trk_filter_timelog
)
from gpx_utilities import gpx_profile
from remove_outliers import trk_remove_outliers
from simplify_gpx import trkseg_simplify
from split_gpx_time import trk_split_trksegs

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

class GPXFile():
    """A generic GPX file."""
    def __init__(self, gpx_path, gpx=None) -> None:
        self.GPKG_FILE = (
            Path(CONFIG['folders']['auto_root']).expanduser()
            / CONFIG['files']['canonical_gpkg']
        )
        if gpx is None:
            with open(gpx_path, 'r') as f:
                gpx = gpxpy.parse(f)
        self.gpx_path = gpx_path
        self.gpx = gpx
        self.ignore = CONFIG['import']['ignore']
        self.is_processed = False
        self.driving_tracks = []
        self.existing_trk_timestamps = self._existing_trk_timestamps()
        self.profile = '_default'
        self.import_config = CONFIG['import']['gpx'][self.profile]
    
    @staticmethod
    def load(gpx_path):
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
            print("This file has already been processed. Skipping processing.")
            return False
        
        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Check if track is already in log.
            if self._trk_in_log(trk):
                self._print_track_already_in_log(trk)
                continue

            # Get timestamp before any trkseg processing.
            timestamp = self._trk_get_timestamp(trk)

            for trkseg in trk.segments:
                # Append processed trkseg to driving tracks list.
                self._trkseg_append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True

    def _existing_trk_timestamps(self):
        """Gets a list of existing source track timestamps."""
        gpkg_file = (
            Path(CONFIG['folders']['auto_root']).expanduser()
            / CONFIG['files']['canonical_gpkg']
        )
        con = sqlite3.connect(gpkg_file)
        query = """
            SELECT DISTINCT source_track_timestamp
            FROM driving_tracks
        """
        df = pd.read_sql(query, con)
        con.close()
        return [parse(d) for d in df['source_track_timestamp'].to_list()]

    def _get_filter_speed_config(self):
        filter_speed_config = {
            v: self.import_config['filter_speed'][v]
            for v in ['min_speed_m_s','rolling_window','method']
        }
        filter_speed_config['profile'] = self.profile
        return filter_speed_config
    
    def _print_track_already_in_log(self, trk):
        print(
            f"\"{trk.name}\" is already in the driving log. "
            "Skipping this track."
        )        
    
    def _trk_get_time_range(self, trk):
        """Returns a tuple with the first and last time of a trk."""
        min_time = min([
            trkseg.points[0].time.astimezone(timezone.utc)
            for trkseg in trk.segments
        ])
        max_time = max([
            trkseg.points[-1].time.astimezone(timezone.utc)
            for trkseg in trk.segments
        ])
        return (min_time, max_time)
    
    def _trk_get_timestamp(self, trk):
        """Gets the time of the earliest point of a track."""
        return self._trk_get_time_range(trk)[0]

    def _trk_in_log(self, trk):
        """Returns true if track is in track log."""
        return (self._trk_get_timestamp(trk) in self.existing_trk_timestamps)
    
    def _trk_merge_trksegs(self, trksegs, index=0):
        """Recursively merges segments with small time gaps."""
        print("Merging segments...")
        if index == 0 and len(trksegs) == 0:
            return trksegs
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
                return self._trk_merge_trksegs(trksegs, index=index)
            else:
                return self._trk_merge_trksegs(trksegs, index=index+1)
        except AttributeError:
            return trksegs

    def _trk_remove_ignored(self, trk):
        """Removes trks and trksegs that are on ignore lists."""
        
        # If trk is ignored, remove all trksegs.
        trk_timestamp = self._trk_get_time_range(trk)[0]
        if trk_timestamp in self.ignore['trk']:
            trk.segments = []
            return trk

        # Remove ignored trksegs.
        try:
            trk.segments = [
                trkseg for trkseg in trk.segments
                if trkseg.points[0].time not in self.ignore['trkseg']
            ]
            return trk
        except AttributeError:
            return trk
    
    def _trkseg_append_driving_track(self, trk, trkseg, timestamp):
        """Appends a trkseg as a new DrivingTrack."""
        if len(trkseg.points) >= CONFIG['import']['min_points']:
            new_track = DrivingTrack(timestamp.astimezone(timezone.utc))
            new_track.load_gpx_trkseg(trkseg)
            new_track.description = trk.description
            new_track.creator = self.gpx.creator
            self.driving_tracks.append(new_track)


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
        
        root = Path(CONFIG['folders']['auto_root']).expanduser()
        log_csv = root / CONFIG['files']['bad_elf_outliers_log']

        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Check if track is already in log.
            if self._trk_in_log(trk):
                self._print_track_already_in_log(trk)
                continue

            # Get timestamp before any trkseg processing.
            timestamp = self._trk_get_timestamp(trk)

            # Remove outlier points.
            trk = trk_remove_outliers(
                trk,
                str_gpx_filename=Path(self.gpx_path).parts[-1],
                log_csv=log_csv,
            )

            # Split trksegs with large time gaps into multiple trksegs.
            trk.segments = trk_split_trksegs(
                trk.segments,
                self.import_config['split_trksegs']['threshold']
            )

            for ts_i, trkseg in enumerate(trk.segments):

                # Simplify trkseg.
                trkseg = trkseg_simplify(
                    trkseg,
                    self.import_config['simplify']['epsilon'],
                    ts_i,
                    len(trk.segments),
                )
                
                # Append processed trkseg to driving tracks list.
                self._trkseg_append_driving_track(trk, trkseg, timestamp)

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

            # Check if track is already in log.
            if self._trk_in_log(trk):
                self._print_track_already_in_log(trk)
                continue

            # Get timestamp before any trkseg processing.
            timestamp = self._trk_get_timestamp(trk)

            # Filter out ignored trks and trksegs.
            trk = self._trk_remove_ignored(trk)

            # Merge track segments with small time gaps between them.
            trk.segments = self._trk_merge_trksegs(trk.segments)

            for ts_i, trkseg in enumerate(trk.segments):
                # Append processed trkseg to driving tracks list.
                self._trkseg_append_driving_track(trk, trkseg, timestamp)

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
        
        # Parse timelog.
        timesegs = get_timelog_segments()

        for trk in self.gpx.tracks:
            print(f"Converting track \"{trk.name}\"...")

            # Check if track is already in log.
            if self._trk_in_log(trk):
                self._print_track_already_in_log(trk)
                continue

            # Get timestamp before any trkseg processing.
            timestamp = self._trk_get_timestamp(trk)

            trk_time_range = self._trk_get_time_range(trk)
            if timelog_overlaps_range(timesegs, trk_time_range):
                # Filter using timelog.
                trk = trk_filter_timelog(
                    trk, timesegs=timesegs, raise_exception=False
                )

            else:
                # Filter using speed and split trksegs.
                print("Track does not overlap timelog segments.")

                # Filter out low speed points.
                trk = trk_filter_speed(trk, **self._get_filter_speed_config())

                # Split trksegs with large time gaps into multiple trksegs.
                trk.segments = trk_split_trksegs(
                    trk.segments,
                    self.import_config['split_trksegs']['threshold']
                )

            for ts_i, trkseg in enumerate(trk.segments):
                # Simplify trkseg.
                trkseg = trkseg_simplify(
                    trkseg,
                    self.import_config['simplify']['epsilon'],
                    ts_i,
                    len(trk.segments),
                )
                
                # Append processed trkseg to driving tracks list.
                self._trkseg_append_driving_track(trk, trkseg, timestamp)

        self.is_processed = True


if __name__ == "__main__":
    sample_paths = [
        # "~/OneDrive/Projects/Driving-Logs/Raw-Data/bad_elf/20221118T222956Z.gpx",
        # "~/OneDrive/Projects/Driving-Logs/Raw-Data/garmin/20220404T0242Z_50LMT.gpx",
        # "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221116T124435Z.gpx",
        "~/OneDrive/Projects/Driving-Logs/Raw-Data/mytracks/20221117T140648Z.gpx",
    ]
    for path in sample_paths:
        gpx_file = GPXFile.load(Path(path).expanduser())
        print(gpx_file)
        gpx_file.process()
        print(gpx_file.driving_tracks, len(gpx_file.driving_tracks))