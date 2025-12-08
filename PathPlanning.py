

import folium
import srtm
import math
import yaml
from os import path


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################



class PathPlannner:
    def __init__(self, start: str, destination:str):
        self.geo_filename = 'geo_info'
        self.start_wp_info = self._load_wp_info(start)
        self.end_wp_info = self._load_wp_info(destination)

        self.intermediate_wps = []
        self.waypoints = []
        self.elevation_data = None
        self.elevations = []
        self.distances = []


    ###### UTILS ######

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

    def _load_wp_info(self,location_key: str):
        info = self._read_yaml(self.geo_filename, ['locations', location_key])
        return info.copy()
    
    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000  # earth
        p1, p2 = math.radians(lat1), math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat/2)**2 +
             math.cos(p1) * math.cos(p2) * math.sin(dlon/2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c
    

    ###### MAIN FUNCS ######

    
    def create_wp_set(self):
        """
        Takes start, int_wps, and destination and creates a list of tuples (lat, lon).
        
        :param self: Description
        """

        waypoints = [
            (self.start_wp_info['latitude'], self.start_wp_info['longitude'])]

        for wp in self.intermediate_wps:
            waypoints.append((wp['latitude'], wp['longitude']))

        waypoints.append(
            (self.end_wp_info['latitude'], self.end_wp_info['longitude']))

        self.waypoints = waypoints
        return waypoints
    

    def create_route(self): #path planning algorithm here
        pass

    def plot_route_on_map(self, root_folder:str, filename: str = 'route_map.html'):
        if not self.waypoints:
            raise ValueError("Call create_wp_set() first.")

        m = folium.Map(location=self.waypoints[0], zoom_start=13)

        # Draw polyline route
        folium.PolyLine(self.waypoints, color="red", weight=4).add_to(m)

        # Mark waypoints
        for i, (lat, lon) in enumerate(self.waypoints):
            folium.Marker([lat, lon], popup=f"WP {i}").add_to(m)

        m.save(f"{path.join(root_folder, filename)}.html")
        print(f"Saved map as {filename}.html")

    def get_elevation_data(self):
        pass

    def plot_elevation_profile(self):
        pass