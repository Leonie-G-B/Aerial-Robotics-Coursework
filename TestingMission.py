
import MissionUtils as utils
import MisisonPlanning as Plan


def build_circular_testing_mission(home_loc: str = 'fenswood', radius_m = 50, altitude: int = 30, num_circ_points: int = 4):

    mission = []


    mission.append(Plan.create_takeoff_event(location_key=home_loc))

    mission.append(Plan.create_loop_waypoints(seq = len(mission), location_key=home_loc, radius_m=radius_m, num_points=num_circ_points))

    mission.append(Plan.create_return_event(seq=len(mission), location_key=home_loc))

    mission.append(Plan.creat_land_event(seq=len(mission), location_key=home_loc))

    