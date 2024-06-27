#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Python script to run SiNet in "TS only" mode. no transmission or computation of
p-values on the node level. Requires connected Arduino Nano Sense Rev2
(with script fc_ts_only installed) and Arduino Uno (with script reset_via_pin
installed).
PLEASE CITE THE CORRESPONDING PAPERS IF YOU USE THIS CODE IN YOUR WORK!

@author: Martin Goelz

---- version number: v2.2 ----
---- version date: 05-06-2024 ----

Arduino requirements:
    fc_ts_only.ino, v2.1
    node_ts_only.ino, v2.0
    reset_via_pin.ino v1.0
"""
# =============================================================================
# Instructions on how to use this file to run the FC of SiNet-
#   1) Make sure your nodes are up and running with the suitable version of
#      node_ts_only.ino installed.
#   2) Install fc_ts_only.ino on your FC-dedicated Arduino Nano and connect
#      this nano to one of the USB ports of the computer this script is running
#      on.
#   3) Specify the name of this USB port in code cell "setup: port names and
#      directories". Remark: If you do not know the port name, opening the
#      Arduino IDE and checking the port name of the connected Nano is a quick
#      approach to finding the name. Also, if you work with linux, portnames
#      can change after rebooting (I noticed that their appended number varies)
#      To deal with this, I specified alternate port names. you may need to
#      specify more.
#   4) Install reset_via_pin.ino on your FC-dedicated Arduino Uno and connect
#      it to one of the USP ports of the computer this script is running on.
#   5) Again, specify the name of this port in the previously mentioned code
#      cell. The same remark about finding the name applies here.
#   6) If you wish to use a specific directory for storing your data and the
#      data backup, make sure to change data_directory or backup_directory
#      variables.
#   7) Run this file and enjoy!
# =============================================================================

# %% setup: imports
import numpy as np

import os
import sys
import time
import datetime

import serial
import re

from utilities.aux import (restart_serial, pass_time_to_nano, reboot,
                           send_telegram_message, write_data_buffer_to_csv)
# %% setup: port names and directories
"""
These here variables here have to be customized to match your own platform!
    possible_nano_port_names : list of strings
        The potential names of USB ports to which the Arduino Nano Sense Rev2
        of the FC is attached, who receives the test statistics from the nodes.
        List needed, as there are multiple ports that the 
        Nano Sense Rev2 might be attached to. Particularly important when
        running under linux, as the port names might change WHILE the script
        is executed, when rebooting of the Nano Sense Rev2 takes place! Hence
        why there are all these alternative definitions of the name for linux.
    possible_rebooter_port_names : list of strings
        The potential names of USB ports to which the Arduino Uno of the FC is
        attached, who takes care of rebooting the Nano in case it does not
        connect to nodes anymore.
    data_directory : String
        The directory the data csv files are to be stored in.
    backup_directory: String
        The directory the backup data csv files are to be stored in.
