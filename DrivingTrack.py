"""Class for working with driving tracks."""

from datetime import timezone
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from shapely import multilinestrings
import tomli

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

class DrivingTrack:
    """An instance of a driving log track."""
    def __init__(self, id_timestamp) -> None:
        self.timestamp = id_timestamp # Starting timestamp is used as id
        self.coords = []
        self.geometry = None
        self.utc_start = None
        self.utc_stop = None
        self.creator = None
        self.role = None
        self.vehicle_owner = None
        self.description = None

    def __repr__(self) -> str:
        return f"DrivingTrack({self.timestamp.isoformat()})"
    
    def load_gpx_trkseg(self, trkseg):
        """Loads data from a GPX trkseg."""
        self.coords = [(p.longitude, p.latitude) for p in trkseg.points]
        if len(self.coords) >= 2:
            self.geometry = multilinestrings([self.coords])
        else:
            self.geometry = None
        self.utc_start = (
            trkseg.points[0].time.astimezone(timezone.utc)
        )
        self.utc_stop =  (
            trkseg.points[-1].time.astimezone(timezone.utc)
        )

    def get_record(self):
        """Returns a record hash for the driving_tracks table."""
        return {
            'geometry': self.geometry,
            'utc_start': self.utc_start,
            'utc_stop': self.utc_stop,
            'creator': self.creator,
            'role': self.role,
            'vehicle_owner': self.vehicle_owner,
            'comments': self.description,
            'source_track_timestamp': self.timestamp,
        }
