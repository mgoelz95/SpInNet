/*
WSN BASE STATION CODE WITH ONLY TEST STATISTICS (NO P-VALUES)
---- version number: v2.1 ----
---- version date: 2024-05-06 ----

** requires node_ts_only version: v2.0 ** 

Always make sure base station and node versions match!

authors: lokubo, mgoelz

email: mgoelz@spg.tu-darmstadt.de

Important notes:
-- WORDING --:
  - variable names containing "time", "duration": refer to absolute time in [milliseconds]
  - variable names containing "epoch", "length": refers to relative time (epoch: no unit, length: in [epochs])
*/
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
// IMPORTS
// % % % % % % % % % % % % % % % % % % % % % % % % %
#include <ArduinoBLE.h>
#include <string.h>
#include <math.h>
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 4% % % % % % % % % % % % % % % % % % % % % % % % % % % % %
// PREPARATION: PARAMETER DEFINITIONS AND INITIALIZATIONS
// % % % % % % % % % % % % % % % % % % % % % % % % %
// User-specified parameters: These parameters may be changed by the user
///////////////////////
// if in recovery mode, no new instructions are transmitted! Only data is received. So make sure to set this false, if you want to transmit new parameters
bool recoverDataMode;

unsigned short tsWindowLength;           // Length of test statistic window
unsigned short tsEpochBufferDuration;  // {epochDuration} = {tsWindowLength} * {sensorSamplingTimeInterval} + {tsEpochBufferDuration}

uint8_t startRecordingEpoch;  // start recording at this epoch. choose large enough,
// so that BS has chance to loop through all nodes and update their parameters

// parameters related to the BLE connection
unsigned long waitingTimeBeforeReconnect;                  // wait this long before connecting a node again
unsigned short waitThisTimeBeforeSkippingNodeConnection;   // if we waited this long without establishing a connection, skip to the next node
unsigned long deathWarningAfterThisTime;                // after this duration with connection to a node, the console warns about potential death of the node
unsigned long transmitDataRecordedDuringThisTimeWindow;  // equals to 1h minutes

unsigned short precisionTS;
unsigned long combinationTransmitDataDuringWindowAndPrecisionTS;
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Define test statistic, data handling and transmission-related parameters
///////////////////////
unsigned short sensorSamplingTimeInterval;  // time interval between sampling the sensors
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Initializations
/////////////////////////
// for catching weird things from the serial input
unsigned long serialBuffer;

// initialization of parameters related to synchronization between node and BS
unsigned long timeNow;                   // the current local time in [ms]
unsigned long globTime;                  // stores the global time in [ms]
unsigned long globTimeInput;
unsigned long currentEpochIndex;         // the index of the current TS epoch
unsigned long updatedEpochIndex;         // The updated epoch index with the most recent time. Needed to see changes
unsigned long locTimeAtStartOfGlobTime;  // the local time corresponding to the global starting time
unsigned long millisWhenGlobalTimeInputWasReceived;
unsigned long timeSinceGlobalTimeInput;
unsigned int tsEpochDuration;

unsigned long locTimeAtStartOfTransCycle;  // the local time corresponding to the start of the transmission cycle
//(one cycle = one time trying to establish connection to all nodes)

const int totalNumberNodes = 54;
// initialization of parameters related to the transmission of data from node to BS
// node identifiers

String nodes[totalNumberNodes] = {
  "Node001", "Node002", "Node003", "Node004", "Node005", "Node006", "Node007", "Node008", "Node009", "Node010",
  "Node011", "Node012", "Node013", "Node014", "Node015", "Node016", "Node017", "Node018", "Node019", "Node020",
  "Node021", "Node022", "Node023", "Node024", "Node025", "Node026", "Node027", "Node028", "Node029", "Node030",
  "Node031", "Node032", "Node033", "Node034", "Node035", "Node036", "Node037", "Node038", "Node039", "Node040",
  "Node041", "Node042", "Node043", "Node044", "Node045", "Node046", "Node047", "Node048", "Node049", "Node050",
  "Node051", "Node052", "Node053", "Node054"
};


bool yetToTriggerNewInstructionsAtNode[totalNumberNodes] = {
  true, true, true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true, true, true,
  true, true, true, true, true, true, true, true, true, true,
  true, true, true, true
};


bool thisNodeMightHaveDied[totalNumberNodes] = {
  false, false, false, false, false, false, false, false,
  false, false, false, false, false, false, false, false,
  false, false, false, false, false, false, false, false,
  false, false, false, false, false, false, false, false,
  false, false, false, false, false, false, false, false,
  false, false, false, false
};

long lastTimeConnectedToNode[totalNumberNodes] = {
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
  0, 0, 0, 0
};

unsigned char loopNodes = totalNumberNodes;  // loop over this many nodes
unsigned short numNodesAlreadyTriggered = 0;
bool someoneMightBeDead = false;

String connectToNodeWithName;                         // identifier of intended node to connect to
unsigned short connectToNodeWithIndex;            // index of node currently establishing connection to to access its identifier in array of node identifiers
unsigned long lastTimeNodeIDToConnectWithChanged = 0;  // last time the node we are trying to connect to was changed
unsigned long lastTimeConnectionToAnyNode = 0;         // last time a connection to any node was established
unsigned long lastBLERestartTime = 0;  // when BLE was last restarted
unsigned int restartBLEAfterTime = 100000;  // restart BLE again after this time
uint8_t yetToTriggerNewInstructionsAtThisNode = 0;    // If new instructions for this node we try to connect to is to be triggered.

bool changeInTransQueueIndex = false;  // indicates reception of new element from transmission queue

