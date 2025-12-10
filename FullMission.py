
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
    # Planner.plot_2d_slice_profile()

    Planner.build_slice_state_space()

    # Planner.plot_slice_state_space()

    Planner.plot_2d_slice_profile(title= "2D Elevation Slice with horizontal cruise and climb.")

    Planner.dilate_obstacles(dilation_m = 50)

    # Planner.plot_slice_state_space(plot_dilated_flags=True)

    Planner.extract_obstacle_polygons()
    Planner.build_visibility_graph()

    # Planner.plot_slice_state_space(title = "Visibility graph in Climb plane state-space",
    #     plot_dilated_flags=True, plot_visibility_graph=True)
    
    Planner.astar_visibility_path()
    Planner.plot_slice_state_space(title = "Node Visibility Graph and Final Path Planning Route (A*)",
                                   plot_dilated_flags=True,
                                   plot_visibility_graph = True,
                                   plot_final_route = True)
    
    Planner.plot_route_from_above_DEM(
        title = f"A* Path Planning Route Result.\nInitial cruise: {cruise_distance}m")


if __name__ == "__main__":
    main()