"""
possible_nano_port_names = []
possible_rebooter_port_names = []

if sys.platform == 'darwin': # macOS
    possible_nano_port_names.append('/dev/cu.usbmodem2101') # right usb-c port
    possible_nano_port_names.append('/dev/cu.usbmodem11101') # left-most usb-c
    # port on table
    possible_rebooter_port_names.append('/dev/cu.usbmodem1301') # hub
    data_directory = r'/Users/gloetz/mounts/wsn/data/csv'
    backup_directory = r'/Users/gloetz/mounts/wsn/data/backup'
elif sys.platform == 'linux': # linux
    possible_nano_port_names.append('/dev/ttyACM1')
    # need to define all these alternatives because linux may change the port
    # name after rebooting of the Nano Sense Rev2
    possible_nano_port_names.append('/dev/ttyACM2')
    possible_nano_port_names.append('/dev/ttyACM3')
    possible_nano_port_names.append('/dev/ttyACM4')
    possible_nano_port_names.append('/dev/ttyACM5')
    possible_nano_port_names.append('/dev/ttyACM6')
    possible_nano_port_names.append('/dev/ttyACM7')
    possible_rebooter_port_names.append('/dev/ttyACM0')
    data_directory = r'/home/ssnetwork/data/csv'
    backup_directory = r'/home/ssnetwork/data/backup'
else: # windows
    possible_nano_port_names.append('TBA')
    possible_rebooter_port_names.append('TBA')
    data_directory = os.path.join("..", "data", "csv")
    backup_directory = os.path.join("..", "data", "csv", "backup")


# %% setup: user inputs
recoverData = 1 # Keep this at 1 unless specifically overwriting local node
# data for identical parameters is desired. If parameter values are changed,
# those get communicated to the nodes and restarts them anyways.
experiment_name = 'experiment_F' # will be the file name
# Parameter values are specific to the experiment_name, so whenever you change
# parameters, make sure to use a different experiment_name

numberOfNodes = 54	 # the total number of nodes in the network

waitingTimeBeforeReconnect = 10000 # time in ms before connecting to same node
# again
waitThisTimeBeforeSkippingNodeConnection = waitingTimeBeforeReconnect # time in
# ms before looking for the next node.

transmitDataRecordedDuringThisTimeWindow = 3600000 # in ms, 3600000 equals one
# hour

# %% setup: processing user inputs
# experiment-dependent parameters. If you wish to run your own experiments, 
# expand.
if experiment_name == 'experiment_E':
    start_glob_time_at = datetime.datetime(2024, 4, 8, 12, 45, 0) 
    tsWindowLength = 10 # take this many measurements from the sensor during
    # one epoch
    tsEpochBufferDuration = 1000 # wait this long (in ms) after all samples for
    # the current epoch have been recorded before the next epoch starts
    sensorSamplingTimeInterval = 500 # sample the sensor again after this many
    # ms
    # precision. Must match precision with which values are sent from nodes!
    precisionTS = 9 # keep at 9. bottle neck is sensor precision, not
    # transmission precision.

    startRecordingEpoch = 5 # nodes start recording after the epoch with this
    # index.
    # It does take a while for the FC to communicate the parameters to all
    # nodes initially, so if you want all nodes to start recording
    # simultaneously, you need to set startRecordingEpoch to a value larger
    # than the epoch by which all nodes have received the parameters. It is not
    # necessary for all nodes to wait until all other nodes have received the
    # parameters before they start recording data. So value can be left as is,
    # unless previously described behavior specifically desired
elif experiment_name == 'experiment_F':
    # the global time at which this experiment started
    start_glob_time_at = datetime.datetime(2024, 5, 8, 15, 55, 0) 
    tsWindowLength = 10 # take this many measurements from the sensor during
    # one epoch
    tsEpochBufferDuration = 1000 # wait this long (in ms) after all samples for
    # the current epoch have been recorded before the next epoch starts
    sensorSamplingTimeInterval = 500 # sample the sensor again after this many
    # ms
    # precision. Must match precision with which values are sent from nodes!
    precisionTS = 9 # keep at 9. bottle neck is sensor precision, not
    # transmission precision.

    startRecordingEpoch = 5 # nodes start recording after the epoch with this
    # index.
else:
    print('An experiment with this name does not exist! Aborting.')
    time.sleep(20)
    sys.exit()

tsEpochDuration = (
    tsWindowLength * sensorSamplingTimeInterval + tsEpochBufferDuration)
deathWarningAfterThisTime = 180 * waitThisTimeBeforeSkippingNodeConnection
# after this time, the node prints on the serial bus that it may have died.

max_data_buffer_size = int(
    transmitDataRecordedDuringThisTimeWindow /  tsEpochDuration * 1.2) # gather
# at most this many values before writing in the CSV file. must be larger than
# the max number of transmitted test statistics per one connection!!
# %% setup: sanity check for port names
# check if user has input their own port names
if "TBA" in possible_nano_port_names or "TBA" in possible_rebooter_port_names:
    print("You have not specified your personal USB ports yet!")
    sys.exit("Program terminated")


# %% setup: start the serial ports to nano and uno
for pn in possible_rebooter_port_names:
    if restart_serial(pn) is not None:
        uno = serial.Serial(pn, 9600, timeout=1)
        reboot(uno)
        break

for pn in possible_nano_port_names:
    if restart_serial(pn) is not None:
        nano = serial.Serial(pn, 9600, timeout=1)
        break
try:
    print("Nano port name is " + nano.name)
    print("Uno port name is " + uno.name)
except:
    print("Nano or uno nowhere found. Specify correct USB port names!")
    sys.exit()

# %% setup: initializations
backup_key = str(time.time())

this_node = 54

last_successfull_connection_at_time = start_glob_time_at # for triggering hard
# reset
reboot_after_time = 300 # in seconds. With = 300, reboots
# FC nano after 5 minutes without connection to node.

wait_for_serial_seconds = 30 # in seconds. Reboots FC nano after this time if
# serial is not found for whatever strange reason

data_buffer = np.zeros([max_data_buffer_size, 3])

# need to keep track which nodes have all been triggered, in order to switch to
# recoverData mode once all have been triffered
numNodesTriggered = 0

# create directory for results if doesnt exist
data_directory = os.path.join(data_directory, experiment_name)
backup_directory = os.path.join(backup_directory, experiment_name)

# upon start-up, pass the current time and time index to the nanao
# first communicate the global time to the nano
print("Global time starts at {}".format(
    start_glob_time_at.strftime("%Y-%m-%d, %H:%M:%S")))

nano = pass_time_to_nano(nano, start_glob_time_at, tsEpochDuration,
                         possible_nano_port_names, wait_for_serial_seconds)

last_successfull_connection_at_time = datetime.datetime.now() # init
last_successfull_transmission_at_time = datetime.datetime.now() # init

# %% setup: define all serial outputs from the nano and uno that trigger serial
# input from this script.

# now set all the remaining parameters 
# the patterns to look for while writing input parameters
set_to_pattern = r'set to'

recoverDataPattern = r'^Enter recoverDataMode'

tsWindowLengthPattern = r'^Enter tsWindowLength'
tsEpochBufferDurationPattern = r'^Enter tsEpochBufferDuration'
precisionTSPattern = r'Enter precisionTS'
startRecordingEpochPattern = r'^Enter startRecordingEpoch'
sensorSamplingTimeIntervalPattern = r'^Enter sensorSamplingTimeInterval'

waitingTimeBeforeReconnectPattern = r'^Enter waitingTimeBeforeReconnect'
waitThisTimeBeforeSkippingNodeConnectionPattern = (
    r'^Enter waitThisTimeBeforeSkippingNodeConnection')
deathWarningAfterThisTimePattern = r'^Enter deathWarningAfterThisTime'
transmitDataRecordedDuringThisTimeWindowPattern = (
    r'^Enter transmitDataRecordedDuringThisTimeWindow')

connectToNodeWithIndexPattern = r'^Enter connectToNodeWithIndex'

# what patterns are we looking for during data transmission?
data_pattern = r'^Node\d+,\d+,\d+,\d+,\d+$'  # Regex pattern to match the
# desired format
successful_connect_pattern  = 'found all characteristics'
disconnect_pattern = r'^Peripheral disconnected' # disconnection pattern
soft_reset_pattern = r'^Restarted softly!' # raise suspicion via telegram bot

trigger_pattern = r'^All have been triggered' # to count number of triggered
# nodes

#%% endlessly running loop to set parameters and receive/store data from nodes
while True:
    if ((datetime.datetime.now() - last_successfull_connection_at_time).seconds
        > reboot_after_time):
        print("Maximum time without connection has passed! Rebooting Nano.")
        send_telegram_message(
            "max time without connection.")
            # save what has been in the buffer to this stage
        write_data_buffer_to_csv(
            data_buffer, this_node, data_directory, backup_directory,
            backup_key)
        data_buffer = np.zeros([max_data_buffer_size, 3])
        reboot(uno)
    if ((datetime.datetime.now()
         - last_successfull_transmission_at_time).seconds > reboot_after_time):
        print("Maximum time without transmission has passed! Rebooting Nano.")
        send_telegram_message(
            "max time without transmission.")
        # save what has been in the buffer to this stage
        write_data_buffer_to_csv(
            data_buffer, this_node, data_directory, backup_directory,
            backup_key)
        data_buffer = np.zeros([max_data_buffer_size, 3])

        this_node = this_node%numberOfNodes + 1 # increase by 1, in case node
        # got stuck somewhere
        reboot(uno)
    try:
        if nano.in_waiting > 0: # if the nano has written something new onto
            # serial output
            line = nano.readline().decode().strip() # grab current line
            print(line)
            # first check for data matching pattern -> this is always found
            # as fastest
            if re.match(data_pattern, line):
                last_successfull_transmission_at_time = datetime.datetime.now()
                values = line.split(",")
                this_node = int(values[0][4:])

                queue_idx = int(values[4])
                data_sfx = int(values[1])%100
                try: 
                    data_buffer[queue_idx, 0] = int(values[3])
                    data_buffer[queue_idx, 1] = (int(values[1]) - data_sfx) / (
                        10**precisionTS)
                    data_buffer[queue_idx, 2] = (int(values[2]) - data_sfx) / (
                        10**precisionTS)
                except IndexError as e:
                    # In case the node was not succesful in reading a smaller
                    # number of samples that should be transmitted during one
                    # connection, reboot and connect to the same node again.
                    # (could also be solved on the node level, but we do as
                    # much as possible in the python script for easier
                    # maintenance)
                    print(e)
                    this_node = this_node - 1
                    send_telegram_message("Index Error! Rebooting")
                    reboot(uno)
            # check if buffer should be written to file
            elif re.match(disconnect_pattern, line) and np.sum(data_buffer)>0:
                write_data_buffer_to_csv(
                    data_buffer, this_node, data_directory, backup_directory,
                    backup_key)
                data_buffer = np.zeros([max_data_buffer_size, 3])
            # check if connection was established
            elif re.search(successful_connect_pattern, line):
                last_successfull_connection_at_time = datetime.datetime.now()
            # check if line matches any of the defined patterns for input
            # parameters
            elif re.match(recoverDataPattern, line):
                nano.write(("{}".format(recoverData)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(tsWindowLengthPattern, line):
                nano.write(("{}".format(tsWindowLength)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(tsEpochBufferDurationPattern, line):
                nano.write(("{}".format(tsEpochBufferDuration)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(precisionTSPattern, line):
                nano.write(("{}".format(precisionTS)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(startRecordingEpochPattern, line):
                nano.write(("{}".format(startRecordingEpoch)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(sensorSamplingTimeIntervalPattern, line):
                nano.write(("{}".format(sensorSamplingTimeInterval)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(waitingTimeBeforeReconnectPattern, line):
                nano.write(("{}".format(waitingTimeBeforeReconnect)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(
                waitThisTimeBeforeSkippingNodeConnectionPattern, line):
                nano.write(("{}".format(
                    waitThisTimeBeforeSkippingNodeConnection)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(deathWarningAfterThisTimePattern, line):
                nano.write(("{}".format(deathWarningAfterThisTime)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(transmitDataRecordedDuringThisTimeWindowPattern,
                          line):
                nano.write(("{}".format(
                    transmitDataRecordedDuringThisTimeWindow)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(connectToNodeWithIndexPattern, line):
                # make sure to start where we left before being turned off
                nano.write(("{}".format(this_node-1)).encode())
                while True:
                    if nano.in_waiting > 0:
                        line = nano.readline().decode().strip()
                        if re.search(set_to_pattern, line):
                            print(line)
                            break
            elif re.match(trigger_pattern, line):
                numNodesTriggered = numNodesTriggered + 1
                print("Number of triggered nodes: {}".format(
                    numNodesTriggered))
                if numNodesTriggered == numberOfNodes:
                    recoverData = 1 # switch to recover data mode if all nodes
                    # have been triggered!
    except (OSError, AttributeError): 
        print("Connection to serial was lost. Waiting for serial...")
        serial_found = False
        while not serial_found:
            for cand_pn in possible_nano_port_names:
                nano_restarted = restart_serial(cand_pn)
                if nano_restarted is not None and not serial_found:
                    print("Serial found!")
                    nano = pass_time_to_nano(
                        nano_restarted, start_glob_time_at, tsEpochDuration,
                        possible_nano_port_names, wait_for_serial_seconds)
                    print("Time succesfully passed to Nano.")
                    if nano is not None:
                        # set to the time of the last reset
                        print("Nano is not none")
                        last_successfull_connection_at_time = (
                            datetime.datetime.now())
                        last_successfull_transmission_at_time = (
                            datetime.datetime.now())
                        serial_found = True
                    else:
                        print("Nano became None in pass_time_to_nano")
                        reboot(uno)
                        send_telegram_message(
                            "Rebooted nano, serial failed to init.")
                        cand_pn = possible_nano_port_names[0] # start from
                        # the first possible name again in the loop
        print("Serial_found is true and the loop was escaped!")
