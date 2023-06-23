"""Class for working with driving tracks."""

from datetime import timezone
from pathlib import Path
from pykml.factory import KML_ElementMaker as KML
from shapely import multilinestrings
import tomli

with open(Path(__file__).parent / "config.toml", 'rb') as f:
    CONFIG = tomli.load(f)

EXT_DATA_ATTRIBUTES = {
    'creator':       "Creator",
    'role':          "Role",
    'vehicle_owner': "Vehicle Owner",
}

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

    def get_kml_placemark(self):
        """Returns a KML Placemark for the track."""
        # Build name and description.
        pm_name = self.timestamp.strftime(CONFIG['timestamps']['kml_name'])
        if self.is_new:
            pm_name += " (new)"
        pm_desc = (
            KML.description(self.description) if self.description
            else None
        )

        # Build geometry.
        coord_str = " ".join(
            ",".join(
                str(t) for t in coord[0:2] # Remove altitude if present
            ) for coord in self.coords
        )
        
        # Build ExtendedData.
        ext_data_elements = [
            KML.Data(
                KML.displayName(display_name),
                KML.value(getattr(self, attr_name)),
                name=attr_name,
            )
            for attr_name, display_name in EXT_DATA_ATTRIBUTES.items()
            if getattr(self, attr_name)
        ]
        
        # Create Placemark.
        pm = KML.Placemark(
            KML.name(pm_name),
            pm_desc,
            KML.ExtendedData(*ext_data_elements),
            KML.TimeStamp(
                KML.when(self.timestamp.isoformat())
            ),
            KML.styleUrl("#1"),
            KML.altitudeMode("clampToGround"),
            KML.tessellate(1),
            KML.LineString(
                KML.coordinates(coord_str),
            ),
        )
        return pm