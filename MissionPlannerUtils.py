

import MissionUtils as Utils
from pymavlink import mavutil

import time


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################


def upload_mission(connection: mavutil.mavlink_connection, mission: list[dict]) -> bool:
    """Uploads mission to Mission Planner via provided connection.
    Returns True if upload is successful.
    """

    if not connection:
        logging.error("No MAVlink connection provided. Cannot upload mission.")
        return False
    
    if not Utils.validate_misison(mission): # should i put this method in this script? 
        logging.error("Mission validation failed. Cannot upload mission.")
        return False
    
    try: 
        logging.info("Clearning any existing mission on Mission Planner.")
        try:
            connection.mav.mission_clear_all_send(connection.target_system, connection.target_component)
        except Exception as e:
            logging.warning(f"Failed to clear existing mission. Continuing anyway...\nError: {e}")

        time.sleep(1) #give some time for clear to process

        mission_elements = len(mission)
        logging.info(f"Uploading mission with {mission_elements} elements to Mission Planner.")

        connection.mav.mission_count_send(connection.target_system, connection.target_component, mission_elements)

        for _ in mission:
            logging.info("Waiting for MISSION_REQUEST_LIST...")
            msg = connection.recv_match(type='MISSION_REQUEST_LIST', blocking=True, timeout=5)
            if msg is None:
                logging.error("No MISSION_REQUEST_LIST received.")
                return False

            logging.info("Received MISSION_REQUEST_LIST, sending mission count.")
            connection.mav.mission_count_send(connection.target_system, connection.target_component, mission_elements)
        
            seq = msg.seq
            wp = mission[seq]

            logging.info(f"REQUESTED: {msg.get_type()} seq={msg.seq}")
            logging.info(f"SENDING seq={seq}, lat={wp['x']}, lon={wp['y']}, cmd={wp['command']}, frame={wp['frame']}")


            logging.info(f"Sending mission item seq={seq}")

                        
            if msg.get_type() == "MISSION_REQUEST_INT":
                # Send INT format
                connection.mav.mission_item_int_send(
                    connection.target_system,
                    connection.target_component,
                    seq,
                    wp['frame'],
                    wp['command'],
                    wp['current'],
                    wp['autocontinue'],
                    wp['param1'],
                    wp['param2'],
                    wp['param3'],
                    wp['param4'],
                    wp['x'],  # int32
                    wp['y'],
                    wp['z']
                )
            else:
                # Send FLOAT format
                connection.mav.mission_item_send(
                    connection.target_system,
                    connection.target_component,
                    seq,
                    wp['frame'],
                    wp['command'],
                    wp['current'],
                    wp['autocontinue'],
                    wp['param1'],
                    wp['param2'],
                    wp['param3'],
                    wp['param4'],
                    wp['x'] / 1e7,  # convert int back to float degrees
                    wp['y'] / 1e7,
                    float(wp['z'])
                )
            time.sleep(0.05)

        # After last item, wait for ACK
        ack = connection.recv_match(type='MISSION_ACK', blocking=True, timeout=5)
        if ack:
            logging.info(f"Mission upload ACK received: {ack.type}")
            return True
        else:
            logging.error("No MISSION_ACK received.")
            return False

    except Exception as e: 
        logging.error(f"Some error when uploading the mission: {e}")