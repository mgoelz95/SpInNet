/*
WSN NODE CODE WITH ONLY TEST STATISTICS (NO P-VALUES)
---- version number: v2.0 ----
---- version date: 2023-05-06 ----

** requires bs_ts_only version: v2.1 ** 

Always make sure base station and node versions match!

authors: lokubo, mgoelz

email: mgoelz@spg.tu-darmstadt.de

Important notes:
-- WORDING --:
  - variable names containing "time", "duration": refer to absolute time in [milliseconds]
  - variable names containing "epoch", "length": refers to relative time (epoch: no unit, length: in [epochs])
*/

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
// IMPORTS
// % % % % % % % % % % % % % % % % % % % % % % % % %
#include <ArduinoBLE.h>
#include <Arduino_HS300x.h>
#include <Arduino_LPS22HB.h>
#include <SPI.h>
#include <SD.h>
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
// PREPARATION: PARAMETER DEFINITIONS AND INITIALIZATIONS
// % % % % % % % % % % % % % % % % % % % % % % % % %
// The device name. Different for each node.
///////////////////////
// The device name
#define BLE_DEVICE_NAME     "Node001"
#define BLE_LOCAL_NAME      "Node001"
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % %
// Define test statistic parameters. 
///////////////////////
// the test statistic is recorded over a time period (in seconds) of {tsWindowLength} * {sensorSamplingTimeInterval} and is computed for 
// {tsWindowLength} measurements.
unsigned short tsWindowLength;  // dummy value, will be received from BS during operation

// per test statistic epoch, add a buffer during which no new recording are collected. Is basically there to ensure that we don't run into
// issues if transmitting the queue takes so long that a new test statistic epoch would end while transmission is still taking place.
unsigned short tsEpochBufferDuration; // {tsEpochDuration} = {tsWindowLength} * {sensorSamplingTimeInterval} + {tsEpochBufferDuration}

// parameters related to taking measurements from sensors
unsigned short sensorSamplingTimeInterval; // measurements are to be collected every {sensorSamplingTimeInterval} milliseconds
unsigned short numMeasRecordedThisEpoch = 0;  // so far recorded this many measurements in this epoch.
unsigned short numberOfNewMeasurementsToRecord = 0;  // number of new measurements to be computed 

bool doneRecordingThisEpochsMeasurements = false;  // if we recorded all of this epoch's measurements

unsigned int tsWindowDuration; // time period (in ms) over which a test statistic is computed.
// {tsWindowDuration} + {tsEpochBufferDuration} = {tsEpochDuration}
unsigned int tsEpochDuration; 

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Define data handling and transmission-related parameters
///////////////////////
// precision for temperature and humidity test statistics
unsigned long precisionTS = 9;  // multiply temperature and humidity test statistic by 10^precisionTemp

const unsigned short QUEUE_SIZE = 12500;  // number of p-values kept in RAM
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Initializations
/////////////////////////
// initializations of parameters for getting from measurements to test statistics 
unsigned long numTSComputed = 0; // total number of computed ts since node was turned on / received new instructions from BS.
unsigned short timesSensorsSampled = 0; // how many times the sensors were sampled in this TS epoch.

// initialization of arrays needed to handle and store measurements / data
float sensorData[2]; // Stores the values that were currently read by the sensor on this node
float prevSensorData[2]; // Stores the values were last read by the sensor, important for calculating the dataIncrease on this node
float dataIncrease[2]; // dataIncrease[i] = sensorData[i] - prevSensorData[i]

float sumAbsChange[2]; // sum of absolute changes of temperature/humidity during this TS epoch 
float meanAbsChange[2]; // mean absolute change of tempreature and humidity during one TS epoch

unsigned long dataQueue[QUEUE_SIZE][3];  // p-value transmission queue

// initialization of parameters related the SD card
const int SD_SELECT_PIN = 10;  // the pin for the SD card

unsigned short tsWindowLengthFromBS = tsWindowLength; 

unsigned short tsEpochBufferDurationFromBS = tsEpochBufferDuration;

unsigned short sensorSamplingTimeIntervalFromBS = sensorSamplingTimeInterval;

// initialization of parameters related to synchronization between node and BS
unsigned long timeNow = 0;  // the current local time in [ms]
unsigned long currentEpochIndex = 0; // the index of the current TS epoch. Reset whenever synchronization takes place
unsigned long updatedEpochIndex = 0; // when time gets updated, this is the new epoch index. variable needed to check if epoch timeNow different from epoch during last time.
unsigned long startRecordingEpoch = 1;  // start recording data at this epoch

unsigned long globTime = 0; // stores the global time in [ms]
unsigned long globTimeFromBS = 0; // if a new global time is received from the BS when change of parameters is triggered
unsigned long locTimeWhenGlobTimeCharChanged = 0; // value returned by millis() when the global time characteristic changed the last time.
unsigned long locTimeAtSync = 0; // the local time when the last synchronization took place
bool synchronized = false;  // if yes, node is synchronized to BS

// initialization of parameters related to the transmission of data from node to BS
bool bleCurrentlyConnected = false;  // if currently node is connected to BS via BLE
bool receivedNewParamsThisConnection = false; // if node received new instructions from BS during this connection. Then nothing is transmitted

unsigned long lastTimeSensorsSampled = 0;
unsigned long lastTimeDisconnected = 0;
unsigned long lastTimeConnected = 0;
unsigned long timePassedSinceSync = 0;  // time that has passed since last synchronization

bool transmittedEverythingThisConnection = false;
bool transmittedPartiallyThisConnection = false;
unsigned int queueIndexAtStartOfTransmission = 0;
unsigned int currentTransmissionQueueIndex = 0;

unsigned long transmitDataRecordedDuringThisTimeWindow = 900000;  // default value equals to 15 minutes
unsigned long transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS;  // default value equals to 15 minutes

