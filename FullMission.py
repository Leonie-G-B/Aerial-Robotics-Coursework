
import PathPlanning 

# everything from defining waypoints, plotting graphs, and sending to mission planner



def main():
    
    Path = PathPlanning.PathPlannner(
        start= "mvo_helipad",
        destination= "soufriere_hills_summit"
    )

    Path.create_wp_set()
    Path.plot_route_on_map(
        root_folder = "C:\\Users\\admin01\\OneDrive\\Documents\\UNI\\UNI\\Fork\\Path-Planning-Helper\\Maps",
        filename= "Test_Map_1"
    )


if __name__ == "__main__":
    main()