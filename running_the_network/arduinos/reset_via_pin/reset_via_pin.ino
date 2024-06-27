/*
THE CODE FOR THE UNO THAT TRIGGERS THE RESET PIN WHEN NECESSARY.

---- version number: v1.0 ----
---- version date: 2024-02-23 ----

** requires node_ts_only version: v2.0 ** 

Always make sure base station and node versions match!

authors: lokubo, mgoelz

email: mgoelz@spg.tu-darmstadt.de

// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %

// Define the LED pin
const int ledPin = 2;
char serialInput;
int resetPin = 12;
void setup() {
  // Set the LED pin as an output
  digitalWrite(resetPin, HIGH);
  pinMode(ledPin, OUTPUT);
  pinMode(resetPin, OUTPUT);

  // Start serial communication
  Serial.begin(9600);
  //Serial.println("The rebooter's serial was (re)started");
  digitalWrite(ledPin, HIGH);   // Turn off the LED
}

void loop() {
  // Check if there is any serial data available
  while (!Serial.available()) {}  // Wait for input
  // Read the incoming character
  serialInput = Serial.parseInt();
    
  if (serialInput == 1) {
    // Toggle the LED state
      Serial.println("rebooting");
      digitalWrite(ledPin, LOW);   // Turn off the LED
      digitalWrite(resetPin, LOW);
      delay(2000);
      digitalWrite(resetPin, HIGH);
      digitalWrite(ledPin, HIGH);  // Turn on the LED
      Serial.println("rebooted!");
  }
}
