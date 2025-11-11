
import MissionUtils as utils

from MisisonPlanning import MissionPlanner


def build_circular_testing_mission(home_loc: str = 'fenswood', radius_m = 50, altitude: int = 30, num_circ_points: int = 4):

    planner = MissionPlanner(home_key='fenswood')

    planner.create_takeoff_event(target_alt=30)
    planner.create_loop_waypoints(radius_m=50, num_points=6, altitude=30)
    planner.create_return_event(target_alt=30)
    planner.create_land_event()

    return planner.get_mission()
    