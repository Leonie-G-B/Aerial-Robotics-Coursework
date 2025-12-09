

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
import pyvista as pv
import numpy as np 


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################


class PathPlannner:
    def __init__(self, start: str, destination: str):
        self.geo_filename = 'geo_info'
        self.start_wp_info = self._load_wp_info(start)
        self.end_wp_info = self._load_wp_info(destination)

        self.avoid_polys = []
        self.intermediate_wps = []
        self.waypoints = []

        # DEM fields
        self.dem = None
        self.dem_band = None
        self.dem_nodata = None
        self.transform = None   # ALWAYS the transform used
        # self.dem_shift_x = 204915 
        # self.dem_shift_y = 0

        # Results
        self.elevations = []
        self.distances = []

    def _read_yaml(self, filename: str, path: list) -> dict:
        filepath = f"{filename}.yml"
        with open(filepath, 'r') as file:
            data = yaml.safe_load(file)

        for variable in path:
            data = data[variable]

        return data

    def _load_wp_info(self, location_key: str):
        return self._read_yaml(self.geo_filename, ['locations', location_key]).copy()

    def _load_houses_info(self):
        return self._read_yaml(self.geo_filename, ['montserrat_houses']).copy()

    def _haversine(self, lat1, lon1, lat2, lon2):
        R = 6371000
        p1 = math.radians(lat1)
        p2 = math.radians(lat2)
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)

        a = (math.sin(dlat/2)**2 +
             math.cos(p1) * math.cos(p2) * math.sin(dlon/2)**2)
        return 2 * R * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    # def _latlon_to_utm20(self, lat, lon):
    #     proj = pyproj.Transformer.from_crs("EPSG:4326", "EPSG:32620", always_xy=True)
    #     return proj.transform(lon, lat)
    def _latlon_to_utm20(self, lat, lon):
        return self._ll_to_dem.transform(lon, lat)


    def _bilinear_sample(self, dem_data, x, y, transform):
        col, row = ~transform * (x, y)
        r0, c0 = int(np.floor(row)), int(np.floor(col))
        r1, c1 = r0 + 1, c0 + 1

        if (
            r0 < 0 or c0 < 0 or
            r1 >= dem_data.shape[0] or
            c1 >= dem_data.shape[1]
        ):
            return None

        dr = row - r0
        dc = col - c0

        Q11 = dem_data[r0, c0]
        Q12 = dem_data[r0, c1]
        Q21 = dem_data[r1, c0]
        Q22 = dem_data[r1, c1]

        return (
            Q11 * (1 - dr) * (1 - dc) +
            Q12 * (1 - dr) * dc +
            Q21 * dr * (1 - dc) +
            Q22 * dr * dc
        )
    
    
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

    def load_dem(self, dem_path="Maps/MontserratDEMv2.tif", plot=False):
        # Open DEM
        self.dem = rasterio.open(dem_path)
        self.dem_band = self.dem.read(1)
        self.dem_nodata = self.dem.nodata
        self.transform = self.dem.transform  # use as-is

        # Let rasterio tell us the CRS
        if self.dem.crs is None:
            logging.error("DEM has no CRS defined. You must assign one externally (e.g. with gdal_edit) before using it.")
            raise ValueError("DEM has no CRS")

        # Transformer: WGS84 (lat/lon) -> DEM CRS
        # always_xy=True means: pass in (lon, lat)
        # self._ll_to_dem = Transformer.from_crs(
        #     "EPSG:4326",
        #     self.dem.crs,
        #     always_xy=True
        # )

        self._ll_to_dem = Transformer.from_crs(
            "EPSG:4326",
            "+proj=utm +zone=20 +datum=WGS84 +units=m +no_defs +x_0=-200000",
            always_xy=True
        )


        logging.info(f"DEM bounds (UTM): {self.dem.bounds}")

        sx, sy = self._ll_to_dem.transform(
            self.start_wp_info["longitude"],
            self.start_wp_info["latitude"]
        )
        logging.info(f"Start UTM: {sx} {sy}")

        ex, ey = self._ll_to_dem.transform(
            self.end_wp_info["longitude"],
            self.end_wp_info["latitude"]
        )
        logging.info(f"End UTM: {ex} {ey}")


        if plot:
            self.plot_dem()


    def _get_dem_bounds_latlon(self):

        transform = self.transform  # ALWAYS use shifted transform
        rows, cols = self.dem_band.shape
        proj_back = Transformer.from_crs("EPSG:32620", "EPSG:4326", always_xy=True)

        pixel_corners = [
            (0, 0),       # top-left
            (cols, 0),    # top-right
            (cols, rows), # bottom-right
            (0, rows),    # bottom-left
        ]

        corners_latlon = []
        for col, row in pixel_corners:
            utm_x, utm_y = transform * (col, row)
            lon, lat = proj_back.transform(utm_x, utm_y)
            corners_latlon.append([lat, lon])

        corners_latlon.append(corners_latlon[0])
        return corners_latlon

    def create_house_polygons(self):
        house_info = self._load_houses_info()
        for _, house in house_info.items():
            self.avoid_polys.append(
                self.circle_to_polygon(house['lat'], house['long'], radius_m=50)
            )

    def create_wp_set(self):
        waypoints = [(self.start_wp_info["latitude"], self.start_wp_info["longitude"])]
        for wp in self.intermediate_wps:
            waypoints.append((wp["latitude"], wp["longitude"]))
        waypoints.append((self.end_wp_info["latitude"], self.end_wp_info["longitude"]))
        self.waypoints = waypoints
        return waypoints

    def plot_route_on_map(self, root_folder: str, filename="route_map.html"):
        if not self.waypoints:
            raise ValueError("Call create_wp_set() first.")

        m = folium.Map(location=self.waypoints[0], zoom_start=13)

        # DEM footprint
        if self.dem is not None:
            try:
                dem_poly = self._get_dem_bounds_latlon()
                folium.Polygon(
                    locations=dem_poly,
                    color="blue",
                    weight=3,
                    fill=False,
                    popup="DEM footprint"
                ).add_to(m)
            except Exception as e:
                print("DEM footprint unavailable:", e)

        #polygons
        for poly in self.avoid_polys:
            folium.Polygon(
                locations=poly,
                color="red",
                fill=True,
                fill_opacity=0.3
            ).add_to(m)

        
        folium.PolyLine(self.waypoints, color="red", weight=4).add_to(m)

        for i, (lat, lon) in enumerate(self.waypoints):
            folium.Marker([lat, lon], popup=f"WP {i}").add_to(m)

        m.save(path.join(root_folder, filename))
        print(f"Saved map: {filename}")


    def plot_dem(self):
        dem_data = self.dem_band
        nodata = self.dem_nodata
        transform = self.transform  # SHIFTED transform

        masked = np.where(dem_data == nodata, np.nan, dem_data)

        def latlon_to_pixel(lat, lon):
            x, y = self._ll_to_dem.transform(lon, lat)  
            col, row = ~transform * (x, y)
            return int(row), int(col)

        s_row, s_col = latlon_to_pixel(
            self.start_wp_info["latitude"], self.start_wp_info["longitude"]
        )

        e_row, e_col = latlon_to_pixel(
            self.end_wp_info["latitude"], self.end_wp_info["longitude"]
        )

        plt.figure(figsize=(10, 8))
        plt.imshow(masked, cmap="terrain", origin="upper")
        plt.colorbar(label="Elevation (m)")
        plt.scatter([s_col], [s_row], c="red", s=80, label="Start")
        plt.scatter([e_col], [e_row], c="cyan", s=80, label="Destination")
        plt.title("DEM (shifted) with route points")
        # plt.legend()
        plt.show()

    def get_elevation_data(self, dem_path="Maps/MontserratDEMv2.tif"):
        if not self.waypoints:
            raise ValueError("Call create_wp_set() first.")

        # Load DEM & set transformer
        self.load_dem(plot=True, dem_path=dem_path)

        dem_data = self.dem_band
        transform = self.transform

        elevations = []
        distances = []

        total_dist = 0.0
        prev = None

        for lat, lon in self.waypoints:
            # IMPORTANT: lon, lat order
            x, y = self._ll_to_dem.transform(lon, lat)

            # Bilinear or nearest sampling – I’ll keep your bilinear helper:
            elev = self._bilinear_sample(dem_data, x, y, transform)

            # Fallback behaviour
            if elev is None or (self.dem_nodata is not None and elev == self.dem_nodata):
                elevations.append(np.nan)
            else:
                elevations.append(float(elev))

            if prev is None:
                distances.append(0.0)
            else:
                total_dist += self._haversine(prev[0], prev[1], lat, lon)
                distances.append(total_dist)

            prev = (lat, lon)

        self.elevations = elevations
        self.distances = distances

        print("Elevation sampling complete.")


    def plot_elevation_profile(self):
        if not self.elevations:
            raise ValueError("Run get_elevation_data() first.")

        plt.figure(figsize=(10, 4))
        plt.plot(self.distances, self.elevations, linewidth=2)
        plt.xlabel("Distance (m)")
        plt.ylabel("Elevation (m)")
        plt.grid()
        plt.tight_layout()
        plt.show()




