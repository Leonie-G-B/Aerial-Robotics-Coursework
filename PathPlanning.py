

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
from rasterio.transform import  xy as transform_xy
from pyproj import Transformer
import pyproj
import pyvista as pv
import numpy as np 
from scipy.ndimage import binary_dilation, label
import shapely
from shapely.geometry import Polygon, Point, LineString, MultiPoint
import networkx as nx
import heapq


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################

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
            n_perp_climb = 200, #resolution perpendicular to climb (R)
            extra_buffer_at_end = 250 #go an extra N metres behind the end point just to make the plots look a bit better.
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

        extended_L = L_m + extra_buffer_at_end
        s_vals = np.linspace(0, extended_L, n_climb_dir) #array along climb
        r_vals = np.linspace( -state_space_width_m, state_space_width_m, n_perp_climb) #array perpendicular to climb

        terrain = np.full((n_climb_dir, n_perp_climb), np.nan) #elevation height
        plane   = np.full((n_climb_dir, n_perp_climb), np.nan) #plane 
        clear   = np.full((n_climb_dir, n_perp_climb), np.nan) # vertical clearance
        obst    = np.zeros((n_climb_dir, n_perp_climb), bool) #obstacle flag (if clearance less than threshold)

        #POPULATE THE GRIDS

        for i, s in enumerate(s_vals):
            Hp = plane_height(min(s, L_m))  #plane height at this position (horizontal after end where plot buffer is)
            for j, r in enumerate(r_vals):
                along_pix = (
                    s / self.cellsize if s <= L_m
                    else L_m / self.cellsize + (s - L_m) / self.cellsize # covvnert to m and 
                )
                side_pix = r / self.cellsize

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
            "extended_L": extended_L,
            "extra_forward_m": extra_buffer_at_end,
            "start_climb_xy": start_climb,
            "L_m": L_m,
            "H_start": initial_alt,
            "H_end": final_alt,
        }

        logging.info(f"Any obstacles: {self.slice_state_space['obstacle_mask'].any()}\nMin clearnace: {np.nanmin(self.slice_state_space['clearance'])}m.")

        return self.slice_state_space
    

    def plot_slice_state_space(self, 
                               title: str = "Obstacle Mask in Climb Direction State Space",
                               plot_dilated_flags: bool = False,
                               plot_visibility_graph: bool = False,
                               plot_final_route: bool = False):
        
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

        if plot_dilated_flags:
            if "obstacle_mask_dilated" in ss:
                dilated = ss["obstacle_mask_dilated"]

                ax.imshow(
                    dilated.T,
                    origin='lower',
                    label = 'Dilated clearance obstacles',
                    extent=[s_vals[0], s_vals[-1], r_vals[0], r_vals[-1]],
                    cmap='Greys',
                    alpha=0.35,
                    aspect='auto'
                )

            else:
                ax.text(
                    0.01, 0.95,
                    "Dilation requested but not computed.\nRun dilate_obstacles() first.",
                    transform=ax.transAxes,
                    fontsize=10,
                    color="red",
                    ha="left"
                )

        if plot_visibility_graph:
            if ("visibility_graph" not in ss) or ("obstacle_polygons" not in ss):
                logging.error("Visibility graph not calculated or found.")
                return
            else:
                G = ss["visibility_graph"]
                polys = ss["obstacle_polygons"]

                for poly in polys:
                    xs, ys = poly.exterior.xy
                    ax.plot(xs, ys, color="pink", linewidth=2)
                    ax.fill(xs, ys, color="pink", alpha=0.2)

                node_positions = {}

                for name in G:
                    if name == "start":
                        pos = (0.0, 0.0)
                    elif name == "goal":
                        pos = (L_m, 0.0)
                    else:
                        poly_id = int(name.split("_")[0][4:])
                        v_id    = int(name.split("_")[1][1:])
                        pos     = polys[poly_id].exterior.coords[v_id]

                    node_positions[name] = pos

                    if name not in ("start" or "goal"):
                        ax.scatter(pos[0], pos[1], c="cyan", s=30)

                for a in G:
                    for b in G[a]:
                        pa = node_positions[a]
                        pb = node_positions[b]
                        ax.plot([pa[0], pb[0]], [pa[1], pb[1]],
                                color="orchid", alpha=0.4, linewidth=1, linestyle = "--")

        if plot_final_route and "astar_path_coords" in ss:
            px, py = zip(*ss["astar_path_coords"])

            ax.plot(
                px, py,
                color="royalblue",
                linewidth=2.0,
                label="A* Final Path"
            )

            ax.scatter(
                px, py,
                color="lime",
                s=15
            )
                
        ax.scatter(0, 0, c='red', s=80, label="Start of Climb (s=0, r=0)")
        ax.scatter(L_m, 0, c='blue', s=80, label="End of Climb (Summit)")


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

        # # Draw arrow
        # ax.arrow(anchor_s, anchor_r,
        #         north_s * scale,
        #         north_r * scale,
        #         head_width=0.05 * scale,
        #         head_length=0.08 * scale,
        #         fc='blue', ec='blue', linewidth=2)
        
        # label_offset = 0.05 * scale
        # ax.text(
        #     anchor_s - north_s * label_offset,
        #     anchor_r - north_r * label_offset,
        #     "N",
        #     color="blue",
        #     fontsize=14,
        #     ha="center",
        #     va="center"
        #     )

        ax.set_xlabel("Distance Along Climb (m)")
        ax.set_ylabel("Perpendicular Distance (m)")
        ax.set_title(title)
        ax.legend(loc='upper left')

        fig.tight_layout()
        self.state_space_plot = (fig, ax)
        return fig, ax


    def dilate_obstacles(self, dilation_m: int = 30):

        if self.slice_state_space is None:
            logging.error("Call build_slice_state_space() before dilating obstacles.")
            return None

        ss = self.slice_state_space
        obst = ss["obstacle_mask"]
        r_vals = ss["r_vals"]


        meters_per_r_pixel = (r_vals[-1] - r_vals[0]) / len(r_vals)
        dilation_pixels = max(1, int(dilation_m / meters_per_r_pixel))

        dilated = binary_dilation(obst, iterations=dilation_pixels)

        self.slice_state_space["obstacle_mask_dilated"] = dilated
        self.slice_state_space["dilation_m"] = dilation_m
        self.slice_state_space["dilation_pixels"] = dilation_pixels

        logging.info(
            f"Dilated obstacle mask created: {dilation_m} m -> {dilation_pixels} pixels"
        )

        return dilated


    def extract_obstacle_polygons(self, min_area: int = 50):
        "still in s,r state space"

        if self.slice_state_space is None: 
            logging.info("Need to build the state space first")
            return None
        
        ss = self.slice_state_space

        if "obstacle_mask_dilated" not in ss:
            logging.error("Call dilate_obstacles() first.")
            return None

        mask = ss["obstacle_mask_dilated"]
        s_vals = ss["s_vals"]
        r_vals = ss["r_vals"]

        # Connected-component labeling
        labeled_mask, num_objs = label(mask)
        logging.info(f"Found {num_objs} obstacle objects before hull reduction.")

        polygons = []

        for obj_id in range(1, num_objs + 1):
            ys, xs = np.where(labeled_mask == obj_id)
            if len(xs) < 3:
                continue

            s_coords = s_vals[ys]
            r_coords = r_vals[xs]

            pts = np.column_stack([s_coords, r_coords])
            hull = MultiPoint(pts).convex_hull

            if hull.area < min_area:
                continue  # remove tiny artifacts

            polygons.append(hull)

        self.slice_state_space["obstacle_polygons"] = polygons
        logging.info(f"{len(polygons)} convex obstacle polygons extracted.")

        return polygons
        

    def build_visibility_graph(self):

        if "obstacle_polygons" not in self.slice_state_space:
            logging.error("Run extract_obstacle_polygons() first.")
            return None
        
        ss = self.slice_state_space
        L_m = ss["L_m"]
        polygons = ss["obstacle_polygons"]

        nodes = []

        start = Point(0.0, 0.0)
        goal = Point(L_m, 0.0)

        nodes.append(("start", start))
        nodes.append(("goal", goal))

        for idx, poly in enumerate(polygons):
            coords = list(poly.exterior.coords)
            for v_i, (s, r) in enumerate(coords):
                nodes.append((f"poly{idx}_v{v_i}", Point(s, r)))

        G = {name: {} for name, _ in nodes} #adjacency graph

        def is_visible(p1, p2):
            seg = LineString([p1, p2])
            for poly in polygons:
                if seg.crosses(poly) or seg.within(poly):
                    return False
            return True

        for i, (name_i, p_i) in enumerate(nodes):
            for j in range(i + 1, len(nodes)):
                name_j, p_j = nodes[j]

                if is_visible(p_i, p_j):
                    dist = p_i.distance(p_j)
                    G[name_i][name_j] = dist
                    G[name_j][name_i] = dist

        self.slice_state_space["visibility_graph"] = G
        logging.info(f"Visibility graph found with {len(G)} nodes")

        return G


    def astar_visibility_path(self):
        """
        A* path finding (manual logic!).
        """

        if "visibility_graph" not in self.slice_state_space:
            raise ValueError("Visibility graph not built. Call build_visibility_graph() first.")

        G    = self.slice_state_space["visibility_graph"]
        polys = self.slice_state_space["obstacle_polygons"]
        L_m   = self.slice_state_space["L_m"]


        pos = {"start": (0.0, 0.0), "goal": (L_m, 0.0)}

        for idx, poly in enumerate(polys):
            coords = list(poly.exterior.coords)
            for v_i, (s, r) in enumerate(coords):
                pos[f"poly{idx}_v{v_i}"] = (s, r)

        def h(n):
            x1, y1 = pos[n]
            x2, y2 = pos["goal"]
            return np.hypot(x1 - x2, y1 - y2)

        open_heap = []
        heapq.heappush(open_heap, (0 + h("start"), 0, "start"))

        came_from = {}
        g_score   = {node: float('inf') for node in G}
        g_score["start"] = 0

        closed = set()

        while open_heap:
            f, g, current = heapq.heappop(open_heap)

            if current in closed:
                continue
            closed.add(current)

            # Goal reached!!
            if current == "goal":
                break

            for neighbor, cost in G[current].items():
                tentative = g + cost
                if tentative < g_score[neighbor]:
                    g_score[neighbor] = tentative
                    came_from[neighbor] = current
                    heapq.heappush(open_heap, (tentative + h(neighbor), tentative, neighbor))

        if "goal" not in came_from:
            logging.error("A* failed: no path found")
            return None, None

        path = ["goal"]
        while path[-1] != "start":
            path.append(came_from[path[-1]])
        path.reverse()

        # Convert to coordinates
        path_coords = [pos[n] for n in path]

        self.slice_state_space["astar_path"] = path
        self.slice_state_space["astar_path_coords"] = path_coords

        logging.info(f"A* path found with {len(path)} nodes.")

        return path, path_coords


    def get_astar_route_length_m(self):
        """
        Returns the climb route length in metres.
        """
        if "astar_path_coords" not in self.slice_state_space:
            raise ValueError("No A* path found. Run astar_visibility_path() first.")

        ss = self.slice_state_space
        path_sr = ss["astar_path_coords"]

        climb_len = 0.0
        for (s0, r0), (s1, r1) in zip(path_sr[:-1], path_sr[1:]):
            ds = s1 - s0
            dr = r1 - r0
            climb_len += np.hypot(ds, dr)

        return climb_len
    

    def plot_route_from_above_DEM(self, title: str = "A* Route from Above"):

        if "astar_path_coords" not in self.slice_state_space:
            raise ValueError("No A* path found. Run astar_visibility_path() first.")
        
        ss = self.slice_state_space
        path_sr = ss["astar_path_coords"]

        axis_unit = ss["axis_unit"]
        side_unit = ss["side_unit"]
        start_climb_xy = ss["start_climb_xy"]

        xs_pix = []
        ys_pix = []

        for (s, r) in path_sr:
            along_pix = s / self.cellsize
            side_pix  = r / self.cellsize

            xy = start_climb_xy + axis_unit * along_pix + side_unit * side_pix
            x_pix, y_pix = xy[0], xy[1]

            xs_pix.append(x_pix)
            ys_pix.append(y_pix)

        start_px = np.array([self.start_info["dem_x"], self.start_info["dem_y"]])
        climb_px = start_climb_xy

        cruise_xs = [start_px[0], climb_px[0]]
        cruise_ys = [start_px[1], climb_px[1]]

        # plot the initial cruise bit
        plt.figure(figsize=(10, 8))
        plt.imshow(self.data, cmap="terrain")
        plt.colorbar(label="Elevation")

        plt.plot(
            cruise_xs,
            cruise_ys,
            color="red",
            linewidth=2.5,
            linestyle="-",
            label=f"Initial Cruise ({self.h_cruise_distance}m)"
            )

        climb_dist = self.get_astar_route_length_m()

        # Route in DEM pixel space
        plt.plot(xs_pix, ys_pix, color="blue", linewidth=2, linestyle = "-",label=f"A* Route ({climb_dist:.1f}m)")

        # Mark start & summit
        plt.scatter(
            self.start_info["dem_x"],
            self.start_info["dem_y"],
            c="red", edgecolors="black", s=100, label="Start location (MVO Helipad)"
        )
        plt.scatter(
            self.end_info["dem_x"],
            self.end_info["dem_y"],
            c="blue", edgecolors="black", s=100, label="Soufrière Hills Summit"
        )

        plt.title(title)
        plt.legend()
        plt.show()