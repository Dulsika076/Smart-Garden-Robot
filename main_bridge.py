import socket
import traceback

from arduino_link import ArduinoLink
from camera_gimbal import CameraGimbal
from robot_motors import RobotMotors
from website_uploader import upload_pot_scan


HOST = "127.0.0.1"
PORT = 5005

LOCATION_REACHED = "POT_REACHED\n"      # 12 bytes
LOCATION_MOVE_FAILED = "MOVE_FAILED\n"  # 12 bytes
LOCATION_TIMEOUT = "TIMEOUT_ERR\n"      # 12 bytes
LOCATION_BAD_COMMAND = "BAD_COMMAND\n"  # 12 bytes

SCAN_COMPLETE = "SCAN_COMPLETE\n"       # 14 bytes
SCAN_SKIPPED = "SCAN_SKIPPED!\n"        # 14 bytes
SCAN_FAILED = "SCAN_FAILED!!\n"         # 14 bytes

WEED_FOUND = "WEED_FOUND!!!\n"          # 14 bytes
NO_WEEDS = "NO_WEEDS!!!!!\n"            # 14 bytes
WEED_SKIPPED = "WEED_SKIPPED!\n"        # 14 bytes
WEED_UNKNOWN = "WEED_UNKNOWN!\n"        # 14 bytes


def send_status(conn, message, expected_length):
    data = message.encode("utf-8")

    if len(data) != expected_length:
        raise ValueError(
            f"Status message has wrong length: {message!r} is {len(data)} bytes, "
            f"expected {expected_length} bytes."
        )

    conn.sendall(data)


def send_location_status(conn, message):
    send_status(conn, message, 12)


def send_scan_status(conn, message):
    send_status(conn, message, 14)


def send_weed_status(conn, message):
    send_status(conn, message, 14)


def map_weed_result(weed_result):
    if weed_result == "WEED_FOUND":
        return WEED_FOUND

    if weed_result == "NO_WEEDS":
        return NO_WEEDS

    return WEED_UNKNOWN


def upload_scan_to_website(scan_result):
    weed_status = scan_result["weed_status"]

    if weed_status not in ("WEED_FOUND", "NO_WEEDS"):
        print(
            "Website upload skipped because the weed result is unknown. "
            "No false weed value will be sent."
        )
        return False

    try:
        response = upload_pot_scan(
            pot_id=scan_result["pot_id"],
            weed_status=weed_status,
            health_status=scan_result["health_status"],
            health_score=scan_result["health_score"],
            green_ratio=scan_result["green_ratio"],
            stress_ratio=scan_result["stress_ratio"],
            image_paths=scan_result["image_paths"],
        )

        if response is None:
            return False

        return response.ok

    except (ValueError, FileNotFoundError, OSError) as error:
        print(f"Website upload validation failed: {error}")
        return False


def handle_move_command(conn, motors, camera):
    print()
    print("Command received: MOVE")
    print("Starting robot movement sequence...")

    pot_id = motors.drive_forward()

    if pot_id is None:
        print("Move command failed. Sending failure back to LabVIEW.")
        send_location_status(conn, LOCATION_MOVE_FAILED)
        send_scan_status(conn, SCAN_SKIPPED)
        send_weed_status(conn, WEED_SKIPPED)
        return

    if not motors.wait_for_tape(timeout=25):
        print("Robot did not reach tape in time. Sending timeout back to LabVIEW.")
        send_location_status(conn, LOCATION_TIMEOUT)
        send_scan_status(conn, SCAN_SKIPPED)
        send_weed_status(conn, WEED_SKIPPED)
        return

    print("Pot reached.")
    send_location_status(conn, LOCATION_REACHED)

    try:
        print(f"Starting camera scan for Pot {pot_id}...")
        scan_result = camera.perform_smart_scan(pot_id)
        weed_result = scan_result["weed_status"]

        send_scan_status(conn, SCAN_COMPLETE)
        send_weed_status(conn, map_weed_result(weed_result))

        uploaded = upload_scan_to_website(scan_result)

        print(
            f"Sequence complete for Pot {pot_id}. "
            f"Weed result: {weed_result}. "
            f"Website upload: {'SUCCESS' if uploaded else 'FAILED/SKIPPED'}"
        )

    except Exception as e:
        print(f"Camera scan failed: {e}")
        traceback.print_exc()

        send_scan_status(conn, SCAN_FAILED)
        send_weed_status(conn, WEED_UNKNOWN)


def main():
    print("=" * 50)
    print("WEEDBOT OOP MASTER CONTROLLER")
    print("=" * 50)

    arduino = ArduinoLink(port="COM12", baud_rate=9600)

    if not arduino.connect():
        print("Critical error: could not connect to Arduino. Exiting.")
        return

    camera = CameraGimbal(arduino)
    motors = RobotMotors(arduino)

    if not camera.select_camera():
        print("Critical error: could not initialize camera. Exiting.")
        arduino.close()
        return

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((HOST, PORT))
            server.listen()

            print()
            print(f"Python Bridge is ready on {HOST}:{PORT}")
            print("Waiting for LabVIEW...")
            print("-" * 50)

            while True:
                conn, addr = server.accept()

                with conn:
                    print(f"Connected to LabVIEW at {addr}")

                    while True:
                        try:
                            data = conn.recv(1024)

                            if not data:
                                print("LabVIEW disconnected. Waiting for new connection...")
                                break

                            command = data.decode("utf-8", errors="ignore").strip().upper()

                            if command == "MOVE":
                                handle_move_command(conn, motors, camera)
                            else:
                                print(f"Unknown command from LabVIEW: {command!r}")
                                send_location_status(conn, LOCATION_BAD_COMMAND)
                                send_scan_status(conn, SCAN_SKIPPED)
                                send_weed_status(conn, WEED_SKIPPED)

                        except ConnectionResetError:
                            print("LabVIEW connection was reset. Waiting for new connection...")
                            break

                        except Exception as e:
                            print(f"Bridge error: {e}")
                            traceback.print_exc()

                            try:
                                send_location_status(conn, LOCATION_MOVE_FAILED)
                                send_scan_status(conn, SCAN_FAILED)
                                send_weed_status(conn, WEED_UNKNOWN)
                            except Exception:
                                pass

                            break

    except OSError as e:
        print(f"Could not start TCP server on {HOST}:{PORT}: {e}")
        print("Check if another Python bridge window is already running.")

    except KeyboardInterrupt:
        print("Stopping Python bridge...")

    finally:
        arduino.close()
        print("Arduino connection closed.")


if __name__ == "__main__":
    main()
