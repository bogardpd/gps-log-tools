"""Class for working with driving tracks."""

from datetime import timezone
from pathlib import Path
from shapely.geometry import MultiLineString
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
        self.geometry = self.__track_geometry()
        self.utc_start = (
            trkseg.points[0].time.astimezone(timezone.utc)
        )
        self.utc_stop =  (
            trkseg.points[-1].time.astimezone(timezone.utc)
        )

    def get_record(self):
        """Returns a record hash for the driving_tracks table."""
        return {
            # If pyogiro is used as the engine in GeoDataFrame.to_file,
            # the fields must be in the same order as the columns in the
            # SQLite database table.
            'geometry': self.geometry,
            'utc_start': self.utc_start,
            'utc_stop': self.utc_stop,
            'source_track_timestamp': self.timestamp,
            'creator': self.creator,
            'role': self.role,
            'vehicle_owner': self.vehicle_owner,
            'comments': self.description,
            'rental_fid': None,
        }
    
    def __track_geometry(self):
        """Returns a Shapely MultiLineString from a list of coordinates."""
        if len(self.coords) < 2:
            return None
        
        # Find indexes of pairs of points that cross the antemeridian.
        crossings = [
            i + 1 for i, (p1, p2)
            in enumerate(zip(self.coords[:-1], self.coords[1:]))
            if (p1[0] < 0 and p2[0] >= 0) or (p1[0] >= 0 and p2[0] < 0)
        ]
        if len(crossings) == 0:
            # Track does not cross the antemeridian.
            return MultiLineString([self.coords])
        
        # Split the track at the antemeridian.
        tracks = []
        starts = [0, *crossings]
        ends = [*crossings, len(self.coords)-1]
        tracks = [self.coords[start:end] for start, end in zip(starts, ends)]
        for i, track in enumerate(tracks):
            if i > 0:
                p1 = track[0]
                p2 = tracks[i-1][-1]
                p_cross = self.__crossing_point(p1, p2)
                if p_cross is not None:
                    track.insert(0, p_cross)
            if i < len(crossings):
                p1 = track[-1]
                p2 = tracks[i+1][0]
                p_cross = self.__crossing_point(p1, p2)
                if p_cross is not None:
                    track.append(p_cross)
        
        # Filter out tracks with only one point.
        tracks = [track for track in tracks if len(track) > 1]
        return MultiLineString(tracks)
    
    def __crossing_point(self, p1, p2):
        """Return the point where a track crosses the antemeridian.
        Returns None if p1 is already on the antemeridian.

        p1 : tuple(float)
            The point on the current track
        p2 : tuple(float)
            The point on the adjacent track.
        """
        p2 = list(p2)
        if -180 < p1[0] < 0:
            lon = -180
            p2[0] = p2[0] - 360
        elif 0 < p1[0] < 180:
            lon = 180
            p2[0] = p2[0] + 360
        else:
            return None
        x_frac = (lon - p1[0]) / (p2[0] - p1[0])
        return tuple([c1 + (x_frac * (c2 - c1)) for c1, c2 in zip(p1, p2)])
