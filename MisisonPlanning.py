
### Utility functions relating to building up a mission (PyMav) plan

import yaml 
import math
from pymavlink import mavutil


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################




def read_yaml(filename: str, path: list): 
    """"Reads yaml file specified and all data through the path specifed. 
    Where the path follows the levels of heirarchy from highest to lowest."""

    filepath = f"{filename}.yml"

    with open(filepath, 'r') as file:
        data = yaml.safe_load(file)
    
    for variable in path: 
        info = data[variable]

    if info is None: 
        logging.warning(f"Yamml file search did not return any information. File: {filename}. Path details: {path}")

    return info


def load_home(location_key: str = 'fenswood', overrides: dict = {}) -> dict:

    location_info = read_yaml(filename='geo_info', path = ['locations', location_key]).copy() #prevent mutation

    if overrides: 
        location_info.update(overrides)

    return location_info


def create_takeoff_event(seq: int = 0, location_key: str = 'fenswood', target_alt: int = 0, overrides: dict = {}):
    """Create MAVLink Mission Planner compatible takeoff event from specified location."""

    location_info = load_home(location_key=location_key)

    return {
        'seq': seq, #number of point in sequence - expected/default to 0.
        'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        'command': mavutil.mavlink.MAV_CMD_NAV_TAKEOFF,
        'current': 0,
        'autocontinue': 1, 
        'param1' : 0, 'param2' : 0, 'param3' : 0, 'param4' : 0, #minimum pitch, empty, empty, yaw angles (deg) 
        'x': location_info['latitude'],
        'y': location_info['longitude'],
        'z': target_alt
    }


def create_loop_waypoints(seq: int, location_key:str = 'fenswood', radius_m: int = 50, num_points: int = 4) -> list[dict]:
    """ Where radius is the metres radius of circle route.
    Returns list of dictionaries for each mission point."""

    events = []

    location_info = load_home(location_key=location_key)

    lat_offset_deg = radius_m / 111_320
    lon_offset_deg = radius_m / (111_320 * math.cos(math.radians(lat)))

    for i in range(num_points):
        angle_rad = (2 * math.pi / num_points) * i
        lat = location_info.latitude  + lat_offset_deg * math.cos(angle_rad)
        lon = location_info.longitude + lon_offset_deg * math.sin(angle_rad)

        events.append({
            'seq': seq + i,
            'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
            'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
            'current': 0,
            'autocontinue': 1,
            'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
            'x': lat, 'y': lon, 'z': 30
        })

    return events



def create_return_event(seq: int, location_key: str = 'fenswood', target_alt: int = 0, overrides: dict = {}):

    location_info = load_home(location_key=location_key)

    return {
    'seq': seq,
    'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
    'command': mavutil.mavlink.MAV_CMD_NAV_WAYPOINT,
    'current': 0,
    'autocontinue': 1,
    'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
    'x': location_info['latitude'],
    'y': location_info['longitude'],
    'z': target_alt
    }


def creat_land_event(seq: int, location_key: str = 'fenswood'):

    location_info = load_home(location_key=location_key)

    return {
        'seq' : seq, 
        'frame': mavutil.mavlink.MAV_FRAME_GLOBAL_RELATIVE_ALT,
        'command': mavutil.mavlink.MAV_CMD_NAV_LAND,
        'current': 0,
        'autocontinue': 1,
        'param1': 0, 'param2': 0, 'param3': 0, 'param4': 0,
        'x': location_info.latitude, 
        'y': location_info.longitude, 
        'z': 0
    }