class PathPlannerv2: 
    def __init__(self,
                  cruise_alt_above_ground_initial = 100,
                  h_cruise_distance  = 3000,
                  summit_clearance = 200,
                  terrain_clearance = 150,
                  plot_dem_on_start = False):
        self.cellsize = 10#
        self.cruise_alt_ag_initial = cruise_alt_above_ground_initial
        self.h_cruise_distance = h_cruise_distance
        self.summit_clearance = summit_clearance
        self.terrain_clearance = terrain_clearance

        self.start_info = self._read_yaml(filename="geo_info", path=["locations","mvo_helipad"])
        self.end_info   = self._read_yaml(filename="geo_info", path=["locations","soufriere_hills_summit"])

        self.simple_dem_load()

        ground_start = self.get_elevation(  
            self.start_info['dem_x'],
            self.start_info['dem_y']
            )

        if plot_dem_on_start:
            self.plot_dem()

        self.initial_cruise_alt = ground_start + self.cruise_alt_ag_initial
        
        self.mission_slice = None
        self.slice_state_space = None


    def _read_yaml(self, filename: str, path: list) -> dict:
        filepath = f"{filename}.yml"
        with open(filepath, 'r') as file:
            data = yaml.safe_load(file)

        for variable in path:
            data = data[variable]

        return data
    
    def sample_between_points(self, x0, y0, x1, y1, num_samples=100):
        xs = np.linspace(x0, x1, num_samples)
        ys = np.linspace(y0, y1, num_samples)
        return xs, ys
    
    def get_elevation_profile_of_line(self, start, end, num_samples=100):
        xs, ys = self.sample_between_points(
            start['dem_x'], start['dem_y'],
            end['dem_x'], end['dem_y'],
            num_samples
        )

        elevations = []
        for x, y in zip(xs, ys):
            elev = self.get_elevation(x, y)
            elevations.append(elev)

        # cellsize = 10
        distances = np.sqrt((xs - xs[0])**2 + (ys - ys[0])**2) * self.cellsize
        return distances, elevations

    def simple_dem_load(self, dem_path: str = "Maps/MontserratDEMv3.tif"):
        self.path = dem_path

        with rasterio.open(self.path) as src:
            self.data = src.read(1).astype(float)
            self.nodata = src.nodata
            self.height, self.width = self.data.shape

        if self.nodata is None: 
            self.data[self.data == -9999] = np.nan

        # replace nodata with NaN
        if self.nodata is not None:
            self.data[self.data == self.nodata] = np.nan

        logging.info(f"Loaded DEM: {self.width} x {self.height}")

    def get_elevation(self, x, y):
            """x,y are pixel coordinates (col, row)."""
            x = int(round(x))
            y = int(round(y))

            if x < 0 or x >= self.width or y < 0 or y >= self.height:
                return None
            
            return self.data[y, x]
    
    def plot_dem(self): 

        start_x = self.start_info['dem_x']
        start_y = self.start_info['dem_y']

        end_x = self.end_info['dem_x']
        end_y = self.end_info['dem_y']

        plt.figure(figsize=(10, 8))
        plt.imshow(self.data, cmap="terrain")
        plt.colorbar(label="Elevation")
        plt.scatter([start_x], [start_y], c="red")
        plt.scatter([end_x], [end_y], c="blue")
        plt.show()

    def plot_elevation_profile(self, title: str = "Elevation Profile Along Line"):
        distances, elevations = self.get_elevation_profile_of_line(
            self.start_info,
            self.end_info,
            num_samples=200
        )

        #interpolate nans
        elevations = np.array(elevations, dtype=float)
        nans = np.isnan(elevations)

        if np.any(nans):
            valid_x = np.where(~nans)[0]
            valid_y = elevations[~nans]

            # linear interpolate missing values
            elevations[nans] = np.interp(
                np.where(nans)[0],
                valid_x,
                valid_y
        )
            
        fig, ax = plt.subplots(figsize=(10,4))

        ax.plot(distances, elevations, linewidth=2)
        ax.fill_between(distances, elevations, color="lightgreen", alpha=0.5)
        ax.set_xlabel("Distance (m)")
        ax.set_ylabel("Elevation (m)")
        ax.set_title(title)
        ax.grid(True)
        fig.tight_layout()

        return fig, ax

    def plot_2d_slice_profile(self, title: str = "Elevation Profile with Horizontal Cruise"):

        fig, ax = self.plot_elevation_profile(
            title=title
        )
        start_alt = self.initial_cruise_alt

        ax.plot(
            [0, self.h_cruise_distance],
            [start_alt, start_alt],
            color="red",
            linestyle="--",
            linewidth=2,
            label="Horizontal Cruise"
        )

        ax.fill_between(
            [0, self.h_cruise_distance],
            [start_alt, start_alt],
            color="pink",
            alpha=0.3
        )

        if self.slice_state_space is not None:
            ss = self.slice_state_space
            s_vals   = ss["s_vals"]
            H_start  = ss["H_start"]
            H_end    = ss["H_end"]
            L_m      = ss["L_m"]

            # Define same plane function used in state space
            def plane_height(s):
                return H_start + (H_end - H_start) * (s / L_m)

            # Build climb path arrays
            climb_x = s_vals
            climb_y = plane_height(s_vals)

            # Plot climb line
            ax.plot(
                climb_x + self.h_cruise_distance,
                climb_y,
                color="blue",
                linestyle = "--",
                linewidth=2,
                label="Climb Plane (to summit clearance)"
            )

            # Optional shading under climb plane
            ax.fill_between(
                climb_x + self.h_cruise_distance,
                climb_y,
                color="lightblue",
                alpha=0.2
            )

        else:
            ax.text(
                0.98, 0.02,
                "State space not built yet — climb line unavailable",
                ha="right", va="bottom",
                transform=ax.transAxes,
                fontsize=8,
                color="gray"
            )

        ax.legend()
        fig.tight_layout()

        # Store reusable view
        self.mission_slice = (fig, ax)

        return fig, ax
    

    def build_slice_state_space(
            self, 
            state_space_width_m = 1000.0,
            n_climb_dir = 400, #resolution in climb direction (S)
            n_perp_climb = 200 #resolution perpendicular to climb (R)
        ):
        """
        Docstring for build_slice_state_space
        
        :param self: Description
        :param cruise_dist_m: Description
        :param end_clearance_m: Description
        :param route_clearance_m: Description
        :param state_space_width_m: Description
        :param n_climb_dir: Description
        :param n_perp_climb: Description
        :param initial_alt: Description
        """
        logging.info("Begginnig state space definition...")

        cruise_dist_m = self.h_cruise_distance
        initial_alt   = self.initial_cruise_alt
        end_clearance_m = self.summit_clearance
        route_clearance_m = self.terrain_clearance


        S = np.array([self.start_info['dem_x'], self.start_info['dem_y']], float)
        E = np.array([self.end_info['dem_x'], self.end_info['dem_y']], float)


        axis_vect = E - S 
        axis_length = np.linalg.norm(axis_vect) #length of vector start to finish
        axis_unit = axis_vect / axis_length #normalised vector

        cruise_pix = cruise_dist_m / self.cellsize
        start_climb = S + axis_unit * cruise_pix # location where cruise ends and climb begins

        remaining_pix = axis_length - cruise_pix
        L_m = remaining_pix * self.cellsize #remaining distance 

        logging.info(f"Remaining distance to travel (as the crow flies): {L_m}m.")

        #now find the highest summit point in the vicinity of the defined 'end point'

        radius_m = 50.0
        radius_pix = int(radius_m / self.cellsize)

        cx, cy = int(E[0]), int(E[1])  # summit pixel center

        max_elev = -np.inf

        for dy in range(-radius_pix, radius_pix + 1):
            for dx in range(-radius_pix, radius_pix + 1):

                # Only include points inside a circular radius
                if dx*dx + dy*dy <= radius_pix*radius_pix:

                    xx = cx + dx
                    yy = cy + dy

                    elev = self.get_elevation(xx, yy)
                    if elev is None or np.isnan(elev):
                        continue

                    if elev > max_elev:
                        max_elev = elev

        summit_elev = max_elev
        final_alt = summit_elev + end_clearance_m

        def plane_height(s_): #plane height as a function of S (underscore after to distibguish from S )
            return initial_alt + (final_alt - initial_alt) * (s_ /L_m)
        

        side_unit = np.array([-axis_unit[1], axis_unit[0]]) #90deg rotated vecotr in the horizontal plane

        #create statespace grids

        s_vals = np.linspace( 0, L_m, n_climb_dir) #array along climb
        r_vals = np.linspace( -state_space_width_m, state_space_width_m, n_perp_climb) #array perpendicular to climb

        terrain = np.full((n_climb_dir, n_perp_climb), np.nan) #elevation height
        plane   = np.full((n_climb_dir, n_perp_climb), np.nan) #plane 
        clear   = np.full((n_climb_dir, n_perp_climb), np.nan) # vertical clearance
        obst    = np.zeros((n_climb_dir, n_perp_climb), bool) #obstacle flag (if clearance less than threshold)

        #POPULATE THE GRIDS

        for i, s in enumerate(s_vals):
            Hp = plane_height(s) #plane height at this position
            for j, r in enumerate(r_vals):
                along_pix = s / self.cellsize #m conversion
                side_pix  = r / self.cellsize
                xy = start_climb + axis_unit * along_pix + side_unit * side_pix
                x_pix, y_pix = xy[0], xy[1]

                elev = self.get_elevation(x_pix, y_pix)
                if elev is None or np.isnan(elev):
                    continue

                terrain[i, j] = elev
                plane[i, j]   = Hp
                clear[i, j]   = Hp - elev

                if Hp - elev < route_clearance_m:
                    obst[i, j] = True

        self.slice_state_space = {
            "s_vals": s_vals,
            "r_vals": r_vals,
            "terrain_height": terrain,
            "plane_height": plane,
            "clearance": clear,
            "obstacle_mask": obst,
            "axis_unit": axis_unit,
            "side_unit": side_unit,
            "start_climb_xy": start_climb,
            "L_m": L_m,
            "H_start": initial_alt,
            "H_end": final_alt,
        }

        logging.info(f"Any obstacles: {self.slice_state_space['obstacle_mask'].any()}\nMin clearnace: {np.nanmin(self.slice_state_space['clearance'])}m.")

        return self.slice_state_space
    

    def plot_slice_state_space(self):
        
        if self.slice_state_space is None:
            logging.error("Call build_slice_state_space() first.")
            return 
        
        ss = self.slice_state_space
        s_vals = ss['s_vals']
        r_vals = ss['r_vals']
        obst   = ss['obstacle_mask']

        axis_unit = ss["axis_unit"]       # direction of climb on DEM
        side_unit = ss["side_unit"]       # perpendicular direction
        L_m       = ss["L_m"]             # total climb distance

        fig, ax = plt.subplots(figsize=(10,6))

        # Plot obstacle mask
        ax.imshow(
            obst.T, 
            origin='lower',
            extent=[s_vals[0], s_vals[-1], r_vals[0], r_vals[-1]],
            cmap='gray_r',
            aspect='auto'
        )


        ax.scatter(0, 0, c='red', s=60, label="Start of Climb (s=0, r=0)")
        ax.scatter(L_m, 0, c='blue', s=60, label="End of Climb (Summit)")

        # axis_unit is a direction in DEM pixels (dx, dy).
        # DEM Y increases downward, so north is -y direction
        # DEM north vector: y decreases upward
        north_dem = np.array([0, -1.0])

        north_s = np.dot(north_dem, axis_unit)
        north_r = np.dot(north_dem, side_unit)

        norm = np.sqrt(north_s**2 + north_r**2)
        north_s /= norm
        north_r /= norm

        scale = 0.1 * s_vals[-1]
        anchor_s = 0.9 * s_vals[-1]
        anchor_r = 0.8 * r_vals[-1]

        # Draw arrow
        ax.arrow(anchor_s, anchor_r,
                north_s * scale,
                north_r * scale,
                head_width=0.05 * scale,
                head_length=0.08 * scale,
                fc='blue', ec='blue', linewidth=2)

        ax.text(anchor_s + north_s * scale * 1.1,
                anchor_r + north_r * scale * 1.1,
                "N", color="blue", fontsize=14, ha="center")

        # ----------------------------------------------------------------------
        # Labels & legend
        # ----------------------------------------------------------------------
        ax.set_xlabel("Distance Along Climb (m)")
        ax.set_ylabel("Perpendicular Distance (m)")
        ax.set_title("Obstacle Mask in Climb Direction State Space")
        ax.legend(loc='upper left')

        fig.tight_layout()
        self.state_space_plot = (fig, ax)
        return fig, ax