const uint32_t lastSuccessfullyAtBSReceivedQueueIndexStartValue = 1000000;  // ridiculuously large
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Define handles to refer to services and characteristics better code readability
/////////////////////////
//TODO: ADJUST UUID TO BLE STANDARD!
#define BLE_UUID_ENVIRONMENT_SENSING_SERVICE          "08966de4-67e9-458f-9697-b10ddd3c3d89"
#define BLE_UUID_MEASUREMENT_SENDING_SERVICE          "5098b505-7b32-4178-9040-7073fe9b3435"
#define BLE_UUID_TEMP_PREV0_EPOCH                     "8e006c26-cf24-4eae-992c-dc0132fc637b"
#define BLE_UUID_HUMID_PREV0_EPOCH                    "dcf4edc4-23d1-45e8-8bbe-ee450802fe9d"
#define BLE_UUID_TEMP_PREV1_EPOCH                     "d044d836-ec23-4e32-a7ab-de7a05cefdd5"
#define BLE_UUID_HUMID_PREV1_EPOCH                    "f7ff6d21-d7c3-4a3d-b718-c734428196ca"
#define BLE_UUID_TEMP_PREV2_EPOCH                     "243dd0fe-b17b-4209-b004-adbe344347e0"
#define BLE_UUID_HUMID_PREV2_EPOCH                    "1159af56-fa8d-4d47-b001-13c4a2f64d02"
#define BLE_UUID_TEMP_PREV3_EPOCH                     "3b360be3-0e8c-4776-b488-b54ee783d4a0"
#define BLE_UUID_HUMID_PREV3_EPOCH                    "b1c09952-1c85-402f-b83e-b67980d09fc3"
#define BLE_UUID_TEMP_PREV4_EPOCH                     "b2751ca3-2d71-4504-a984-2e9d49510dcd"
#define BLE_UUID_HUMID_PREV4_EPOCH                    "47374d0e-54c0-409d-a26f-8c37e456b973"
#define BLE_UUID_TEMP_PREV5_EPOCH                     "753da6ed-77fa-4e5c-aed1-478ea9e8d7e9"
#define BLE_UUID_HUMID_PREV5_EPOCH                    "80771f44-d417-4012-b3ec-31126eb472d1"
#define BLE_UUID_ACK                                  "161f993e-b869-406c-91b4-cad683f27f80"
#define BLE_UUID_TIME_GLOBAL                          "6c445da7-b2dc-4564-8a7f-d82945640232"
#define BLE_UUID_QUEUEINDEX                           "d282b749-eb07-4645-83cc-cc5db454a542"
#define BLE_UUID_GLOBAL_TIME_INDEX                    "abcd3989-34fe-425f-aac4-07d6e5aa2366"
#define BLE_UUID_START_RECORDING_INDEX                "8b2b27f6-f520-483b-a900-907c2aa77984"
#define BLE_UUID_TEST_STATISTICS_SAMPLES              "ed249bef-1098-40f1-b6cd-2070bf850648"
#define BLE_UUID_EPOCH_BUFFER_DURATION                "31c6058f-707c-40cf-8390-ee22a4bfce53"
#define BLE_UUID_SENSOR_SAMPLING_TIME_INTERVAL        "a3265cde-cce8-4bd2-8e89-788e34a8acdc"
#define BLE_UUID_TRIGGER_NEW_INSTRUCTIONS             "1bb7b1eb-00c6-49df-b67a-44245cc5b022"
#define BLE_UUID_TEMP_THIS_EPOCH                      "4b5311a8-eeec-45e5-a9b9-dfac0b7ffd0a"
#define BLE_UUID_HUMID_THIS_EPOCH                     "0b290afc-ae8e-4983-bcb0-bd41935ec62d"
#define BLE_UUID_TRANSMIT_TIME_WINDOW                 "21713072-ae4d-4f7a-a896-155ec6779679"
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
// SETUP: DO WHEN BS IS POWERED UP
// % % % % % % % % % % % % % % % % % % % % % % % % %
void setup() {
  Serial.begin(9600);  // specify serial port
  while (!Serial)
    ;  // wait until serial has started up

  // Initialize builtin LEDs for showing things
  pinMode(LEDR, OUTPUT);
  pinMode(LEDG, OUTPUT);
  pinMode(LEDB, OUTPUT);
  turnLEDOff();

  //delay( 10 );

  // initialize the Bluetooth® Low Energy hardware
  BLE.begin();

  confirmBlink(true, false, true, true);  // initialization of sensor and BLE worked

  globTimeInput = getParameterFromSerialInput("globTimeInput", false);
  
  millisWhenGlobalTimeInputWasReceived = millis();  // millis when global time was received
  timeSinceGlobalTimeInput = millis() - millisWhenGlobalTimeInputWasReceived;

  // Interactive setup for recoverDataMode
  recoverDataMode = getParameterFromSerialInput("recoverDataMode", false);
  tsWindowLength = getParameterFromSerialInput("tsWindowLength", false);
  tsEpochBufferDuration = getParameterFromSerialInput("tsEpochBufferDuration", false);
  startRecordingEpoch = getParameterFromSerialInput("startRecordingEpoch", false);
  waitingTimeBeforeReconnect = getParameterFromSerialInput("waitingTimeBeforeReconnect", false);
  waitThisTimeBeforeSkippingNodeConnection = getParameterFromSerialInput("waitThisTimeBeforeSkippingNodeConnection", false);
  deathWarningAfterThisTime = getParameterFromSerialInput("deathWarningAfterThisTime", false);
  transmitDataRecordedDuringThisTimeWindow = getParameterFromSerialInput("transmitDataRecordedDuringThisTimeWindow", false);
  precisionTS = getParameterFromSerialInput("precisionTS", false);
  sensorSamplingTimeInterval = getParameterFromSerialInput("sensorSamplingTimeInterval", false);

  connectToNodeWithIndex = getParameterFromSerialInput("connectToNodeWithIndex", false);

  // Setup with conditions from python code
  /*globTimeInput = 1000;
  recoverDataMode = 1;
  tsWindowLength = 5;
  tsEpochBufferDuration = 100;
  startRecordingEpoch = 5;
  waitingTimeBeforeReconnect = 10000;
  waitThisTimeBeforeSkippingNodeConnection = 10000;
  deathWarningAfterThisTime = 1800000;
  transmitDataRecordedDuringThisTimeWindow = 3600000;
  precisionTS = 9;
  sensorSamplingTimeInterval = 500;

  connectToNodeWithIndex = 0;*/
  tsEpochDuration = tsWindowLength * sensorSamplingTimeInterval + tsEpochBufferDuration;

  if (Serial) {
    Serial.println("Started searching for nodes...");
  }

  if (recoverDataMode){
    turnTriggerOff();  // turning triggering of new instructions off. To recover data after BS stalled
  }

  connectToNodeWithName = nodes[connectToNodeWithIndex];  // start by connecting to node 1
  yetToTriggerNewInstructionsAtThisNode = yetToTriggerNewInstructionsAtNode[connectToNodeWithIndex];
  // initialize starting times
  locTimeAtStartOfGlobTime = globalMillis();    // initialize global starting time with current time
  locTimeAtStartOfTransCycle = globalMillis();  // initialize starting time of this transmission cycle with current time
  // global time initialization
  globTime = globalMillis(); // MAYBE CHANGE HERE TO GET GLOBAL TIME CORRECT
  currentEpochIndex = floor(globTime / tsEpochDuration);
  combinationTransmitDataDuringWindowAndPrecisionTS = transmitDataRecordedDuringThisTimeWindow + precisionTS;
}
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %

// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
// LOOP: REPEAT
// % % % % % % % % % % % % % % % % % % % % % % % % %
void loop() {
  // restart BLE module if somehow not able to connect to anything anymore
  /**if ((millis() - lastTimeConnectionToAnyNode) > (10 * waitThisTimeBeforeSkippingNodeConnection) && (millis() - lastBLERestartTime) > restartBLEAfterTime ){
    NVIC_SystemReset() ;
    if (Serial){
      Serial.println("Restarted!");
    }
    lastBLERestartTime = millis();
  }
  */
  //timeNow = globalMillis();
  globTime = globalMillis();  // global time is current local time - local time at start of global time
  updatedEpochIndex = floor(globTime / tsEpochDuration);
  // If there was a change in the epoch index, print it on the console for visualization purpose
  if ((currentEpochIndex != updatedEpochIndex)) {
    currentEpochIndex = updatedEpochIndex;
    if (Serial) {
      Serial.print("Current time/epoch index: ");
      Serial.print(globTime);
      Serial.print("/");
      Serial.println(currentEpochIndex);
      // Write on Serial output which nodes still have to be triggered
      if (numNodesAlreadyTriggered < loopNodes) {  // make sure that if everything was triggered, we dont end up here anymore
        char localVariableNumAlreadyTriggered = 0;
        Serial.print("Nodes left to trigger: ");
        for (char i = 0; i < loopNodes; i++) {
          if (yetToTriggerNewInstructionsAtNode[i] == true) {
            Serial.print(nodes[i]);
            Serial.print(" ");
          } else {
            localVariableNumAlreadyTriggered++;
          }
        }
        Serial.println("");
        if (localVariableNumAlreadyTriggered >= loopNodes) {
          numNodesAlreadyTriggered = loopNodes;
        }
        if (numNodesAlreadyTriggered == loopNodes && !recoverDataMode){
          Serial.println("All have been triggered!");
        }
      }
      // THIS IS COMMENTED OUT BECUASE DOESNT WORK PROPERLY CURRENTLY
      /*
      someoneMightBeDead = false;
      for (char i = 0; i < loopNodes; i++) {
        if (thisNodeMightHaveDied[i]) {
          someoneMightBeDead = true;
          break;
        }
      }
      if (someoneMightBeDead) {
        Serial.print("Might be dead: ");
        for (char i = 0; i < loopNodes; i++) {
          if (thisNodeMightHaveDied[i]) {
            Serial.print(nodes[i]);
            Serial.print(" ");
          }
        }
        Serial.println("");
      }
      */
    }
  }

  if (globTime - lastTimeNodeIDToConnectWithChanged >= waitThisTimeBeforeSkippingNodeConnection) {
    if (Serial) {
      /*
      Serial.print("Skipped ");
      Serial.print(connectToNodeWithName);
      Serial.print(", now scanning for ");
      */
    }
    connectToNodeWithIndex = (connectToNodeWithIndex + 1) % loopNodes;  // modulo necessary to reset to 1 after 60 nodes were visited!
    //connectToNodeWithIndex = 38;
    connectToNodeWithName = nodes[connectToNodeWithIndex];
    yetToTriggerNewInstructionsAtThisNode = yetToTriggerNewInstructionsAtNode[connectToNodeWithIndex];
    // if all nodes were visited in this cycle, reset cycle starting time
    if (connectToNodeWithIndex == 0) {
      locTimeAtStartOfTransCycle = globalMillis();
    }
    if (Serial) {
      //Serial.println(connectToNodeWithName);
    }
    lastTimeNodeIDToConnectWithChanged = globalMillis();
  }

  // check if a peripheral has been discovered
  BLE.scanForName(connectToNodeWithName);


  if (globTime - lastTimeConnectedToNode[connectToNodeWithIndex] > waitingTimeBeforeReconnect || lastTimeConnectedToNode[connectToNodeWithIndex] == 0) {
    BLEDevice nodeConnected = BLE.available();

    if (nodeConnected) {
      BLE.stopScan();
      // discovered a peripheral, print out address, local name, and advertised service UUID
      if (Serial) {
        // Serial.print("Connection to node ");
        // Serial.print(nodeConnected.localName());
        // Serial.print(" | ");
        // Serial.print(nodeConnected.address());
        // Serial.print(" | ");
        // Serial.print(nodeConnected.advertisedServiceUuid());
        // Serial.println();
      }
      if (nodeConnected.connect()) {
        if (Serial) {
          Serial.print(connectToNodeWithName);
          Serial.print(": connected --");
        }
        if (!nodeConnected.discoverAttributes()) {
          if (Serial) {
            Serial.println(" attribute discovery failed!");
          }
          return;
        } else {
          if (Serial) {
            Serial.print(" attributes discovered -- ");
          }
          getAndVisualizeTempHumid(nodeConnected);
        }
        if (nodeConnected.disconnect()) {
          if (Serial) {
            Serial.println("Disconnected!");
          }
        }
        // TODO: What was here previously has been removed, check if this was needed at all
      } else {
        if (Serial) {
          Serial.println("Failed to connect!");
        }
        return;
      }
    }

    if (globTime - lastTimeConnectedToNode[connectToNodeWithIndex] > deathWarningAfterThisTime) {
      thisNodeMightHaveDied[connectToNodeWithIndex] = true;
    } else {
      thisNodeMightHaveDied[connectToNodeWithIndex] = false;
    }
  }
}

// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %
// AUXILIARY FUNCTIONS
// % % % % % % % % % % % % % % % % % % % % % % % % %