unsigned short maxNumberOfTransmissionsPerConnection; // the number of queue entries to be transmitted in one connection cycle
unsigned long maxDurationOfConnection;

unsigned int queueIndex = 0;
uint32_t lastSuccessfullyAtBSReceivedQueueIndex = 0;  // the data from this queue index was the last one to be fully received at the BS

// initialization of other parameters
bool turnLEDOnOrOff = false;  // controls the blinking in the loop()

// for debugging -> print relevant parameters after queue resets to enable finding the error 
bool queueReset = false;
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
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// Initialization of BLE service and characteristics
/////////////////////////
BLEService environmentSensingService( BLE_UUID_ENVIRONMENT_SENSING_SERVICE);
BLEService measurementSendingService( BLE_UUID_MEASUREMENT_SENDING_SERVICE);

BLEUnsignedLongCharacteristic   humidPrev0EpochCharacteristic( BLE_UUID_HUMID_PREV0_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev0EpochCharacteristic( BLE_UUID_TEMP_PREV0_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   humidPrev1EpochCharacteristic( BLE_UUID_HUMID_PREV1_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev1EpochCharacteristic( BLE_UUID_TEMP_PREV1_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   humidPrev2EpochCharacteristic( BLE_UUID_HUMID_PREV2_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev2EpochCharacteristic( BLE_UUID_TEMP_PREV2_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   humidPrev3EpochCharacteristic( BLE_UUID_HUMID_PREV3_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev3EpochCharacteristic( BLE_UUID_TEMP_PREV3_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   humidPrev4EpochCharacteristic( BLE_UUID_HUMID_PREV4_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev4EpochCharacteristic( BLE_UUID_TEMP_PREV4_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   humidPrev5EpochCharacteristic( BLE_UUID_HUMID_PREV5_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   tempPrev5EpochCharacteristic( BLE_UUID_TEMP_PREV5_EPOCH, BLERead | BLENotify );
BLEUnsignedLongCharacteristic   globTimeCharacteristic(BLE_UUID_TIME_GLOBAL, BLERead | BLEWrite );
BLEUnsignedShortCharacteristic  queueIndexCharacteristic(BLE_UUID_QUEUEINDEX, BLERead | BLENotify);
BLEUnsignedShortCharacteristic  lastSuccessfullyAtBSReceivedQueueIndexCharacteristic(BLE_UUID_ACK, BLERead | BLEWrite);
BLEUnsignedLongCharacteristic   localEpochCharacteristic(BLE_UUID_GLOBAL_TIME_INDEX, BLERead);
BLEUnsignedShortCharacteristic  startRecordingIndexCharacteristic(BLE_UUID_START_RECORDING_INDEX, BLEWrite);
BLEUnsignedShortCharacteristic  tsWindowLengthCharacteristic(BLE_UUID_TEST_STATISTICS_SAMPLES, BLEWrite | BLERead);
BLEUnsignedShortCharacteristic  tsEpochBufferDurationCharacteristic(BLE_UUID_EPOCH_BUFFER_DURATION, BLEWrite | BLERead);
BLEUnsignedShortCharacteristic  sensorSamplingTimeIntervalCharacteristic(BLE_UUID_SENSOR_SAMPLING_TIME_INTERVAL, BLEWrite | BLERead);
BLEBooleanCharacteristic        triggerNewInstructionsCharacteristic(BLE_UUID_TRIGGER_NEW_INSTRUCTIONS, BLERead | BLEWrite );
BLEUnsignedLongCharacteristic   tempThisEpochCharacteristic(BLE_UUID_TEMP_THIS_EPOCH, BLEWrite | BLERead);
BLEUnsignedLongCharacteristic   humidThisEpochCharacteristic(BLE_UUID_HUMID_THIS_EPOCH, BLEWrite | BLERead );
BLEUnsignedLongCharacteristic   transmitDataRecordedDuringThisTimeWindowCharacteristic(BLE_UUID_TRANSMIT_TIME_WINDOW, BLEWrite);
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % %  
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
// SETUP: DO WHEN NODE IS POWERED UP
// % % % % % % % % % % % % % % % % % % % % % % % % %
void setup(){
  Serial.begin( 9600 );
  resetParValues();
  updateMaxNumberOfTransmissionsPerConnection();

  delay(5000); // wait a bit to give serial chance to show up


  if(Serial){
    Serial.print( "WSN NODE : " );
    Serial.println(BLE_DEVICE_NAME);
  }
  printCurrentParameters();

  // Initialize builtin LEDs for showing things
  pinMode(LED_BUILTIN, OUTPUT );
  pinMode(LEDR, OUTPUT);
  pinMode(LEDG, OUTPUT);
  pinMode(LEDB, OUTPUT);

  delay( 10 );

  HS300x.begin();  // turn on sensor
  setupBleMode(); // initialize BLE

  confirmBlink(true, true, true, true);  // initialization of sensor and BLE worked
  delay(5000);  // wait a bit so there is a chance to blink

  // because transmission time window and precisionTS are transmitted in one characteristic! didn't work otherwise
  transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS = transmitDataRecordedDuringThisTimeWindow + precisionTS;
  turnLEDOff();
  
}
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 

// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
// LOOP: REPEAT
// % % % % % % % % % % % % % % % % % % % % % % % % %
void loop() {
  // if we are in epoch buffer, the LED is off. If we are not in epoch buffer, the LED is on
  if (doneRecordingThisEpochsMeasurements){
    turnLEDOnOrOff = true;
  } else {
    turnLEDOnOrOff = false;
  }
  if (!bleCurrentlyConnected){
    digitalWrite(LEDB, HIGH);
    digitalWrite(LEDR, turnLEDOnOrOff);
    digitalWrite(LEDG, turnLEDOnOrOff);
  } else {
    digitalWrite(LEDR, HIGH);
    digitalWrite(LEDG, HIGH);
    digitalWrite(LEDB, LOW);
  }

  BLE.poll();

  // to force disconnect if connected for longer than max allowed time
  BLEDevice central = BLE.central();
  if (bleCurrentlyConnected && (millis() - lastTimeConnected) > maxDurationOfConnection){
    Serial.println((millis() - lastTimeConnected));
    Serial.println(maxDurationOfConnection);
    if (central.disconnect()){
      if (Serial){
        Serial.println("Connection timed out, so forced disconnect of central");
      }
    }
  }

  // check for new instructions from BS and process them
  bleGetInstructionsFromBS();

  // transmit the queue to the BS.
  bleQueueTransmission();

  // initialization of current measurements
  float temperature = 0;
  float humidity = 0;

  // update current local time
  updLocTime();

  numberOfNewMeasurementsToRecord = ceil(float((long(timeNow - tsEpochBufferDuration - (currentEpochIndex)*tsEpochDuration) - long(numMeasRecordedThisEpoch * sensorSamplingTimeInterval)))/float(sensorSamplingTimeInterval)) * (currentEpochIndex >= startRecordingEpoch);
  //if (timeNow - lastTimeSensorsSampled >= sensorSamplingTimeInterval){   // If it's time to record and/or send data
  if (numberOfNewMeasurementsToRecord > 0 && !doneRecordingThisEpochsMeasurements){
    Serial.print( timeNow); Serial.print(","); Serial.print(currentEpochIndex); Serial.print(","); Serial.print(numMeasRecordedThisEpoch); Serial.print(","); Serial.print(numberOfNewMeasurementsToRecord); Serial.println("");
    if (numberOfNewMeasurementsToRecord + numMeasRecordedThisEpoch > tsWindowLength){
      if (Serial){
        Serial.println(timeNow);
        Serial.println(startRecordingEpoch);
        Serial.println(currentEpochIndex);
        Serial.println(numberOfNewMeasurementsToRecord);
      }
      measErrorBlink("recorded more measurements than allowed for time window!");
    }

    while (numberOfNewMeasurementsToRecord > 0){
      lastTimeSensorsSampled = timeNow;
      //Acquire the data from the sensors
      float t = HS300x.readTemperature(); // Gets the values of the temperature
      float h = HS300x.readHumidity(); // Gets the values of the humidity
      sensorData[0] = t;
      sensorData[1] = h;

      // calculate increase in measured data
      computeTSAndUpdateDataArray(sensorData, prevSensorData, dataIncrease);

      // update absolute change in temperature and humidity
      sumAbsChange[0] += abs(dataIncrease[0]);
      sumAbsChange[1] += abs(dataIncrease[1]);
      numMeasRecordedThisEpoch ++;
      numberOfNewMeasurementsToRecord --;
      timesSensorsSampled++;
    }

    //if(timesSensorsSampled%tsWindowLength == 0 && timesSensorsSampled > 0){  // if we have observed the desired number of measurements composing one test statistic
    if (timesSensorsSampled > 0 && numMeasRecordedThisEpoch == tsWindowLength){
      // Compute the test statistic for this test statistic epoch
      meanAbsChange[0] = sumAbsChange[0]/tsWindowLength;
      meanAbsChange[1] = sumAbsChange[1]/tsWindowLength;

      sumAbsChange[0] = 0;
      sumAbsChange[1] = 0;
      // show the test statistic


      if(Serial){
        Serial.print("TS temperature/humidity: ");
        Serial.print(meanAbsChange[0],10);
        Serial.print("/");
        Serial.print(meanAbsChange[1],10);
        Serial.print(", measurements collected: ");
        Serial.println(numMeasRecordedThisEpoch);
      }

      numTSComputed++;
      numberOfNewMeasurementsToRecord = 0;
      numMeasRecordedThisEpoch = 0; // This epoch is complete, a new one is about to start.
      doneRecordingThisEpochsMeasurements = true;

      if(synchronized){
        if(queueIndex == QUEUE_SIZE){
          if (bleCurrentlyConnected){
            central.disconnect(); // disconnect first, to see if this was the reason why weird things were happening
          }
          delay(50); // trying to get rid of the getting stuck problem upon reset
          // WARNING: JUST CLEARING THE QUEUE NOW, NOT SAVING ANYTHING ON THE SD CARD AS NOT CURRENTLY STUDIED
          // saveSDfuncpValue(currentEpochIndex);       
          // then erase queue
          memset(dataQueue, 0, sizeof(dataQueue));
          delay(50); // trying to get rid of the getting stuck problem upon reset
          
          while (queueIndex > 0){ // added the loop to make sure that the queue Index is definitely set to 0!!
            Serial.print("Still in the loop trying to set the queueIndex to 0!");
            queueIndex = 0;
          }
          queueReset = true;
        }  
        dataQueue[queueIndex][0] = meanAbsChange[0] * pow(10, precisionTS);
        dataQueue[queueIndex][1] = meanAbsChange[1] * pow(10, precisionTS);
        dataQueue[queueIndex][2] = currentEpochIndex;

        queueIndex++;
        // This part here should not be necessary, but it necessary because nodes sometimes do weird things and numMeasRecordedThisEpoch was equal to TSWindowlength which caused nothing new to be recorded anymore
        // hence, here is repeated what was done before the (if(synchronized))
        numMeasRecordedThisEpoch = 0;
        numberOfNewMeasurementsToRecord = 0;
        doneRecordingThisEpochsMeasurements = true;

        if (Serial){
          Serial.print("Queue length: "); Serial.print(queueIndex); Serial.print("/"); Serial.println(QUEUE_SIZE);
          Serial.println("-------------------------------");
          printQueueUntilIndex(queueIndex);
          Serial.println("-------------------------------");
        }
      }
      if (Serial){
        Serial.println("");
      }
    }
  }
}

// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
// AUXILIARY FUNCTIONS
// % % % % % % % % % % % % % % % % % % % % % % % % %
// CONNECTIVITY
/////////////////////////

bool setupBleMode() {
// setting up the BLE module
  if ( !BLE.begin() ){
    if(Serial){
      Serial.println("BLE Setup has failed");
    }
    errorBlink("BLE Setup has failed");
  }
  BLE.setDeviceName( BLE_DEVICE_NAME );
  BLE.setLocalName( BLE_LOCAL_NAME );
  BLE.setAdvertisedService( environmentSensingService );
  BLE.setAdvertisedService( measurementSendingService );

  // BLE add characteristics
  measurementSendingService.addCharacteristic( tempPrev0EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev0EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempPrev1EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev1EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempPrev2EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev2EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempPrev3EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev3EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempPrev4EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev4EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempPrev5EpochCharacteristic );
  measurementSendingService.addCharacteristic( humidPrev5EpochCharacteristic );
  measurementSendingService.addCharacteristic( tempThisEpochCharacteristic);
  measurementSendingService.addCharacteristic( humidThisEpochCharacteristic);
  measurementSendingService.addCharacteristic( localEpochCharacteristic );

  environmentSensingService.addCharacteristic( globTimeCharacteristic );
  environmentSensingService.addCharacteristic( queueIndexCharacteristic );
  environmentSensingService.addCharacteristic( lastSuccessfullyAtBSReceivedQueueIndexCharacteristic );

  environmentSensingService.addCharacteristic( startRecordingIndexCharacteristic );
  environmentSensingService.addCharacteristic( tsWindowLengthCharacteristic );
  environmentSensingService.addCharacteristic( tsEpochBufferDurationCharacteristic );
  environmentSensingService.addCharacteristic( sensorSamplingTimeIntervalCharacteristic );

  environmentSensingService.addCharacteristic(triggerNewInstructionsCharacteristic);

  environmentSensingService.addCharacteristic(transmitDataRecordedDuringThisTimeWindowCharacteristic);

  // add service
  BLE.addService( environmentSensingService );
  BLE.addService( measurementSendingService );
  // set the initial value for the characeristics
  tempPrev0EpochCharacteristic.writeValue( 0 );
  humidPrev0EpochCharacteristic.writeValue( 0 );
  tempPrev1EpochCharacteristic.writeValue( 0 );
  humidPrev1EpochCharacteristic.writeValue( 0 );
  tempPrev2EpochCharacteristic.writeValue( 0 );
  humidPrev2EpochCharacteristic.writeValue( 0 );
  tempPrev3EpochCharacteristic.writeValue( 0 );
  humidPrev3EpochCharacteristic.writeValue( 0 );
  tempPrev4EpochCharacteristic.writeValue( 0 );
  humidPrev4EpochCharacteristic.writeValue( 0 );
  tempPrev5EpochCharacteristic.writeValue( 0 );
  humidPrev5EpochCharacteristic.writeValue( 0 );
  tempThisEpochCharacteristic.writeValue(0);
  humidThisEpochCharacteristic.writeValue(0);
  tempThisEpochCharacteristic.writeValue(0);
  humidThisEpochCharacteristic.writeValue(0);
  globTimeCharacteristic.writeValue( globTime );
  queueIndexCharacteristic.writeValue( 0 );
  lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.writeValue(lastSuccessfullyAtBSReceivedQueueIndex);
  localEpochCharacteristic.writeValue(currentEpochIndex);
  startRecordingIndexCharacteristic.writeValue(startRecordingEpoch);
  tsWindowLengthCharacteristic.writeValue(tsWindowLength);
  tsEpochBufferDurationCharacteristic.writeValue(tsEpochBufferDuration);
  sensorSamplingTimeIntervalCharacteristic.writeValue(sensorSamplingTimeInterval);
  triggerNewInstructionsCharacteristic.writeValue(false);
  transmitDataRecordedDuringThisTimeWindowCharacteristic.writeValue(transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS);

  // set BLE event handlers for connecting and disconnecting
  BLE.setEventHandler( BLEConnected, blePeripheralConnectHandler );
  BLE.setEventHandler( BLEDisconnected, blePeripheralDisconnectHandler );
  // start advertising
  BLE.advertise();

  return true;
}


void bleGetInstructionsFromBS(){

  // check if there was an update of TS parameters by the BS  -> can be triggered by change in tsWindowLength or tsEpochBufferDuration.
  // Once triggered, wait for some time and queury other characteristics multiple times to make sure that all changes get recorded
  bool changeInParamsDetected = false;
  uint8_t newInstructionsTriggered = 0;
  unsigned long currentGlobTimeCharacteristic = globTimeFromBS;

  globTimeCharacteristic.readValue(currentGlobTimeCharacteristic);

  if (globTimeFromBS != currentGlobTimeCharacteristic + 1200){
    // there was an update of global time from the BS
    globTimeFromBS = currentGlobTimeCharacteristic + 1200; // the 1200 come from experience, takes about that long to write/read value
    locTimeWhenGlobTimeCharChanged = millis(); 
  } else {
    // received the same value again, do nothing
  }

  triggerNewInstructionsCharacteristic.readValue(newInstructionsTriggered);  // if change in parameters is to be triggered

  if (newInstructionsTriggered == 1){
    if (Serial){
      Serial.println("Reception of new instructions triggered!");
    }
    resetParValues();
    newInstructionsTriggered = 0;
    triggerNewInstructionsCharacteristic.writeValue(newInstructionsTriggered);
    changeInParamsDetected = true;
  }
  
  // always check those first that cannot trigger a change of parameters
  transmitDataRecordedDuringThisTimeWindowCharacteristic.readValue(transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS);
  if (transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS != transmitDataRecordedDuringThisTimeWindow + precisionTS){
    precisionTS = transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS % 100;
    transmitDataRecordedDuringThisTimeWindow = transmitDataRecordedDuringThisTimeWindowPlusPrecisionFromBS - precisionTS;
    updateMaxNumberOfTransmissionsPerConnection();
  }

  startRecordingIndexCharacteristic.readValue(startRecordingEpoch); // cannot trigger a change, so always check first and always write first at BS.

  // now those guys can trigger a complete reset
  tsWindowLengthCharacteristic.readValue(tsWindowLengthFromBS);  // get number of measurements per test statistic from BS
  tsEpochBufferDurationCharacteristic.readValue(tsEpochBufferDurationFromBS);
  sensorSamplingTimeIntervalCharacteristic.readValue(sensorSamplingTimeIntervalFromBS);

  if (tsWindowLengthFromBS != tsWindowLength){
    if (Serial){
      Serial.println("Change in tsWindowLength detected!");
    }
    changeInParamsDetected = true;
  }
  if (tsEpochBufferDurationFromBS != tsEpochBufferDuration){
    if (Serial){
      Serial.println("Change in tsEpochBufferDuration detected!");
    }
    changeInParamsDetected = true;
  }
  if (sensorSamplingTimeIntervalFromBS != sensorSamplingTimeInterval){
    if (Serial){
      Serial.println("Change in sensorSamplingTimeInterval detected");
    }
    changeInParamsDetected = true;
  }


  if (changeInParamsDetected){
    receivedNewParamsThisConnection = true;
    synchronized = false;  // need to re-synchronize

    // clear the queue
    memset(dataQueue, 0, sizeof(dataQueue));
    // also flush queue copies

    delay(50);
    queueIndex = 0;

    queueReset = false;
    
    numberOfNewMeasurementsToRecord = 0;
    numMeasRecordedThisEpoch = 0; // This epoch is complete, a new one is about to start.

    tsWindowLength = tsWindowLengthFromBS;
    tsEpochBufferDuration = tsEpochBufferDurationFromBS;
    sensorSamplingTimeInterval = sensorSamplingTimeIntervalFromBS;

    computeTSWindowAndEpochDuration();
  
    if (!synchronized){
      doSynchronization();
    }

    printCurrentParameters();

    // computeStartRecordingEpoch();  // must take place after synchronization!
    if (Serial){
      Serial.print("Recording starts at epoch: "); Serial.println(startRecordingEpoch);
    }

  }
}


void bleQueueTransmission(){
  
  
  if (bleCurrentlyConnected && currentTransmissionQueueIndex != 0 /*&& !receivedNewParamsThisConnection*/){
    //Serial.println("CONNECTED AND READY AND HAS VALUES");
    
    /*lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
    Serial.print("\n currentTransmissionQueueIndex: ");
    Serial.print(currentTransmissionQueueIndex);
    Serial.print(", queueIndexAtStartOfTransmission: ");
    Serial.print(queueIndexAtStartOfTransmission);
    Serial.print(", lastSuccessfullyAtBSReceivedQueueIndex: ");
    Serial.print(lastSuccessfullyAtBSReceivedQueueIndex);
    Serial.print("\n");*/
    // Since we use 7 characteristics to send the data, inside this if only 7 characteristics are used
    if (currentTransmissionQueueIndex > 6){    
      tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 1][2])%100));
      humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 1][2])%100));
      tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
      humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
      tempPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
      humidPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100) );
      tempPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100));
      humidPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100) );
      tempPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100));
      humidPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100) );
      tempPrev4EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-6][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 6][2])%100));
      humidPrev4EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-6][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 6][2])%100) );
      tempPrev5EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-7][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 7][2])%100));
      humidPrev5EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-7][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 7][2])%100) );
      localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex - 1][2]);
      queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);      

      //unsigned long test[2] ={};

      /*Serial.print("\n Write \n tempPrev1: ");
      Serial.print((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
      Serial.print(", tempPrev2: ");
      Serial.print((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));*/

      //tempPrev1EpochCharacteristic.readValue(test[0]);
      //humidPrev1EpochCharacteristic.readValue(test[1]);

      /*Serial.print("\n read \n tempPrev1: ");
      Serial.print(test[0]);
      Serial.print(", tempPrev2: ");
      Serial.print(test[1]);*/

      //Serial.print(lastSuccessfullyAtBSReceivedQueueIndex); Serial.print("/"); Serial.println(currentTransmissionQueueIndex);
      lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
      if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){ // check specifically if previous index was successfully received at BS
        if (Serial){
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-3][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-3][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-3][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-4][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-4][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-4][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-5][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-5][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-5][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-6][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-6][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-6][1]);
          Serial.print("successfully transmitted - epoch ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-7][2]);
          Serial.print(" - TS temp/humid: ");
          Serial.print(dataQueue[currentTransmissionQueueIndex-7][0]);
          Serial.print("/");
          Serial.println(dataQueue[currentTransmissionQueueIndex-7][1]);
        }
        //globTimeCharacteristic.readValue(globTime);
        //Serial.print("Last Queue index successfully received at BS: ");
        // Serial.println(lastSuccessfullyAtBSReceivedQueueIndex);
        // Make sure this is the correct other, otherwise 7 datas will be lost
        if(currentTransmissionQueueIndex == 7){
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
        if(currentTransmissionQueueIndex > 6){
          currentTransmissionQueueIndex = currentTransmissionQueueIndex - 7;
        }
      }
    }
    // Case treatment using less characteristics than the maximum per transmission
    if(currentTransmissionQueueIndex <= 6){
      if(currentTransmissionQueueIndex == 6){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        tempPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
        humidPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100) );
        tempPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100));
        humidPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100) );
        tempPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100));
        humidPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100) );
        tempPrev4EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-6][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 6][2])%100));
        humidPrev4EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-6][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 6][2])%100) );
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-3][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-4][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-5][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-5][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-5][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-6][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-6][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-6][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 5){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        tempPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
        humidPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100) );
        tempPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100));
        humidPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100) );
        tempPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100));
        humidPrev3EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-5][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 5][2])%100) );
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-3][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-4][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-5][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-5][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-5][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 4){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        tempPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
        humidPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100) );
        tempPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100));
        humidPrev2EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-4][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 4][2])%100) );
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-3][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-4][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-4][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 3){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        tempPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100));
        humidPrev1EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-3][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 3][2])%100) );
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-3][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-3][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 2){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        tempPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        humidPrev0EpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-2][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex - 2][2])%100));
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-2][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-2][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 1){
        tempThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][0])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        humidThisEpochCharacteristic.writeValue((((dataQueue[currentTransmissionQueueIndex-1][1])/100)*100) + ((dataQueue[currentTransmissionQueueIndex-1][2])%100));
        localEpochCharacteristic.writeValue(dataQueue[currentTransmissionQueueIndex-1][2]);
        queueIndexCharacteristic.writeValue(currentTransmissionQueueIndex);
        lastSuccessfullyAtBSReceivedQueueIndexCharacteristic.readValue(lastSuccessfullyAtBSReceivedQueueIndex);
        if(lastSuccessfullyAtBSReceivedQueueIndex == currentTransmissionQueueIndex){
          if (Serial){
            Serial.print("successfully transmitted - epoch ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][2]);
            Serial.print(" - TS temp/humid: ");
            Serial.print(dataQueue[currentTransmissionQueueIndex-1][0]);
            Serial.print("/");
            Serial.println(dataQueue[currentTransmissionQueueIndex-1][1]);
          }
          currentTransmissionQueueIndex = 0;
          transmittedEverythingThisConnection = true;
        }
      }
      if(currentTransmissionQueueIndex == 0){
        transmittedEverythingThisConnection = true;
      }
    }
  }
}


