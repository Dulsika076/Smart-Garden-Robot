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
#define BACKWARD 2
#define RELEASE 3

byte shiftData = 0; 
char lastCommand = ' '; 

void setup() {
  Serial.begin(9600); 
  
  pinMode(MOTOR_LATCH, OUTPUT); pinMode(MOTOR_CLK, OUTPUT);
  pinMode(MOTOR_ENABLE, OUTPUT); pinMode(MOTOR_DATA, OUTPUT);
  pinMode(MOTOR1_PWM, OUTPUT); pinMode(MOTOR2_PWM, OUTPUT);
  pinMode(MOTOR3_PWM, OUTPUT); pinMode(MOTOR4_PWM, OUTPUT);

  digitalWrite(MOTOR_ENABLE, LOW); 
  
  // High power profile to handle skid-steering turns
  analogWrite(MOTOR1_PWM, 255);
  analogWrite(MOTOR2_PWM, 255);
  analogWrite(MOTOR3_PWM, 255);
  analogWrite(MOTOR4_PWM, 255);

  Serial.println("ROBOT ONLINE - Multi-Direction Mode");
}

void loop() {
  if (Serial.available() > 0) {
    char incomingByte = Serial.read(); 
    
    if (incomingByte != lastCommand) {
      if (incomingByte == 'F' || incomingByte == 'f') {
        moveForward();
        Serial.println("Moving FORWARD");
        lastCommand = incomingByte;
      } 
      else if (incomingByte == 'B' || incomingByte == 'b') {
        stopRobot();
        delay(200); // Safety pause before reversing current
        moveBackward();
        Serial.println("Moving BACKWARD");
        lastCommand = incomingByte;
      } 
      else if (incomingByte == 'L' || incomingByte == 'l') {
        stopRobot();
        delay(200);
        turnLeft();
        Serial.println("Turning LEFT");
        lastCommand = incomingByte;
      } 
      else if (incomingByte == 'R' || incomingByte == 'r') {
        stopRobot();
        delay(200);
        turnRight();
        Serial.println("Turning RIGHT");
        lastCommand = incomingByte;
      } 
      else if (incomingByte == 'S' || incomingByte == 's') {
        stopRobot();
        Serial.println("STOPPED");
        lastCommand = incomingByte;
      }
    }
  }
}

// --- DIRECTION FUNCTIONS ---
void moveForward() {
  runMotor(1, FORWARD); runMotor(2, FORWARD); 
  runMotor(3, FORWARD); runMotor(4, FORWARD);
}

void moveBackward() {
  runMotor(1, BACKWARD); runMotor(2, BACKWARD); 
  runMotor(3, BACKWARD); runMotor(4, BACKWARD);
}

void turnLeft() {
  runMotor(1, FORWARD);  runMotor(2, FORWARD); 
  runMotor(3, BACKWARD); runMotor(4, BACKWARD);
}

void turnRight() {
  runMotor(1, BACKWARD); runMotor(2, BACKWARD); 
  runMotor(3, FORWARD);  runMotor(4, FORWARD);
}

void stopRobot() {
  runMotor(1, RELEASE); runMotor(2, RELEASE); 
  runMotor(3, RELEASE); runMotor(4, RELEASE);
}

// --- LOW-LEVEL REGISTER CONVERSION ---
void runMotor(int motorNum, int dir) {
  int a_bit, b_bit;
  if (motorNum == 1) { a_bit = M1_A; b_bit = M1_B; }
  else if (motorNum == 2) { a_bit = M2_A; b_bit = M2_B; }
  else if (motorNum == 3) { a_bit = M3_A; b_bit = M3_B; }
  else if (motorNum == 4) { a_bit = M4_A; b_bit = M4_B; }
  else return;

  if (dir == FORWARD) { bitSet(shiftData, a_bit); bitClear(shiftData, b_bit); } 
  else if (dir == BACKWARD) { bitClear(shiftData, a_bit); bitSet(shiftData, b_bit); } 
  else if (dir == RELEASE) { bitClear(shiftData, a_bit); bitClear(shiftData, b_bit); }
  
  digitalWrite(MOTOR_LATCH, LOW);
  shiftOut(MOTOR_DATA, MOTOR_CLK, MSBFIRST, shiftData);
  digitalWrite(MOTOR_LATCH, HIGH);
}