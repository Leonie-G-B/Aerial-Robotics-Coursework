
### Utility functions relating to building up a mission (PyMav) plan

import yaml 
import math
from pymavlink import mavutil

import MissionUtils as utils


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################


class MissionPlanner: 
    def __init__(self, home_key: str = 'fenswood'):
        self.home_key = home_key
        self.geo_filename = 'geo_info'
        self.home = self._load_home(location_key=home_key)
        self.connection = utils.connect()
        self.mission = []
        self.seq = 0

        logging.info(f"MissionPlanner initialsied with home: {home_key}")

    
    def _read_yaml(self, filename: str, path: list) -> dict: 
        """"Reads yaml file specified and all data through the path specifed. 
        Where the path follows the levels of heirarchy from highest to lowest."""

        filepath = f"{filename}.yml"
        with open(filepath, 'r') as file:
            data = yaml.safe_load(file)
        
        for variable in path: 
            data = data[variable]

        if data is None: 
            logging.warning(f"Yamml file search did not return any information. File: {filename}. Path details: {path}")

        return data

    def _load_home(self,location_key: str):
        info = self._read_yaml(self.geo_filename, ['locations', location_key])
        return info.copy()

    #### Mission event funcs #####

    def create_takeoff_event(self, target_alt: int = 0, overrides: dict = None):
        """Create MAVLink Mission Planner compatible takeoff event from specified location."""

        loc = self.home.copy()
        if overrides:
            loc.update(overrides)

        event = {
            'seq': self.seq, #number of point in sequence - expected/default to 0.
            'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
            'current': 0,
            'autocontinue': 1, 
            'param1' : 0, 'param2' : 0, 'param3' : 0, 'param4' : 0, #minimum pitch, empty, empty, yaw angles (deg) 
            'x': loc['latitude'],
            'y': loc['longitude'],
            'z': target_alt
        }
        self._append_event(event)
        return event


    def create_loop_waypoints(self, radius_m: int = 50, num_points: int = 4, altitude: int = 30) -> bool:
        """ Where radius is the metres radius of circle route.
        Returns list of dictionaries for each mission point."""

        loc = self.home
        lat_offset_deg = radius_m / 111_320
        lon_offset_deg = radius_m / (111_320 * math.cos(math.radians(loc['latitude'])))

        for i in range(num_points):
            angle_rad = (2 * math.pi / num_points) * i
            lat = loc['latitude']  + lat_offset_deg * math.cos(angle_rad)
            lon = loc['longitude'] + lon_offset_deg * math.sin(angle_rad)

            wp = {
                'seq': self.seq,
                'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
                'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
                'current': 0,
                'autocontinue': 1,
                'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
                'x': lat, 'y': lon, 'z': 30
            }
            self._append_event(wp)

        return True

    def create_return_event(self, target_alt: int = 0, overrides: dict = None):

        loc = self.home.copy()

        event = {
        'seq': self.seq,
        'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
        'current': 0,
        'autocontinue': 1,
        'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
        'x': loc['latitude'],
        'y': loc['longitude'],
        'z': target_alt
        }
        self._append_event(event)
        return event


    def create_land_event(self):

        loc = self.home

        event = {
            'seq' : self.seq, 
            'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            'command': mavutil.mavlink.MAV_CMD_NAV_LAND,
            'current': 0,
            'autocontinue': 1,
            'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
            'x': loc['latitude'], 
            'y': loc['longitude'], 
            'z': 0
        }
        self._append_event(event)
        return event
    

    ### other util functions ###


    def _append_event(self, event: dict):
        self.mission.append(event)
        self.seq += 1


    def get_mission(self) -> list:
        return self.mission