void blePeripheralConnectHandler( BLEDevice central )
{
  
  lastSuccessfullyAtBSReceivedQueueIndex = 0;
  
  if (queueIndex > maxNumberOfTransmissionsPerConnection){
    queueIndexAtStartOfTransmission = maxNumberOfTransmissionsPerConnection;
  }
  else {
    queueIndexAtStartOfTransmission = queueIndex;
  }
  if (queueIndexAtStartOfTransmission % 7 != 0){
    queueIndexAtStartOfTransmission = queueIndexAtStartOfTransmission - 1; // make sure that there are multiple of 2 elements in the queue 
  }
  //if (queueIndexAtStartOfTransmission < 7){
  //  queueIndexAtStartOfTransmission = 0;
  //}
  currentTransmissionQueueIndex = queueIndexAtStartOfTransmission;
  
  receivedNewParamsThisConnection = false;

  bleCurrentlyConnected = true;

  // find queue index with non-zero entry
  unsigned short firstNonZeroQueueEntry = 0;
  for (short i = 0; i<queueIndex; i++){
    if (dataQueue[i][2]>0){
      firstNonZeroQueueEntry = i;
      break;
    }
  }

  turnLEDOff();
  digitalWrite(LEDB, LOW);  // turn on blue if connection established
  lastTimeConnected = millis();
}

