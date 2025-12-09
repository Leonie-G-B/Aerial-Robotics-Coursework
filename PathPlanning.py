

import folium
# import srtm
# from srtm.data import SrtmElevationData 
import math
import yaml
import elevation
import rasterio
import numpy as np
import matplotlib.pyplot as plt
from os import path
import requests
import rasterio
from rasterio.transform import rowcol
from pyproj import Transformer
import pyproj


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

    def _latlon_to_utm20(self, lat, lon):
        """Transformer for elevtion interpolation"""
        proj = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32620", always_xy=True)
        x, y = proj.transform(lon, lat)
        return x, y


    def _bilinear_sample(self, dem_data, x, y, transform):
        """Bilinear interp. for DEM at x,y in UTM 20N coords."""

        col, row = ~transform * (x, y)  # fractional row/col
        r0, c0 = int(np.floor(row)), int(np.floor(col))
        r1, c1 = r0 + 1, c0 + 1

        # If outside DEM bounds
        if (r0 < 0 or c0 < 0 or r1 >= dem_data.shape[0] or c1 >= dem_data.shape[1]):
            return None

        # fractional parts
        dr = row - r0
        dc = col - c0

        # four neighboring cells
        Q11 = dem_data[r0, c0]
        Q12 = dem_data[r0, c1]
        Q21 = dem_data[r1, c0]
        Q22 = dem_data[r1, c1]

        # bilinear interpolation formula
        value = (
            Q11 * (1 - dr) * (1 - dc) +
            Q12 * (1 - dr) * dc +
            Q21 * dr * (1 - dc) +
            Q22 * dr * dc
        )

        return float(value)



    def load_dem(self, plot:bool = True, dem_path="Maps/MontserratDEM.tif",):
        self.dem = rasterio.open(dem_path)
        self.dem_band = self.dem.read(1)
        self.dem_nodata = self.dem.nodata


        # Lat/lon -> UTM 20N converter
        self._ll_to_utm = Transformer.from_crs(
            "EPSG:4326", "EPSG:32620", always_xy=True
        )

        if plot: 
            self.plot_dem()


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

    def _get_dem_bounds_latlon(self):
        """Return DEM bounding box corners in lat/lon using the shifted transform."""

        # if not hasattr(self, "transform"):
        #     raise RuntimeError("Load DEM before requesting bounds.")

        # DEM array shape: (rows, cols)
        rows, cols = self.dem_band.shape

        # t = self.transform  
        transform = getattr(self, "transform", self.dem.transform)

        # Pixel corners → UTM
        corners_utm = [
            (0, 0),            # top-left
            (cols, 0),         # top-right
            (cols, rows),      # bottom-right
            (0, rows),         # bottom-left
        ]

        # Convert UTM → lat/lon
        proj_back = Transformer.from_crs("EPSG:32620", "EPSG:4326", always_xy=True)
        corners_latlon = []

        for col, row in corners_utm:
            utm_x, utm_y = transform * (col, row)

            lon, lat = proj_back.transform(utm_x, utm_y)
            corners_latlon.append([lat, lon])

        # Close polygon loop
        corners_latlon.append(corners_latlon[0])

        return corners_latlon

    def plot_route_on_map(self, root_folder:str, filename: str = 'route_map.html'):
        if not self.waypoints:
            raise ValueError("Call create_wp_set() first.")

        m = folium.Map(location=self.waypoints[0], zoom_start=13)

        if hasattr(self, "dem"):
            try:
                dem_poly = self._get_dem_bounds_latlon()
                folium.Polygon(
                    locations=dem_poly,
                    color="blue",
                    weight=3,
                    fill=False,
                    popup="DEM footprint (shifted)"
                ).add_to(m)
            except Exception as e:
                print("DEM footprint unavailable:", e)

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

    def plot_dem(self, dem_path="Maps/MontserratDEM.tif"):
        """Plot DEM with start and end waypoints marked."""
        import matplotlib.pyplot as plt
        import numpy as np

        if not self.dem: 
            self.load_dem()
        dem = self.dem
        nodata = self.dem_nodata
        dem_data = self.dem_band
        transform = dem.transform
        # transform = self.transform

        # Mask NODATA
        nodata = dem.nodata
        if nodata is not None:
            masked_dem = np.where(dem_data == nodata, np.nan, dem_data)
        else:
            masked_dem = dem_data.astype(float)

        # Convert start/destination lat/lon → UTM → pixel row/col
        def latlon_to_pixel(lat, lon):
            x, y = self._latlon_to_utm20(lat, lon)
            col, row = ~transform * (x, y)
            return int(row), int(col)

        # Start point
        s_lat = self.start_wp_info["latitude"]
        s_lon = self.start_wp_info["longitude"]
        s_row, s_col = latlon_to_pixel(s_lat, s_lon)

        # End point
        e_lat = self.end_wp_info["latitude"]
        e_lon = self.end_wp_info["longitude"]
        e_row, e_col = latlon_to_pixel(e_lat, e_lon)

        # --- Plot ---
        plt.figure(figsize=(10, 8))
        plt.imshow(masked_dem, cmap="terrain", origin="upper")
        plt.colorbar(label="Elevation (m)")
        plt.title("Montserrat DEM with Start & End Waypoints")

        # Mark points
        plt.scatter([s_col], [s_row], c="red", s=80, label="Start")
        plt.scatter([e_col], [e_row], c="cyan", s=80, label="Destination")

        plt.legend()
        plt.xlabel("Column index (DEM pixels)")
        plt.ylabel("Row index (DEM pixels)")
        plt.show()

    def get_elevation_data(self, dem_path="Maps/MontserratDEM.tif"):
        """Load DEM and sample elevation along stored waypoints."""

        if not self.waypoints:
            raise ValueError("Call create_wp_set() before get_elevation_data().")

        self.load_dem()
        dem = self.dem
        dem_data = self.dem_band
        transform = dem.transform

        elevations = []
        distances = []

        total_dist = 0.0
        prev_latlon = None

        for lat, lon in self.waypoints:

            # Convert to DEM coordinate system (UTM 20N)
            x, y = self._latlon_to_utm20(lat, lon)

            # Sample DEM (bilinear)
            elev = self._bilinear_sample(dem_data, x, y, transform)
            elevations.append(elev)

            # Distance accumulation
            if prev_latlon is None:
                distances.append(0)
            else:
                d = self._haversine(prev_latlon[0], prev_latlon[1], lat, lon)
                total_dist += d
                distances.append(total_dist)

            prev_latlon = (lat, lon)

        self.elevations = elevations
        self.distances = distances

        print("Elevation sampling complete.")
        print("Sample count:", len(elevations))



    def plot_elevation_profile(self):
        import matplotlib.pyplot as plt

        if not self.elevations or not self.distances:
            raise ValueError("Run get_elevation_data() first.")

        plt.figure(figsize=(10,4))
        plt.plot(self.distances, self.elevations, linewidth=2)
        plt.xlabel("Distance (m)")
        plt.ylabel("Elevation (m)")
        plt.title("Terrain Elevation Profile Along Route")
        plt.grid(True)
        plt.tight_layout()
        plt.show()



class MontserratDEM:
    def __init__(self, dem_path="montserrat_dem.asc"):
        # Open the ESRI ASCII grid
        self.src = rasterio.open(dem_path)

        # DEM is in WGS84 / UTM zone 20N -> EPSG:32620
        self.transformer = Transformer.from_crs(
            "EPSG:4326",   # lat/lon
            "EPSG:32620",  # UTM zone 20N
            always_xy=True
        )

        self.band = self.src.read(1)
        self.nodata = self.src.nodata

    def get_elevation(self, lat, lon):
        # Convert geographic coords to UTM
        x, y = self.transformer.transform(lon, lat)

        # Convert to row/col indices in the raster
        row, col = self.src.index(x, y)

        # Guard against out-of-bounds
        if row < 0 or row >= self.band.shape[0] or col < 0 or col >= self.band.shape[1]:
            return None

        z = float(self.band[row, col])
        if self.nodata is not None and z == self.nodata:
            return None

        return z