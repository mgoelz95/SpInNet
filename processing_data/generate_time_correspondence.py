#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
This script translates epoch indexes into absolute time and vice-versa. Stores
the correspondences as a csv file. These correspondences help the operator of
the recorded data sets to understand at what absolute time entries of the csv
data files were recorded.
"""

# %% setup: imports
import numpy as np
import datetime

import os
import sys
import time

import pandas as pd

from utilities.physical_setup import get_experiment_parameters
#%% setup: auxiliary functions
def create_new_timefile(filename, shape):
    """Create a new empty csv file to store time correspondences.

    Parameters
    ----------
    filename : string
        The absolute filename of the file to create 
    shape : list
        The initial dimension of the file structure.
    """
    df = pd.DataFrame({'epoch': [], 'time': []})
    df.to_csv(filename, index=False)

def write_time_buffer_to_csv(time_buffer, data_directory):
    """Write previously created time buffer into csv file.

    Parameters
    ----------
    time_buffer : dictionairy
        Contains correspondences of epochs to absolute times.
    data_directory : string
        The data directory.
    """
    filename = 'time_correspondences'
    abs_filename = os.path.join(data_directory, filename + '.csv')

    # create directories if they don't exist
    if not os.path.exists(data_directory):
        os.makedirs(data_directory)
    
    # check if file exists, otherwise create new 
    if not os.path.exists(abs_filename):
        create_new_timefile(abs_filename, [10000, 1])

    # first load files
    df = pd.read_csv(abs_filename)

    # modify the datafield (DF) entries
    for key in time_buffer.keys():
        new_row = {'epoch': int(key), 'time': time_buffer[key]}
        df =  pd.concat([df, pd.DataFrame([new_row])], ignore_index = True)

    # save modified DF to file
    df.to_csv(abs_filename, index=False, mode='w')

# %% setup: user-defined parameters
experiment_name = "eusipco" # choices are: 'eusipco', 'bonus'
until_epoch = 250000 # create absolute time indexes from 0 to this value

# %% setup: automated initializations
"""
These here variables here have to be customized to match your own platform!
    data_directory : String
        The directory the data csv files are stored in.
    backup_directory: String
        The directory the backup data csv files are stored in.
"""
data_directory = os.path.join("csv", experiment_name)

# %% setup: processing user inputs
(start_glob_time_at, tsEpochDuration, tsWindowLength,
 sensorSamplingTimeInterval) = get_experiment_parameters(experiment_name)

# %% calculate duration of one epoch
tsEpochDurationInSeconds = tsEpochDuration/1000
print("One epoch lasts {} seconds".format(tsEpochDurationInSeconds))

# %% calculate time correspondences
time_correspondences = {}

for i in np.arange(until_epoch):
    time_correspondences[i] = (start_glob_time_at + i*datetime.timedelta(
        seconds=tsEpochDurationInSeconds))

# %% save time correspondences
dat_path = os.path.join(os.getcwd(), '..', data_directory)

write_time_buffer_to_csv(
    time_correspondences, dat_path)