void getAndVisualizeTempHumid(BLEDevice peripheral) {
  unsigned long fullDataTempFromPrevEpochChar0 = 0;
  unsigned long fullDataTempFromPrevEpochChar1 = 0;
  unsigned long fullDataTempFromPrevEpochChar2 = 0;
  unsigned long fullDataTempFromPrevEpochChar3 = 0;
  unsigned long fullDataTempFromPrevEpochChar4 = 0;
  unsigned long fullDataTempFromPrevEpochChar5 = 0;
  long temperatureForIndex;
  long prevFullDataTempFromPrevEpochChar0 = 0;
  long prevFullDataTempFromPrevEpochChar1 = 0;
  long prevFullDataTempFromPrevEpochChar2 = 0;
  long prevFullDataTempFromPrevEpochChar3 = 0;
  long prevFullDataTempFromPrevEpochChar4 = 0;
  long prevFullDataTempFromPrevEpochChar5 = 0;
  long prevFullDataTempFromThisEpochChar;
  long prevEpochTempIdx0 = 0;
  long prevEpochTempIdx1 = 0;
  long prevEpochTempIdx2 = 0;
  long prevEpochTempIdx3 = 0;
  long prevEpochTempIdx4 = 0;
  long prevEpochTempIdx5 = 0;
  long thisEpochTempIdx;
  unsigned long fullDataHumidFromPrevEpochChar0 = 0;
  unsigned long fullDataHumidFromPrevEpochChar1 = 0;
  unsigned long fullDataHumidFromPrevEpochChar2 = 0;
  unsigned long fullDataHumidFromPrevEpochChar3 = 0;
  unsigned long fullDataHumidFromPrevEpochChar4 = 0;
  unsigned long fullDataHumidFromPrevEpochChar5 = 0;
  long humidityForIndex;
  long prevFullDataHumidFromPrevEpochChar0 = 0;
  long prevFullDataHumidFromPrevEpochChar1 = 0;
  long prevFullDataHumidFromPrevEpochChar2 = 0;
  long prevFullDataHumidFromPrevEpochChar3 = 0;
  long prevFullDataHumidFromPrevEpochChar4 = 0;
  long prevFullDataHumidFromPrevEpochChar5 = 0;
  long prevFullDataHumidFromThisEpochChar;
  long prevEpochHumidIdx0 = 0;
  long prevEpochHumidIdx1 = 0;
  long prevEpochHumidIdx2 = 0;
  long prevEpochHumidIdx3 = 0;
  long prevEpochHumidIdx4 = 0;
  long prevEpochHumidIdx5 = 0;
  long thisEpochHumidIdx;
  unsigned long DataFromLocalTimeIndexCharacteristic;
  long prevDataFromLocalTimeIndexCharacteristic;
  long thisEpochIndex;
  short transQueueIndex = 0;
  short prevTransQueueIndex = 0;
  float tmpVal;
  float humVal;
  unsigned long fullDataTempFromThisEpochChar;
  unsigned long fullDataHumidFromThisEpochChar;

  if (!peripheral.connected()) {
    if (Serial) {
      Serial.println("Peripheral is not connected! Cannot get anything!!");
    }
    return;  // if connection was not possible, make sure to get out
  }

  // NEed to define charactersitics for everything that we want to exchange with the node via BLE.
  BLECharacteristic globTimeCharacteristic = peripheral.characteristic(BLE_UUID_TIME_GLOBAL);

  BLECharacteristic tempPrev0EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV0_EPOCH);
  BLECharacteristic humidPrev0EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV0_EPOCH);
  BLECharacteristic tempPrev1EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV1_EPOCH);
  BLECharacteristic humidPrev1EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV1_EPOCH);
  BLECharacteristic tempPrev2EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV2_EPOCH);
  BLECharacteristic humidPrev2EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV2_EPOCH);
  BLECharacteristic tempPrev3EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV3_EPOCH);
  BLECharacteristic humidPrev3EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV3_EPOCH);
  BLECharacteristic tempPrev4EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV4_EPOCH);
  BLECharacteristic humidPrev4EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV4_EPOCH);
  BLECharacteristic tempPrev5EpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_PREV5_EPOCH);
  BLECharacteristic humidPrev5EpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_PREV5_EPOCH);
  BLECharacteristic tempThisEpochCharacteristic = peripheral.characteristic(BLE_UUID_TEMP_THIS_EPOCH);
  BLECharacteristic humidThisEpochCharacteristic = peripheral.characteristic(BLE_UUID_HUMID_THIS_EPOCH);

  BLECharacteristic queueIndexCharacteristic = peripheral.characteristic(BLE_UUID_QUEUEINDEX);
  BLECharacteristic lastSuccessfullyAtBSReceivedQueueIndexCharacteristic = peripheral.characteristic(BLE_UUID_ACK);
  BLECharacteristic localTimeIndexCharacteristic = peripheral.characteristic(BLE_UUID_GLOBAL_TIME_INDEX);

  BLECharacteristic tsWindowLengthCharacteristic = peripheral.characteristic(BLE_UUID_TEST_STATISTICS_SAMPLES);
  BLECharacteristic tsEpochBufferDurationCharacteristic = peripheral.characteristic(BLE_UUID_EPOCH_BUFFER_DURATION);
  BLECharacteristic sensorSamplingTimeIntervalCharacteristic = peripheral.characteristic(BLE_UUID_SENSOR_SAMPLING_TIME_INTERVAL);

  BLECharacteristic startRecordingIndexCharacteristic = peripheral.characteristic(BLE_UUID_START_RECORDING_INDEX);
  BLECharacteristic triggerNewInstructionsCharacteristic = peripheral.characteristic(BLE_UUID_TRIGGER_NEW_INSTRUCTIONS);

  BLECharacteristic transmitDataRecordedDuringThisTimeWindowCharacteristic = peripheral.characteristic(BLE_UUID_TRANSMIT_TIME_WINDOW);

  bool foundAllCharacteristics = checkIfAllCharacteristicsExist(
    globTimeCharacteristic, queueIndexCharacteristic, lastSuccessfullyAtBSReceivedQueueIndexCharacteristic,
    startRecordingIndexCharacteristic, tsWindowLengthCharacteristic, triggerNewInstructionsCharacteristic, tempThisEpochCharacteristic, humidThisEpochCharacteristic,
    transmitDataRecordedDuringThisTimeWindowCharacteristic);

  if (foundAllCharacteristics) {
    if (Serial) {
      Serial.println("found all characteristics!");
    }
  } else {
    peripheral.disconnect();  // Disconnect if characteristics were missing.
    return;
  }

  lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(lastSuccessfullyAtBSReceivedQueueIndexStartValue);

  // Before connection, no change can have taken place
  changeInTransQueueIndex = false;

  String dat_str1;
  String dat_str2;
  String dat_str3;
  String dat_str4;
  String dat_str5;
  String dat_str6;
  String dat_str7;

  // the following is repeated as long as the peripherial stays connected
  while (peripheral.connected()) {
    if (yetToTriggerNewInstructionsAtThisNode) {
      if (Serial) {
         Serial.println("Triggering reception of null parameters at the node ...");
      }
    }

    globTimeCharacteristic.writeValue(globTime);  // tell the node the current global time

    // then update those that cannot trigger anything
    startRecordingIndexCharacteristic.writeValue(startRecordingEpoch);  // tell node when to start recording
    transmitDataRecordedDuringThisTimeWindowCharacteristic.writeValue(combinationTransmitDataDuringWindowAndPrecisionTS);

    // then those that can trigger
    tsWindowLengthCharacteristic.writeValue(tsWindowLength);                          // tell node how many samples per test statistics are to be used
    tsEpochBufferDurationCharacteristic.writeValue(tsEpochBufferDuration);            // tell node epoch buffer duration
    sensorSamplingTimeIntervalCharacteristic.writeValue(sensorSamplingTimeInterval);  // tell node duration between two times sensor is sampled

    if (!recoverDataMode){ // if we are in recover mode, new instructions are not triggered
      triggerNewInstructionsCharacteristic.writeValue(yetToTriggerNewInstructionsAtThisNode);  // trigger a change if this node has not received new instructions yet

      triggerNewInstructionsCharacteristic.readValue(yetToTriggerNewInstructionsAtThisNode);

      if (!yetToTriggerNewInstructionsAtThisNode) {
        yetToTriggerNewInstructionsAtNode[connectToNodeWithIndex] = false;
      }
    }

    ////////////////////////////////////
    // Probe transmission characteristics
    // get temperature, humidity p-values and test statistics as well as current queue index (of transmission queue) from the node
    tempPrev5EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar5);
    if (fullDataTempFromPrevEpochChar5 != prevFullDataTempFromPrevEpochChar5) {
      prevFullDataTempFromPrevEpochChar5 = fullDataTempFromPrevEpochChar5;
      prevEpochTempIdx5 = fullDataTempFromPrevEpochChar5 % 100;
    }
    
    tempPrev4EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar4);
    if (fullDataTempFromPrevEpochChar4 != prevFullDataTempFromPrevEpochChar4) {
      prevFullDataTempFromPrevEpochChar4 = fullDataTempFromPrevEpochChar4;
      prevEpochTempIdx4 = fullDataTempFromPrevEpochChar4 % 100;
    }
    
    tempPrev3EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar3);
    if (fullDataTempFromPrevEpochChar3 != prevFullDataTempFromPrevEpochChar3) {
      prevFullDataTempFromPrevEpochChar3 = fullDataTempFromPrevEpochChar3;
      prevEpochTempIdx3 = fullDataTempFromPrevEpochChar3 % 100;
    }

    tempPrev2EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar2);
    if (fullDataTempFromPrevEpochChar2 != prevFullDataTempFromPrevEpochChar2) {
      prevFullDataTempFromPrevEpochChar2 = fullDataTempFromPrevEpochChar2;
      prevEpochTempIdx2 = fullDataTempFromPrevEpochChar2 % 100;
    }

    tempPrev1EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar1);
    if (fullDataTempFromPrevEpochChar1 != prevFullDataTempFromPrevEpochChar1) {
      prevFullDataTempFromPrevEpochChar1 = fullDataTempFromPrevEpochChar1;
      prevEpochTempIdx1 = fullDataTempFromPrevEpochChar1 % 100;
      //Serial.print("\n : prevEpochTempIdx1: ");
      //Serial.print(prevEpochTempIdx1);
    }
    //Serial.print("\n : prevEpochTempIdx1: ");
    //Serial.print(prevEpochTempIdx1);

    tempPrev0EpochCharacteristic.readValue(fullDataTempFromPrevEpochChar0);
    if (fullDataTempFromPrevEpochChar0 != prevFullDataTempFromPrevEpochChar0) {
      prevFullDataTempFromPrevEpochChar0 = fullDataTempFromPrevEpochChar0;
      prevEpochTempIdx0 = fullDataTempFromPrevEpochChar0 % 100;
    }

    tempThisEpochCharacteristic.readValue(fullDataTempFromThisEpochChar);
    if (fullDataTempFromThisEpochChar != prevFullDataTempFromThisEpochChar) {
      prevFullDataTempFromThisEpochChar = fullDataTempFromThisEpochChar;
      thisEpochTempIdx = fullDataTempFromThisEpochChar % 100;
    }

    humidPrev5EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar5);
    if (fullDataHumidFromPrevEpochChar5 != prevFullDataHumidFromPrevEpochChar5) {
      prevFullDataHumidFromPrevEpochChar5 = fullDataHumidFromPrevEpochChar5;
      prevEpochHumidIdx5 = fullDataHumidFromPrevEpochChar5 % 100;
    }
    
    humidPrev4EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar4);
    if (fullDataHumidFromPrevEpochChar4 != prevFullDataHumidFromPrevEpochChar4) {
      prevFullDataHumidFromPrevEpochChar4 = fullDataHumidFromPrevEpochChar4;
      prevEpochHumidIdx4 = fullDataHumidFromPrevEpochChar4 % 100;
    }

    humidPrev3EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar3);
    if (fullDataHumidFromPrevEpochChar3 != prevFullDataHumidFromPrevEpochChar3) {
      prevFullDataHumidFromPrevEpochChar3 = fullDataHumidFromPrevEpochChar3;
      prevEpochHumidIdx3 = fullDataHumidFromPrevEpochChar3 % 100;
    }

    humidPrev2EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar2);
    if (fullDataHumidFromPrevEpochChar2 != prevFullDataHumidFromPrevEpochChar2) {
      prevFullDataHumidFromPrevEpochChar2 = fullDataHumidFromPrevEpochChar2;
      prevEpochHumidIdx2 = fullDataHumidFromPrevEpochChar2 % 100;
    }

    humidPrev1EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar1);
    if (fullDataHumidFromPrevEpochChar1 != prevFullDataHumidFromPrevEpochChar1) {
      prevFullDataHumidFromPrevEpochChar1 = fullDataHumidFromPrevEpochChar1;
      prevEpochHumidIdx1 = fullDataHumidFromPrevEpochChar1 % 100;
      //Serial.print("\n prevEpochHumidIdx1: ");
      //Serial.print(prevEpochHumidIdx1);
    }
    //Serial.print("\n prevEpochHumidIdx1: ");
    //erial.print(prevEpochHumidIdx1);

    humidPrev0EpochCharacteristic.readValue(fullDataHumidFromPrevEpochChar0);
    if (fullDataHumidFromPrevEpochChar0 != prevFullDataHumidFromPrevEpochChar0) {
      prevFullDataHumidFromPrevEpochChar0 = fullDataHumidFromPrevEpochChar0;
      prevEpochHumidIdx0 = fullDataHumidFromPrevEpochChar0 % 100;
      //Serial.print("\n : prevEpochHumidIdx0: ");
      //Serial.print(prevEpochHumidIdx0);
    }
    //Serial.print("\n prevEpochHumidIdx0: ");
    //Serial.print(prevEpochHumidIdx0);

    humidThisEpochCharacteristic.readValue(fullDataHumidFromThisEpochChar);
    if (fullDataHumidFromThisEpochChar != prevFullDataHumidFromThisEpochChar) {
      prevFullDataHumidFromThisEpochChar = fullDataHumidFromThisEpochChar;
      thisEpochHumidIdx = fullDataHumidFromThisEpochChar % 100;
    }

    localTimeIndexCharacteristic.readValue(DataFromLocalTimeIndexCharacteristic);
    if (DataFromLocalTimeIndexCharacteristic != prevDataFromLocalTimeIndexCharacteristic) {
      prevDataFromLocalTimeIndexCharacteristic = DataFromLocalTimeIndexCharacteristic;
      thisEpochIndex = DataFromLocalTimeIndexCharacteristic % 100;
    }

    queueIndexCharacteristic.readValue(transQueueIndex);
    if (transQueueIndex != prevTransQueueIndex) {
      changeInTransQueueIndex = true;
    }
    /*Serial.print("\n transQueueIndex: ");
    Serial.println(transQueueIndex);
    Serial.print("\n changeInTransQueueIndex: ");
    Serial.println(changeInTransQueueIndex);*/

    /*Serial.print("\n Parameter \n a: ");
    Serial.print(fullDataTempFromPrevEpochChar0);
    Serial.print(", b: ");
    Serial.print(fullDataHumidFromPrevEpochChar0);
    Serial.print(", c: ");
    Serial.print(fullDataTempFromThisEpochChar);
    Serial.print(", d: ");
    Serial.print(fullDataHumidFromThisEpochChar);
    Serial.print(", e: ");
    Serial.print(DataFromLocalTimeIndexCharacteristic); 
    Serial.print(", f: ");
    Serial.print(fullDataTempFromPrevEpochChar1);
    Serial.print(", g: ");
    Serial.println(fullDataHumidFromPrevEpochChar1);

    Serial.print("\n Index \n a: ");
    Serial.print(prevEpochTempIdx0);
    Serial.print(", b: ");
    Serial.print(prevEpochHumidIdx0);
    Serial.print(", c: ");
    Serial.print(thisEpochTempIdx);
    Serial.print(", d: ");
    Serial.print(thisEpochHumidIdx);
    Serial.print(", e: ");
    Serial.print(thisEpochIndex); 
    Serial.print(", f: ");
    Serial.print(prevEpochTempIdx1);
    Serial.print(", g: ");
    Serial.println(prevEpochHumidIdx1);*/    

    // check if all received all values for the given queue index, depending on the lenght of the queue only certain characteristics are being used
    if (receivedCorrectQueueEntry(fullDataTempFromPrevEpochChar5, fullDataHumidFromPrevEpochChar5,
                                  fullDataTempFromPrevEpochChar4, fullDataHumidFromPrevEpochChar4,
                                  fullDataTempFromPrevEpochChar3, fullDataHumidFromPrevEpochChar3,
                                  fullDataTempFromPrevEpochChar2, fullDataHumidFromPrevEpochChar2,
                                  fullDataTempFromPrevEpochChar1, fullDataHumidFromPrevEpochChar1, fullDataTempFromPrevEpochChar0,
                                  fullDataHumidFromPrevEpochChar0, fullDataTempFromThisEpochChar, fullDataHumidFromThisEpochChar,
                                  prevEpochTempIdx5, prevEpochHumidIdx5, prevEpochTempIdx4, prevEpochHumidIdx4,
                                  prevEpochTempIdx3, prevEpochHumidIdx3, prevEpochTempIdx2, prevEpochHumidIdx2,
                                  prevEpochTempIdx1, prevEpochHumidIdx1, prevEpochTempIdx0, prevEpochHumidIdx0,
                                  thisEpochTempIdx, thisEpochHumidIdx, thisEpochIndex, transQueueIndex) && changeInTransQueueIndex) {
      //Serial.println("entrei na funcao");
      if(transQueueIndex > 6) {
        // A successful transmission requires all indicators to be equal!
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        dat_str3 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar1) + "," + String(fullDataHumidFromPrevEpochChar1) + "," + String(DataFromLocalTimeIndexCharacteristic-2) + "," + String(transQueueIndex-3);
        dat_str4 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar2) + "," + String(fullDataHumidFromPrevEpochChar2) + "," + String(DataFromLocalTimeIndexCharacteristic-3) + "," + String(transQueueIndex-4);
        dat_str5 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar3) + "," + String(fullDataHumidFromPrevEpochChar3) + "," + String(DataFromLocalTimeIndexCharacteristic-4) + "," + String(transQueueIndex-5);
        dat_str6 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar4) + "," + String(fullDataHumidFromPrevEpochChar4) + "," + String(DataFromLocalTimeIndexCharacteristic-5) + "," + String(transQueueIndex-6);
        dat_str7 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar5) + "," + String(fullDataHumidFromPrevEpochChar5) + "," + String(DataFromLocalTimeIndexCharacteristic-6) + "," + String(transQueueIndex-7);

        Serial.println(dat_str1);
        Serial.println(dat_str2);
        Serial.println(dat_str3);
        Serial.println(dat_str4);
        Serial.println(dat_str5);
        Serial.println(dat_str6);
        Serial.println(dat_str7);
        changeInTransQueueIndex = false;
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        if(transQueueIndex == 7){
          transQueueIndex = 0;
        }
      }
      if(transQueueIndex == 6){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        dat_str3 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar1) + "," + String(fullDataHumidFromPrevEpochChar1) + "," + String(DataFromLocalTimeIndexCharacteristic-2) + "," + String(transQueueIndex-3);
        dat_str4 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar2) + "," + String(fullDataHumidFromPrevEpochChar2) + "," + String(DataFromLocalTimeIndexCharacteristic-3) + "," + String(transQueueIndex-4);
        dat_str5 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar3) + "," + String(fullDataHumidFromPrevEpochChar3) + "," + String(DataFromLocalTimeIndexCharacteristic-4) + "," + String(transQueueIndex-5);
        dat_str6 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar4) + "," + String(fullDataHumidFromPrevEpochChar4) + "," + String(DataFromLocalTimeIndexCharacteristic-5) + "," + String(transQueueIndex-6);
        Serial.println(dat_str1);
        Serial.println(dat_str2);
        Serial.println(dat_str3);
        Serial.println(dat_str4);
        Serial.println(dat_str5);
        Serial.println(dat_str6);
        changeInTransQueueIndex = false;
        
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
      if(transQueueIndex == 5){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        dat_str3 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar1) + "," + String(fullDataHumidFromPrevEpochChar1) + "," + String(DataFromLocalTimeIndexCharacteristic-2) + "," + String(transQueueIndex-3);
        dat_str4 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar2) + "," + String(fullDataHumidFromPrevEpochChar2) + "," + String(DataFromLocalTimeIndexCharacteristic-3) + "," + String(transQueueIndex-4);
        dat_str5 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar3) + "," + String(fullDataHumidFromPrevEpochChar3) + "," + String(DataFromLocalTimeIndexCharacteristic-4) + "," + String(transQueueIndex-5);
        Serial.println(dat_str1);
        Serial.println(dat_str2);
        Serial.println(dat_str3);
        Serial.println(dat_str4);
        Serial.println(dat_str5);
        changeInTransQueueIndex = false;
        
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
      if(transQueueIndex == 4){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        dat_str3 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar1) + "," + String(fullDataHumidFromPrevEpochChar1) + "," + String(DataFromLocalTimeIndexCharacteristic-2) + "," + String(transQueueIndex-3);
        dat_str4 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar2) + "," + String(fullDataHumidFromPrevEpochChar2) + "," + String(DataFromLocalTimeIndexCharacteristic-3) + "," + String(transQueueIndex-4);
        Serial.println(dat_str1);
        Serial.println(dat_str2);
        Serial.println(dat_str3);
        Serial.println(dat_str4);
        changeInTransQueueIndex = false;
        
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
      if(transQueueIndex == 3){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        dat_str3 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar1) + "," + String(fullDataHumidFromPrevEpochChar1) + "," + String(DataFromLocalTimeIndexCharacteristic-2) + "," + String(transQueueIndex-3);
        Serial.println(dat_str1);
        Serial.println(dat_str2);
        Serial.println(dat_str3);
        changeInTransQueueIndex = false;
        
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
      if(transQueueIndex == 2){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        dat_str2 = connectToNodeWithName + "," + String(fullDataTempFromPrevEpochChar0) + "," + String(fullDataHumidFromPrevEpochChar0) + "," + String(DataFromLocalTimeIndexCharacteristic-1) + "," + String(transQueueIndex-2);
        Serial.println(dat_str1);
        Serial.println(dat_str2);
        changeInTransQueueIndex = false;
        
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
      if(transQueueIndex == 1){
        prevTransQueueIndex = transQueueIndex;
        dat_str1 = connectToNodeWithName + "," + String(fullDataTempFromThisEpochChar) +  "," + String(fullDataHumidFromThisEpochChar) + "," + String(DataFromLocalTimeIndexCharacteristic) + "," + String(transQueueIndex-1);
        Serial.println(dat_str1);
        changeInTransQueueIndex = false;
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(transQueueIndex);
        transQueueIndex = 0;
      }
    }
    //disconnection is triggered if there is nothing left on the queue
    if(transQueueIndex < 1){
      //Serial.println("Disconnection triggered");
      lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(lastSuccessfullyAtBSReceivedQueueIndexStartValue);
      peripheral.disconnect();
    }
  }

  lastTimeConnectedToNode[connectToNodeWithIndex] = globalMillis();
  lastTimeConnectionToAnyNode = globalMillis();
  if (Serial) {
    Serial.println("Peripheral disconnected");
  }
}

