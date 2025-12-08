

import folium
# import srtm
from srtm.data import SrtmElevationData 
import math
import yaml
from os import path
import matplotlib as plt


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

        self.avoid_polys = []
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

    def _load_houses_info(self):
        info = self._read_yaml(self.geo_filename, ['montserrat_houses'])
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

    def circle_to_polygon(self, lat, lon, radius_m, num_points=60):
        """
        Convert a circular zone into a polygon (list of [lat, lon] points). Compatible with folium .

        :param lat: center latitude
        :param lon: center longitude
        :param radius_m: circle radius in meters
        :param num_points: resolution of polygon
        :return: list of [lat, lon]
        """
        R = 6371000#radius of earth
        poly = []

        for i in range(num_points):
            angle = math.radians(float(i) / num_points * 360.0)
            
            # Offset in meters → degrees
            dlat = (radius_m * math.sin(angle)) / R
            dlon = (radius_m * math.cos(angle)) / (R * math.cos(math.radians(lat)))

            new_lat = lat + math.degrees(dlat)
            new_lon = lon + math.degrees(dlon)
            
            poly.append([new_lat, new_lon])

        return poly
    

    ###### MAIN FUNCS ######

    def create_house_polygons(self): 

        house_info = self._load_houses_info()

        for house_num in house_info:
            house = house_info[house_num]
            self.avoid_polys.append(self.circle_to_polygon(lat= house['lat'], lon= house['long'], radius_m=50))

        return

    
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

        # block out polygons
        for poly in self.avoid_polys:
            folium.Polygon(
                locations=poly,
                color = "red",
                fill=True,
                fill_opacity=0.3,
                popup="50m Radius around house."
            ).add_to(m)

        # Draw polyline route
        folium.PolyLine(self.waypoints, color="red", weight=4).add_to(m)

        # Mark waypoints
        for i, (lat, lon) in enumerate(self.waypoints):
            folium.Marker([lat, lon], popup=f"WP {i}").add_to(m)

        m.save(f"{path.join(root_folder, filename)}.html")
        print(f"Saved map as {filename}.html")

    def get_elevation_data(self):
        """
        Samples elevation at each waypoint currently stored in self.waypoints.
        Populates:
            self.elevations -> list of elevation values (meters)
            self.distances  -> cumulative distance array (meters)
        """
        if not self.waypoints:
            raise ValueError("Call create_wp_set() first, no waypoints defined.")

        #strm elevation dataset
        elevation_source = SrtmElevationData()
        self.elevations = []
        self.distances = [0.0]

        for i, (lat, lon) in enumerate(self.waypoints):
            h = elevation_source.get_elevation(lat, lon, approximate=True)
            self.elevations.append(h)

            if i > 0:
                prev_lat, prev_lon = self.waypoints[i - 1]
                d = self._haversine(prev_lat, prev_lon, lat, lon)
                self.distances.append(self.distances[-1] + d)

        return self.elevations, self.distances

    def plot_elevation_profile(self):
        """
        Plots elevation vs distance using the data stored in the class.
        """
        if not self.elevations or not self.distances:
            raise ValueError("Call get_elevation_data() before plotting.")

        plt.figure(figsize=(10, 4))
        plt.plot(self.distances, self.elevations, marker="o", linewidth=2)

        plt.xlabel("Distance along route (m)")
        plt.ylabel("Elevation (m)")
        plt.title("Elevation Profile Along UAV Route")
        plt.grid(True)

        plt.tight_layout()
        plt.show()  