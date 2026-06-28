// Direct control pins for the L293D / HW-130 shield
const int MOTOR_LATCH = 12;
const int MOTOR_CLK = 4;
const int MOTOR_ENABLE = 7;
const int MOTOR_DATA = 8;

// PWM Speed control pins on the Arduino Uno
const int MOTOR1_PWM = 11; // M1 (Front Right)
const int MOTOR2_PWM = 3;  // M2 (Back Right)
const int MOTOR3_PWM = 6;  // M3 (Back Left)
const int MOTOR4_PWM = 5;  // M4 (Front Left)

// Shift register bit positions for the HW-130 Shield
const int M1_A = 2; const int M1_B = 3;
const int M2_A = 1; const int M2_B = 4;
const int M3_A = 5; const int M3_B = 7;
const int M4_A = 0; const int M4_B = 6;

// Custom Direction Commands
#define FORWARD 1
#define RELEASE 3

byte shiftData = 0; // Holds the current state of all motors
char lastCommand = ' '; // Tracks the last command to manage serial feedback

void setup() {
  // MUST MATCH YOUR LABVIEW BAUD RATE
  Serial.begin(9600); 
  
  pinMode(MOTOR_LATCH, OUTPUT); pinMode(MOTOR_CLK, OUTPUT);
  pinMode(MOTOR_ENABLE, OUTPUT); pinMode(MOTOR_DATA, OUTPUT);
  pinMode(MOTOR1_PWM, OUTPUT); pinMode(MOTOR2_PWM, OUTPUT);
  pinMode(MOTOR3_PWM, OUTPUT); pinMode(MOTOR4_PWM, OUTPUT);

  digitalWrite(MOTOR_ENABLE, LOW); // Activate the HW-130 driver chips
  
  // Set speed to Max Power (255)
  analogWrite(MOTOR1_PWM, 255);
  analogWrite(MOTOR2_PWM, 255);
  analogWrite(MOTOR3_PWM, 255);
  analogWrite(MOTOR4_PWM, 255);

  // Initial connection printout
  Serial.println("ROBOT ONLINE - DAQ Control Ready");
}

void loop() {
  // Check if LabVIEW's decision logic has sent a character down the serial line
  if (Serial.available() > 0) {
    char incomingByte = Serial.read(); 
    
    // Only execute actions and print updates when LabVIEW transitions to a NEW command
    if (incomingByte != lastCommand) {
      
      if (incomingByte == 'F' || incomingByte == 'f') {
        moveForward();
        Serial.println("Moving FORWARD"); // This updates your read buffer string
        lastCommand = incomingByte;
      } 
      else if (incomingByte == 'S' || incomingByte == 's') {
        stopRobot();
        Serial.println("STOPPED");        // This updates your read buffer string
        lastCommand = incomingByte;
      }
    }
  }
}

// --- MOVEMENT FUNCTIONS ---
void moveForward() {
  runMotor(1, FORWARD); runMotor(2, FORWARD); 
  runMotor(3, FORWARD); runMotor(4, FORWARD);
}

void stopRobot() {
  runMotor(1, RELEASE); runMotor(2, RELEASE); 
  runMotor(3, RELEASE); runMotor(4, RELEASE);
}

// --- LOW-LEVEL SHIFT REGISTER LOGIC FOR HW-130 ---
void runMotor(int motorNum, int dir) {
  int a_bit, b_bit;
  if (motorNum == 1) { a_bit = M1_A; b_bit = M1_B; }
  else if (motorNum == 2) { a_bit = M2_A; b_bit = M2_B; }
  else if (motorNum == 3) { a_bit = M3_A; b_bit = M3_B; }
  else if (motorNum == 4) { a_bit = M4_A; b_bit = M4_B; }
  else return;

  if (dir == FORWARD) {
    bitSet(shiftData, a_bit);
    bitClear(shiftData, b_bit);
  } else if (dir == RELEASE) {
    bitClear(shiftData, a_bit);
    bitClear(shiftData, b_bit);
  }
  
  digitalWrite(MOTOR_LATCH, LOW);
  delayMicroseconds(2);
  shiftOut(MOTOR_DATA, MOTOR_CLK, MSBFIRST, shiftData);
  delayMicroseconds(2);
  digitalWrite(MOTOR_LATCH, HIGH);
}