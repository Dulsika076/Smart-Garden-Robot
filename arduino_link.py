import time

try:
    import serial
    from serial import SerialException
except ImportError:
    serial = None
    SerialException = Exception


class ArduinoLink:
    def __init__(self, port='COM12', baud_rate=9600):
        self.port = port
        self.baud_rate = baud_rate
        self.connection = None

        self.timeout = 1
        self.write_timeout = 2
        self.reconnect_delay = 2.5

    def connect(self):
        print(f"Connecting to Arduino on {self.port}...")

        try:
            self.close()

            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.write_timeout
            )

            # Arduino usually resets when serial opens.
            time.sleep(self.reconnect_delay)

            self._clear_buffers()
            print("Arduino connected.")
            return True

        except Exception as e:
            print(f"Arduino connection failed: {e}")
            self.connection = None
            return False

    def send_command(self, command, retries=2):
        """
        Send a command to Arduino.
        If writing fails, reconnect and resend the same command.
        Returns True if command was sent, False if it failed.
        """

        if not command.endswith("\n"):
            command += "\n"

        for attempt in range(retries + 1):
            try:
                if not self.connection or not self.connection.is_open:
                    print("Serial port is closed. Reconnecting...")
                    if not self.reconnect():
                        continue

                self.connection.write(command.encode("utf-8"))
                self.connection.flush()

                print(f"Sent to Arduino: {command.strip()}")
                return True

            except Exception as e:
                print(f"Serial write failed on attempt {attempt + 1}: {e}")

                if attempt < retries:
                    print("Trying to reconnect and resend command...")
                    self.reconnect()
                else:
                    print(f"Failed to send command after retries: {command.strip()}")

        return False

    def read_message(self):
        """
        Read one line from Arduino.
        Returns the message string, or None if no message is available.
        """

        try:
            if not self.connection or not self.connection.is_open:
                return None

            if self.connection.in_waiting > 0:
                msg = self.connection.readline().decode("utf-8", errors="ignore").strip()

                if msg:
                    return msg

        except Exception as e:
            print(f"Serial read failed: {e}")
            self.reconnect()

        return None

    def reconnect(self):
        print("Reconnecting to Arduino...")

        if serial is None:
            print("Serial package is not installed. Cannot reconnect to Arduino.")
            return False

        try:
            self.close()
            time.sleep(1)

            self.connection = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=self.write_timeout
            )

            # Wait for Arduino reset/setup after opening serial.
            time.sleep(self.reconnect_delay)

            self._clear_buffers()
            print("Arduino reconnected.")
            return True

        except Exception as e:
            print(f"Could not reconnect to Arduino: {e}")
            self.connection = None
            return False

    def _clear_buffers(self):
        try:
            if self.connection and self.connection.is_open:
                self.connection.reset_input_buffer()
                self.connection.reset_output_buffer()
        except SerialException:
            pass

    def close(self):
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
        except Exception:
            pass
        finally:
            self.connection = None