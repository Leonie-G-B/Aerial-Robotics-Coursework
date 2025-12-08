

#### Main entry point code (simple and clear)

import TestingMission as Test
import MissionPlannerUtils as MP


def main():
    
    
    mission, connection = Test.build_circular_testing_mission()

    MP_success = MP.upload_mission(connection=connection,
                                   mission=mission)


    pass



if __name__ == "__main__":
    main()