bool checkIfAllCharacteristicsExist(BLECharacteristic globTimeCharacteristic, BLECharacteristic queueIndexCharacteristic,
                                    BLECharacteristic lastSuccessfullyAtBSReceivedQueueIndexCharacteristic,
                                    BLECharacteristic startRecordingIndexCharacteristic, BLECharacteristic tsWindowLengthCharacteristic,
                                    BLECharacteristic triggerNewInstructionsCharacteristic, BLECharacteristic tempThisEpochCharacteristic,
                                    BLECharacteristic humidThisEpochCharacteristic, 
                                    BLECharacteristic transmitDataRecordedDuringThisTimeWindowCharacteristic) {
  if (!globTimeCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have global time characteristic!");
    }
    return false;
  }
  // if (!tempPrevEpochCharacteristic) {
  //   if (Serial) {
  //     Serial.println("Peripheral does not have temperature characteristic!");
  //   }
  //   return false;
  // }
  // if (!humidPrevEpochCharacteristic) {
  //   if (Serial) {
  //     Serial.println("Peripheral does not have humidity characteristic!");
  //   }
  //   return false;
  // }
  if (!queueIndexCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have queueIndexCharacteristic characteristic!");
    }
    return false;
  }
  if (!lastSuccessfullyAtBSReceivedQueueIndexCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have lastSuccessfullyAtBSReceivedQueueIndexCharacteristic characteristic!");
    }
    return false;
  }
  if (!startRecordingIndexCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have startRecordingIndex characteristic!");
    }
    return false;
  }
  if (!tsWindowLengthCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have tsWindowLength characteristic!");
    }
    return false;
  }
  if (!triggerNewInstructionsCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have triggerNewInstructionsCharacteristic characteristic");
    }
    return false;
  }
  if (!tempThisEpochCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have tempThisEpochCharacteristic characteristic");
    }
    return false;
  }
  if (!humidThisEpochCharacteristic) {
    if (Serial) {
      Serial.println("Peripheral does not have humidThisEpochCharacteristic characteristic");
    }
    return false;
  }
  if (!transmitDataRecordedDuringThisTimeWindow) {
    if (Serial) {
      Serial.println("Peripheral does not have transmitDataRecordedDuringThisTimeWindow characteristic");
    }
    return false;
  }
  return true;
}

