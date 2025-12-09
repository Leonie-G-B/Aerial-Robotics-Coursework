
import PathPlanning 

# everything from defining waypoints, plotting graphs, and sending to mission planner



def main():
    
    # Path = PathPlanning.PathPlannner(
    #     start= "mvo_helipad",
    #     destination= "soufriere_hills_summit"
    # )
    
    # Path.create_house_polygons()
    # Path.create_wp_set()


    # Path.get_elevation_data()
    # Path.plot_elevation_profile()

    # Path.plot_route_on_map(
    #     root_folder = "C:\\Users\\admin01\\OneDrive\\Documents\\UNI\\UNI\\Fork\\Path-Planning-Helper\\Maps",
    #     filename= "Test_Map_1"
    # )

    cruise_distance =2800

    Planner = PathPlanning.PathPlannerv2(
        cruise_alt_above_ground_initial = 125,
        h_cruise_distance  = cruise_distance,
        summit_clearance = 150,
        terrain_clearance = 130
    )
    # Planner.plot_elevation_profile()
    Planner.plot_2d_slice_profile()

    Planner.build_slice_state_space()

    Planner.plot_slice_state_space()

    Planner.plot_2d_slice_profile(title= "2D Elevation Slice with horizontal cruise and climb.")


if __name__ == "__main__":
    main()