void blePeripheralDisconnectHandler( BLEDevice central ) { 
  digitalWrite( LEDB, HIGH );
  digitalWrite( LEDR, LOW );
  digitalWrite( LEDG, LOW );

  bleCurrentlyConnected = false;
  receivedNewParamsThisConnection = false;

  // rearrange the queue if a full transmission took place durint this connection
  if (transmittedEverythingThisConnection) {// if a transmission took place
    if (Serial){
      Serial.print("Rearranging the queue...");
    }
    // after transmission has finished, any test statistics that were recorded during the time the transmission took place to the beginning of the queue and delete the rest
    for (unsigned short i = queueIndexAtStartOfTransmission; i < queueIndex; i++){
      for (unsigned char j = 0; j < 3; j++){
        dataQueue[i - queueIndexAtStartOfTransmission][j] = dataQueue[i][j];
      }
    }
    for (unsigned short i = queueIndex - queueIndexAtStartOfTransmission; i <= queueIndex; i++){
      for (unsigned char j = 0; j < 3; j++){
        dataQueue[i][j] = 0;
      }
    }
    queueIndex = queueIndex-queueIndexAtStartOfTransmission;
    if (Serial){
      Serial.println(" complete!");
    }
  }

  /*if (transmittedPartiallyThisConnection) {// if a transmission took place
    if (Serial){
      Serial.print("Removing transmitted items from the queue...");
    }
    // after transmission has finished, any test statistics that were recorded during the time the transmission took place to the beginning of the queue and delete the rest
    for (unsigned short i = queueIndexAtStartOfTransmission-7; i <= queueIndex; i++){
      for (unsigned char j = 0; j < 3; j++){
        dataQueue[i][j] = 0;
      }
    }
    queueIndex = queueIndexAtStartOfTransmission-7;
    if (Serial){
      Serial.println(" complete!");
    }
  }*/
  //transmittedPartiallyThisConnection = false;
  transmittedEverythingThisConnection = false;
  queueIndexAtStartOfTransmission = 0;
  currentTransmissionQueueIndex = 0;
  queueIndexCharacteristic.writeValue(0);
  lastTimeDisconnected = millis();
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// WORKING WITH TIME 
/////////////////////////

void updLocTime(){
// update the current local time, depending on whethe synchronization took place or not
  if(!synchronized){
    timeNow = millis();
    updatedEpochIndex = floor(timeNow/tsEpochDuration);
    if (!(currentEpochIndex == updatedEpochIndex)){
      currentEpochIndex = updatedEpochIndex;
      doneRecordingThisEpochsMeasurements = false;
      if (Serial){
        Serial.print(BLE_LOCAL_NAME); Serial.print(" - "); Serial.print("time/epoch index: "); Serial.print(timeNow); Serial.print("/"); Serial.println(currentEpochIndex);
      }
    }
    //currentEpochIndex = 0;
  } else {
    timePassedSinceSync = millis() - locTimeAtSync;  // at this time, the global time was received. Adds as an offset
    timeNow = globTime + timePassedSinceSync;  // update the current time
    //Serial.println(timeNow);
    updatedEpochIndex = floor(timeNow/tsEpochDuration); // remove this again!!
    //Serial.println(updatedEpochIndex);
    if (!(currentEpochIndex == updatedEpochIndex)){
      currentEpochIndex = updatedEpochIndex;
      doneRecordingThisEpochsMeasurements = false;
      numMeasRecordedThisEpoch = 0; // added to avoid getting stuck after queueReset took place! Also, should be reset when a new epoch starts, as there has not been recorded
      // anything yet
      if (Serial){
          Serial.print(BLE_LOCAL_NAME); Serial.print(" synchronized - "); Serial.print("time/epoch index: "); Serial.print(timeNow); Serial.print("/"); Serial.println(currentEpochIndex);
          if (queueReset){
            Serial.print("doneRecordingThisEpochsMeasurements: "); Serial.println(doneRecordingThisEpochsMeasurements);
            Serial.print("numMeasRecordedThisEpoch: "); Serial.println(numMeasRecordedThisEpoch);
            Serial.print("numberOfNewMeasurementsToRecord: "); Serial.println(numberOfNewMeasurementsToRecord);
            Serial.print("queueIndex : "); Serial.println(queueIndex);
            Serial.print("timesSensorsSampled : "); Serial.println(timesSensorsSampled);
            Serial.print("numTSComputed : "); Serial.println(numTSComputed);
            printCurrentParameters();
            printQueueUntilIndex(20);
          }
      }
    }
    //Serial.println(currentEpochIndex);
  }
}

void doSynchronization(){
  // synchronize the node with the BS
  globTime = globTimeFromBS + millis() - locTimeWhenGlobTimeCharChanged;
  timeNow = globTime;

  locTimeAtSync = millis();  // sync was timeNow, so update!
  timePassedSinceSync = millis() - locTimeAtSync;  // time that has passed since last synchronization

  unsigned long timeIndexAtReceptionOfGlobTimeFromBS = floor(globTime/tsEpochDuration);
  currentEpochIndex = timeIndexAtReceptionOfGlobTimeFromBS;
  if (Serial){
    Serial.print("Received global time/index:  "); Serial.print(globTime); Serial.print("/"); Serial.println(timeIndexAtReceptionOfGlobTimeFromBS);

  }
  queueIndexCharacteristic.writeValue(0);  // tell BS to disconnect

  // loop necessary to wait until this TS time window has entirely passsed to make sure new test statistic calculation starts exactly at beginning of new block
  while(currentEpochIndex == timeIndexAtReceptionOfGlobTimeFromBS){
    timePassedSinceSync = millis() - locTimeAtSync;
    timeNow = globTime + timePassedSinceSync;
    currentEpochIndex = floor(timeNow/tsEpochDuration);
  }
  if(currentEpochIndex != timeIndexAtReceptionOfGlobTimeFromBS){
    if (Serial){
      Serial.print("Synchronization complete. Current global time absolute/index: "); Serial.print(timeNow); Serial.print("/"); Serial.println(currentEpochIndex);
    }
    sumAbsChange[0] = 0;
    sumAbsChange[1] = 0;
    numTSComputed = 0;
    timesSensorsSampled = 0;
    synchronized = true;
    lastTimeSensorsSampled = timeNow;
  }
}
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// WORKING WITH DATA
/////////////////////////
void computeTSAndUpdateDataArray(float sensorData[2], float prevSensorData[2], float dataIncrease[2]){
// based on the new measurements sensorData and the past measurements prevSensorData, calculate the increase in the newly measured values
  
  // if/else needed to avoid huge increase in first run where prev data is just 0 
  if(prevSensorData[0]>0 && prevSensorData[1]>0){ 
    dataIncrease[0] = (sensorData[0] - prevSensorData[0]);  // temperature
    dataIncrease[1] = (sensorData[1] - prevSensorData[1]);  // humidity
  } else{
    // initialize sumAbsChange 
    sumAbsChange[0] = 0; 
    sumAbsChange[1] = 0;

    // initialize data increase
    dataIncrease[0] = 0;  // temperature
    dataIncrease[1] = 0;  // humidity
    timesSensorsSampled --;  // remove a epoch because there was no proper difference calculated
    numberOfNewMeasurementsToRecord++;
    numMeasRecordedThisEpoch --;
  }

  // current data is timeNow previous data
  prevSensorData[0] = (sensorData[0]);  // temperature
  prevSensorData[1] = (sensorData[1]);  // humidity
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// UPDATE PARAMETERS
/////////////////////////

void computeTSWindowAndEpochDuration(){
  // call whenever tsWindowLength or sensorSamplingTimeInterval change from the BS
  tsWindowDuration = tsWindowLength * sensorSamplingTimeInterval;
  tsEpochDuration = tsWindowDuration + tsEpochBufferDuration;
  updateMaxNumberOfTransmissionsPerConnection();
}

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// WORKING WITH SD CARD
/////////////////////////

void saveSDfuncpValue(int fileIdentifier) {
  if (Serial){
    Serial.println(" ////////////////////");
  }
  if (!SD.begin(SD_SELECT_PIN)) {
    if (Serial){
      Serial.println("SD card initialization failed.");
    }
    return;
  }

  if (Serial){
    Serial.println("SD card initialized.");
  }

  // Create a filename based on fileID
  char filename[13];
  sprintf(filename, "file%d.txt", fileIdentifier);

  File file = SD.open(filename, FILE_WRITE | O_APPEND);
  if (file) {
    for (int iSD = 0; iSD < QUEUE_SIZE; iSD++) {
      file.println(dataQueue[iSD][0]); // write data to file
      file.println(dataQueue[iSD][1]); // write data to file
      file.println(dataQueue[iSD][2]); // write data to file
    }

    file.close(); // close the file
    if (Serial){
      Serial.println("p-values saved saved to SD card");
    }
  } else {
    errorBlink("p-values saved saved to SD card");
  }

  file = SD.open(filename);
  while (file.available()) {
    float number = file.parseFloat();
    if (Serial){
      Serial.println(number, 4);
    }
  }
  if (!file) {
    if (Serial){
      Serial.println("Error opening file for reading.");
    }
    errorBlink("Error opening file for reading.");
  }
}


//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////

//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////
// USER FEEDBACK: PRINTING AND LED CONTROL FOR FEEDBACK
/////////////////////////
// LED CONTROL
void confirmBlink(bool leaveOn, bool blinkR, bool blinkG, bool blinkB){
// affirmative blinking that something succeeded
  short i = 1;
  while(i<3){
    if (blinkR){
      digitalWrite(LEDR, LOW);
    }
    if (blinkG){
      digitalWrite(LEDG, LOW);
    }
    if (blinkB){
      digitalWrite(LEDB, LOW);
    }
    delay(500);
    if (blinkR){
      digitalWrite(LEDR, HIGH);
    }
    if (blinkG){
      digitalWrite(LEDG, HIGH);
    }
    if (blinkB){
      digitalWrite(LEDB, HIGH);
    }
    delay(500);
    i++;
  }
  if (leaveOn){
    if (blinkR){
      digitalWrite(LEDR, LOW);
    }
    if (blinkG){
      digitalWrite(LEDG, LOW);
    }
    if (blinkB){
      digitalWrite(LEDB, LOW);
    }
  }
}

void errorBlink(String msg){
// If something went wrong, end up here to raise suspicion -> Need to blink RBG LED as digital pin 13 (ufor builtin led) is used by the SD card
  // and cannot be controlled anymore after initializing the SD card
  digitalWrite(LEDG, HIGH);
  digitalWrite(LEDB, HIGH);
  while(true){
    digitalWrite(LEDR, HIGH);
    delay(250);
    digitalWrite(LEDR, LOW);
    delay(250);
    if (Serial){ // print the error message
      Serial.println(msg);
    }
  }
}

void measErrorBlink(String msg){
// If something went wrong, end up here to raise suspicion -> Need to blink RBG LED as digital pin 13 (ufor builtin led) is used by the SD card
  // and cannot be controlled anymore after initializing the SD card
  digitalWrite(LEDG, HIGH);
  digitalWrite(LEDB, HIGH);
  while(true){
    short i = 0;
    while (i<3){
      digitalWrite(LEDR, HIGH);
      delay(250);
      digitalWrite(LEDR, LOW);
      delay(250);
      i++;
    }
    delay(1000);
  }
  if (Serial){
    Serial.println(msg);
  }
}

void turnLEDOff(){
// turn all LEDs off
  digitalWrite(LEDR, HIGH);
  digitalWrite(LEDG, HIGH);
  digitalWrite(LEDB, HIGH);
}

// PRINTING


void printQueueUntilIndex(int untilThisIndex){
  if (Serial){
    for(int i = 0; i < untilThisIndex; i++){
      if (dataQueue[i][2]>0){
        Serial.print(i);
        Serial.print(" - epoch ");
        Serial.print(dataQueue[i][2]);
        Serial.print(" - TS temp/humid ");
        Serial.print(dataQueue[i][0]);
        Serial.print("/");
        Serial.println(dataQueue[i][1]);
      }
    }
  }
  //delay(5000); // give a little time to read the output
}


void resetParValues(){
  tsWindowLength = 25;
  tsEpochBufferDuration = 4000;
  sensorSamplingTimeInterval = 600;

  computeTSWindowAndEpochDuration(); 
}


void updateMaxNumberOfTransmissionsPerConnection(){
  // update maxNumberOfTransmissionsPerConnection always such that about 20 mins worth of p-values are transmitted during one connection cycle
  maxNumberOfTransmissionsPerConnection = ceil(transmitDataRecordedDuringThisTimeWindow / tsEpochDuration);
  maxDurationOfConnection = maxNumberOfTransmissionsPerConnection * 2000; // usually clears about > 4 TS per second, so calculating max transmission time as 2* max number of transmissions should leave more than enough room for connection
  // never less than 2 minutes for reliability reasons! 
  if (maxDurationOfConnection < 120000){
    maxDurationOfConnection = 120000;
  }
  Serial.print("Disconnection time was changed to "); Serial.print(maxDurationOfConnection); Serial.println(" ms.");
}

void printCurrentParameters(){
  if (Serial){
    Serial.println("------------------------------- Current parameter values -------------------------------");
    Serial.print("TS Window length: "); Serial.println(tsWindowLength);
    Serial.print("TS Epoch Buffer Duration: "); Serial.println(tsEpochBufferDuration);
    Serial.print("sensor sampling time interval: "); Serial.println(sensorSamplingTimeInterval);
    Serial.print("Number of queue entries transmitted during one connection cycle: "); Serial.println(maxNumberOfTransmissionsPerConnection);
    Serial.print("TS precision: "); Serial.println(precisionTS);
    Serial.println("----------------------------------------------------------------------------------------");
  }
}
// % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % % 
//////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////////