void confirmBlink(bool leaveOn, bool blinkR, bool blinkG, bool blinkB) {
  // affirmative blinking that something succeeded
  short i = 1;
  while (i < 3) {
    if (blinkR) {
      digitalWrite(LEDR, LOW);
    }
    if (blinkG) {
      digitalWrite(LEDG, LOW);
    }
    if (blinkB) {
      digitalWrite(LEDB, LOW);
    }
    delay(500);
    if (blinkR) {
      digitalWrite(LEDR, HIGH);
    }
    if (blinkG) {
      digitalWrite(LEDG, HIGH);
    }
    if (blinkB) {
      digitalWrite(LEDB, HIGH);
    }
    delay(500);
    i++;
  }
  if (leaveOn) {
    if (blinkR) {
      digitalWrite(LEDR, LOW);
    }
    if (blinkG) {
      digitalWrite(LEDG, LOW);
    }
    if (blinkB) {
      digitalWrite(LEDB, LOW);
    }
  }
}

void turnLEDOff() {
  // turn all LEDs off
  digitalWrite(LEDR, HIGH);
  digitalWrite(LEDG, HIGH);
  digitalWrite(LEDB, HIGH);
}

bool receivedCorrectQueueEntry(int prevEpochTemp5, int prevEpochHumid5,
                               int prevEpochTemp4, int prevEpochHumid4,
                               int prevEpochTemp3, int prevEpochHumid3,
                               int prevEpochTemp2, int prevEpochHumid2,
                               int prevEpochTemp1, int prevEpochHumid1, int prevEpochTemp0,
                               int prevEpochHumid0, int thisEpochTemp, int thisEpochHumid,
                               int n, int o, int l, int m, int j, int k, int h, int i, int f, int g, int a, int b, int c, int d, int e,
                               int transQueueIndex) {
  // Check if the data read on the BS matches the last digits with the index, several case treatments depending on the queue lenght
  if(transQueueIndex >= 7){
    if(prevEpochTemp5%100 != n){
      Serial.println("Last two digits of prevEpochTemp5 are not equal to index");
      return false;
    }
    if(prevEpochHumid5%100 != o){
      Serial.println("Last two digits of prevEpochHumid5 are not equal to index");
      return false;
    }
    if(prevEpochTemp4%100 != l){
      Serial.println("Last two digits of prevEpochTemp4 are not equal to index");
      return false;
    }
    if(prevEpochHumid4%100 != m){
      Serial.println("Last two digits of prevEpochHumid4 are not equal to index");
      return false;
    }
    if(prevEpochTemp3%100 != j){
      Serial.println("Last two digits of prevEpochTemp3 are not equal to index");
      return false;
    }
    if(prevEpochHumid3%100 != k){
      Serial.println("Last two digits of prevEpochHumid3 are not equal to index");
      return false;
    }
    if(prevEpochTemp2%100 != h){
      Serial.println("Last two digits of prevEpochTemp2 are not equal to index");
      return false;
    }
    if(prevEpochHumid2%100 != i){
      Serial.println("Last two digits of prevEpochHumid2 are not equal to index");
      return false;
    }
    if(prevEpochTemp1%100 != f){
      Serial.println("Last two digits of prevEpochTemp1 are not equal to index");
      return false;
    }
    if(prevEpochHumid1%100 != g){
      Serial.println("Last two digits of prevEpochHumid1 are not equal to index");
      return false;
    }
    if(prevEpochTemp0%100 != a){
      Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
      return false;
    }
    if(prevEpochHumid0%100 != b){
      Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
      return false;
    }
    if(thisEpochTemp%100 != c){
      Serial.println("Last two digits of thisEpochTemp are not equal to index");
      return false;
    }
    if(thisEpochHumid%100 != d){
      Serial.println("Last two digits of thisEpochHumid are not equal to index");
      return false;
    }
    return ((n == o && o+1 == l && l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) || 
           (n == o && o+1 == l && l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b == 99 && c == d && c == e && c == 0) ||
           (n == o && o+1 == l && l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g == 99 && a == b && b == 0 && b+1 == c && c == d && c == e) ||
           (n == o && o+1 == l && l == m && m+1 == j && j == k && k+1 == h && h == i && i == 99 && f == g && g == 0 && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
           (n == o && o+1 == l && l == m && m+1 == j && j == k && k == 99 && h == i && i == 0 && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
           (n == o && o+1 == l && l == m && m == 99 && j == k && k == 0 && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
           (n == o && o == 99 && l == m && m == 0 && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e));
  }
  else{
    if(transQueueIndex == 6){
      if(prevEpochTemp4%100 != l){
        Serial.println("Last two digits of prevEpochTemp4 are not equal to index");
        return false;
      }
      if(prevEpochHumid4%100 != m){
        Serial.println("Last two digits of prevEpochHumid4 are not equal to index");
        return false;
      }
      if(prevEpochTemp3%100 != j){
        Serial.println("Last two digits of prevEpochTemp3 are not equal to index");
        return false;
      }
      if(prevEpochHumid3%100 != k){
        Serial.println("Last two digits of prevEpochHumid3 are not equal to index");
        return false;
      }
      if(prevEpochTemp2%100 != h){
        Serial.println("Last two digits of prevEpochTemp2 are not equal to index");
        return false;
      }
      if(prevEpochHumid2%100 != i){
        Serial.println("Last two digits of prevEpochHumid2 are not equal to index");
        return false;
      }
      if(prevEpochTemp1%100 != f){
        Serial.println("Last two digits of prevEpochTemp1 are not equal to index");
        return false;
      }
      if(prevEpochHumid1%100 != g){
        Serial.println("Last two digits of prevEpochHumid1 are not equal to index");
        return false;
      }
      if(prevEpochTemp0%100 != a){
        Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
        return false;
      }
      if(prevEpochHumid0%100 != b){
        Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
        return false;
      }
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b == 99 && c == d && c == e && c == 0) ||
             (l == m && m+1 == j && j == k && k+1 == h && h == i && i+1 == f && f == g && g == 99 && a == b && b == 0 && b+1 == c && c == d && c == e) ||
             (l == m && m+1 == j && j == k && k+1 == h && h == i && i == 99 && f == g && g == 0 && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (l == m && m+1 == j && j == k && k == 99 && h == i && i == 0 && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (l == m && m == 99 && j == k && k == 0 && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e));
    }
    if(transQueueIndex == 5){
      if(prevEpochTemp3%100 != j){
        Serial.println("Last two digits of prevEpochTemp3 are not equal to index");
        return false;
      }
      if(prevEpochHumid3%100 != k){
        Serial.println("Last two digits of prevEpochHumid3 are not equal to index");
        return false;
      }
      if(prevEpochTemp2%100 != h){
        Serial.println("Last two digits of prevEpochTemp2 are not equal to index");
        return false;
      }
      if(prevEpochHumid2%100 != i){
        Serial.println("Last two digits of prevEpochHumid2 are not equal to index");
        return false;
      }
      if(prevEpochTemp1%100 != f){
        Serial.println("Last two digits of prevEpochTemp1 are not equal to index");
        return false;
      }
      if(prevEpochHumid1%100 != g){
        Serial.println("Last two digits of prevEpochHumid1 are not equal to index");
        return false;
      }
      if(prevEpochTemp0%100 != a){
        Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
        return false;
      }
      if(prevEpochHumid0%100 != b){
        Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
        return false;
      }
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (j == k && k+1 == h && h == i && i+1 == f && f == g && g+1 == a && a == b && b == 99 && c == d && c == e && c == 0) ||
             (j == k && k+1 == h && h == i && i+1 == f && f == g && g == 99 && a == b && b == 0 && b+1 == c && c == d && c == e) ||
             (j == k && k+1 == h && h == i && i == 99 && f == g && g == 0 && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (j == k && k == 99 && h == i && i == 0 && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e));
    }
    if(transQueueIndex == 4){
      if(prevEpochTemp2%100 != h){
        Serial.println("Last two digits of prevEpochTemp2 are not equal to index");
        return false;
      }
      if(prevEpochHumid2%100 != i){
        Serial.println("Last two digits of prevEpochHumid2 are not equal to index");
        return false;
      }
      if(prevEpochTemp1%100 != f){
        Serial.println("Last two digits of prevEpochTemp1 are not equal to index");
        return false;
      }
      if(prevEpochHumid1%100 != g){
        Serial.println("Last two digits of prevEpochHumid1 are not equal to index");
        return false;
      }
      if(prevEpochTemp0%100 != a){
        Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
        return false;
      }
      if(prevEpochHumid0%100 != b){
        Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
        return false;
      }
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((h == i && i+1 == f && f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (h == i && i+1 == f && f == g && g+1 == a && a == b && b == 99 && c == d && c == e && c == 0) ||
             (h == i && i+1 == f && f == g && g == 99 && a == b && b == 0 && b+1 == c && c == d && c == e) ||
             (h == i && i == 99 && f == g && g == 0 && g+1 == a && a == b && b+1 == c && c == d && c == e));
    }
    if(transQueueIndex == 3){
      if(prevEpochTemp1%100 != f){
        Serial.println("Last two digits of prevEpochTemp1 are not equal to index");
        return false;
      }
      if(prevEpochHumid1%100 != g){
        Serial.println("Last two digits of prevEpochHumid1 are not equal to index");
        return false;
      }
      if(prevEpochTemp0%100 != a){
        Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
        return false;
      }
      if(prevEpochHumid0%100 != b){
        Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
        return false;
      }
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((f == g && g+1 == a && a == b && b+1 == c && c == d && c == e) ||
             (f == g && g+1 == a && a == b && b == 99 && c == d && c == e && c == 0) ||
             (f == g && g == 99 && a == b && b == 0 && b+1 == c && c == d && c == e));
    }
    if(transQueueIndex == 2){
      if(prevEpochTemp0%100 != a){
        Serial.println("Last two digits of prevEpochTemp0 are not equal to index");
        return false;
      }
      if(prevEpochHumid0%100 != b){
        Serial.println("Last two digits of prevEpochHumid0 are not equal to index");
        return false;
      }
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((a == b && b+1 == c && c == d && c == e) ||
             (a == b && b == 99 && c == d && c == e && c == 0));
    }
    if(transQueueIndex == 1){
      if(thisEpochTemp%100 != c){
        Serial.println("Last two digits of thisEpochTemp are not equal to index");
        return false;
      }
      if(thisEpochHumid%100 != d){
        Serial.println("Last two digits of thisEpochHumid are not equal to index");
        return false;
      }
      return ((c == d && c == e) || (c == d && c == e && c == 0));
    }
    if(transQueueIndex == 0){
      return false;
    }
  }
}

void turnTriggerOff(){
  for (short i = 0; i<totalNumberNodes; i++){
    yetToTriggerNewInstructionsAtNode[i] = false;
  }
}

unsigned long globalMillis(){
  timeSinceGlobalTimeInput = millis() - millisWhenGlobalTimeInputWasReceived;
  return globTimeInput + timeSinceGlobalTimeInput;
}

int getParameterFromSerialInput(String parameterName, bool needBuffer){
  // needBuffer has to be false at first parameter to be set and true for everything else when user is writing on console but has to be false for everything when pythin script is used
  Serial.println("Enter " + parameterName + ":");
  int value = 0;
  if (needBuffer){
    while (!Serial.available()) {}  // Wait for input
    serialBuffer = Serial.parseInt();  
  }
  while (!Serial.available()) {}  // Wait for input
  value = Serial.parseInt();
  Serial.print(parameterName + " set to: ");
  Serial.println(value);
  return value;
}

