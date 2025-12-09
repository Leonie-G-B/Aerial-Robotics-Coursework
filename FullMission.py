
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

    cruise_distance = 3000

    Planner = PathPlanning.PathPlannerv2()
    Planner.plot_elevation_profile()
    Planner.plot_horizontal_cruise(start_alt=100, cruise_dist=cruise_distance)

    Planner.build_slice_state_space(
        cruise_dist_m=cruise_distance, 
        end_clearance_m= 200,
        route_clearance_m= 300
    )


if __name__ == "__main__":
    main()