import time


class RobotMotors:
    def __init__(self, arduino_link):
        self.arduino = arduino_link
        self.next_pot = 1
        self.active_pot = None

    def drive_forward(self):
        """
        Send the motor move command to Arduino.
        Sends pot number directly: mMOVE1, mMOVE2, mMOVE3.
        Returns the target pot number, or None if sending fails.
        """
        if self.next_pot > 3:
            self.next_pot = 1

        target_pot = self.next_pot
        command = f"mMOVE{target_pot}\n"

        print(f"Motors ON: driving to Pot {target_pot}...")

        sent = self.arduino.send_command(command)

        if not sent:
            print("Motor command failed. Robot did not start moving.")
            self.active_pot = None
            return None

        self.active_pot = target_pot
        self.next_pot += 1
        return target_pot

    def wait_for_tape(self, timeout=25):
        """
        Wait until Arduino reports REACHED from the IR tape sensor.
        Returns True if tape was reached, False if timeout happens.
        """
        print("Listening for IR sensor detection...")

        start_time = time.time()

        while True:
            msg = self.arduino.read_message()

            if msg:
                print(f"Arduino says: {msg}")

            if msg and "REACHED" in msg:
                print(f"Robot hit the tape. Arduino says: {msg}")
                return True

            elapsed = time.time() - start_time
            if elapsed >= timeout:
                print(f"Timeout: robot did not report REACHED within {timeout} seconds.")
                return False

            time.sleep(0.05)
