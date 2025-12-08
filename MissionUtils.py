

from pymavlink import mavutil


#################################################################################
import logging                                                                  #       
logging.basicConfig(level=logging.INFO,                                         #
                    format='%(asctime)s [%(levelname)s] %(message)s')           #
#################################################################################




def connect(dom: str = 'tcp:127.0.0.1:5762', conn_timeout: int = 10) -> mavutil.mavlink_connection:
    logging.info(f"Connecting to Mission Planner on {dom}")

    try: 
        connection = mavutil.mavlink_connection(dom)
        hb_msg = connection.wait_heartbeat(timeout = conn_timeout)
    
        if hb_msg is None: #i.e. timeout has occurred
            raise TimeoutError 
        
        logging.info(f"Connection successful on {dom}")

    except TimeoutError as e:
        logging.error(f"Connection unsucsessful after {conn_timeout}s.\nError: {e}")
        connection = None

    except Exception as e:
        logging.error(f"Some other error occurred: {e}")
        connection = None
    
    return connection

def validate_misison(mission: list[dict])-> bool: 
    """Some verificataion that mission plan is likely to work. Returns True if deemed valid.
    Note that this is experimental and qualitative and should be taken as guidelinen anywayyy..
    """

    # COMPLETE THIS AT SOME POINT

    return True


