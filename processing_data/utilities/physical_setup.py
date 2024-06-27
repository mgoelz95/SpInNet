#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python script to define all physical properties of SiNet. This includes both
information that is known before the experiments are conducted, such as the
sensor locations or the dimensions of the room, and information from during
the experiment. For instance, when H0 was in place throughout the entire room.

PLEASE CITE THE CORRESPONDING PAPER IF YOU USE THIS CODE IN YOUR WORK!

    [Goelz2024EUSIPCO]:
        Gölz et al., "Spatial Inference Network: Indoor Proximity
        Detection via Multiple Hypothesis Testing"
        DOI: TBA

@author: Martin Goelz
"""
# setup: imports
import numpy as np

import sys
sys.path.append('..')

import datetime

from utilities.aux import (get_sen_loc_arrary, start_end_to_index_list_renewed)

# %% the room and sensors
dim = (20, 20)  # there are twenty grid points in each direction in the room.

# First coordinate is x, second coordinate is y
sen_loc = [(6,11),(7,11),(8,12),(5,12),(6,13),(7,13),(6,2),(6,0),(7,1),(6,4),
           (9,2),(8,4),(11,1),(12,1),(13,1),(14,1),(15,2),(16,3),(16,5),(16,7),
           (16,9),(13,5),(14,8),(2,12),(2,14),(12,10),(13,9),(14,10),(12,11),
           (13,12),(14,11),(15,10),(15,12),(17,14),(17,15),(14,16),(12,16),
           (13,14),(7,19),(6,16),(4,16),(2,16),(0,16),(18,19),(11,19),(4,19),
           (1,9),(3,10),(2,9),(5,8),(1,7),(1,5),(1,3),(4,8)]

# sensor locations as an array
sen_loc_arr = get_sen_loc_arrary(dim, sen_loc)

# the anchor locations (anchor = grid points where H0 is known to be true. can
# be because there is an obstacle, wall etc).
anchor_loc = [(0, 0), (1, 0), (12, 0), (13, 0), (14, 0), (15, 0), (16, 0),
             (17, 0), (18, 0), (19, 0),
             (0, 1), (1, 1), (16, 1), (17, 1), (18, 1), (19, 1),
             (0, 2), (1, 2), (16, 2), (17, 2), (18, 2), (19, 2),
             (17, 3), (18, 3), (19, 3),
             (17, 4), (18, 4), (19, 4),
             (17, 5), (18, 5), (19, 5), 
             (0, 6), (17, 6), (18, 6), (19, 6),
             (17, 7), (18, 7), (19, 7),
             (17, 8), (18, 8), (19, 8),
             (17, 9), (18, 9), (19, 9), 
             (0, 10), (1, 10), (17, 10), (18, 10), (19, 10),
             (0, 11), (1, 11), (16, 11), (17, 11), (18, 11), (19, 11),
             (0, 12), (1, 12), (16, 12), (17, 12), (18, 12), (19, 12),
             (0, 13), (1, 13), (18, 13), (19, 13),
             (18, 14), (19, 14),
             (19, 15),
             (19, 16), 
             (0, 17), (1, 17), (2, 17), (19, 17),
             (0, 18), (1, 18), (2, 18), (19, 18),
             (0, 19), (1, 19), (2, 19), (13, 19), (14, 19), (9, 19), (19, 19)]

# anchor locations as an array
anchor_loc_arr = get_sen_loc_arrary(dim, anchor_loc)

# # %% experiment-dependent quantities
def get_true_label_start_and_end_time_lsts(experiment_name, null_sfx=''):
    """This function is used to label the data. When adding new data, make sure
    to add the labels here.

    Parameters
    ----------
    experiment_name : string
        The experiment name
    null_sfx : string
        Null suffix to indicate what is all included into the null. The default
        is to include everything.

    Returns
    -------
    tuple
        Four lists, containing start and end time of all H0 periods and the
        walking through the room H1 periods
    """
    if experiment_name == 'eusipco':
        # declare all periods during which H0 was true
        null_start_end_lst = []
        if null_sfx == '' or null_sfx == '_everything':
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 26, 18, 30, 0),
                 datetime.datetime(2024, 2, 26, 18, 50, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 26, 20, 45, 0), 
                 datetime.datetime(2024, 2, 27, 7, 0, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 27, 7, 0, 0),
                 datetime.datetime(2024, 2, 27, 13, 0, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 27, 15, 30, 0),
                 datetime.datetime(2024, 2, 27, 19, 0, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 27, 21, 0, 0), 
                 datetime.datetime(2024, 2, 28, 7, 0, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 28, 7, 0, 0), 
                 datetime.datetime(2024, 2, 28, 19, 0, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 28, 19, 0, 0), 
                 datetime.datetime(2024, 2, 29, 7, 0, 0)])   
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 29, 7, 0, 0), 
                 datetime.datetime(2024, 2, 29, 10, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 2, 29, 12, 0, 0), 
                 datetime.datetime(2024, 2, 29, 14, 45, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 1, 14, 5, 0), 
                 datetime.datetime(2024, 3, 1, 14, 46, 0)])  
            null_start_end_lst.append( # scenario_3
                [datetime.datetime(2024, 3, 1, 18, 30, 0), 
                 datetime.datetime(2024, 3, 2, 7, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 2, 7, 0, 0), 
                 datetime.datetime(2024, 3, 2, 19, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 2, 19, 0, 0), 
                 datetime.datetime(2024, 3, 3, 7, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 3, 7, 0, 0), 
                 datetime.datetime(2024, 3, 3, 19, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 3, 19, 0, 0), 
                 datetime.datetime(2024, 3, 4, 7, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 4, 7, 0, 0), 
                 datetime.datetime(2024, 3, 4, 12, 17, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 4, 13, 30, 0), 
                 datetime.datetime(2024, 3, 4, 14, 38, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 4, 16, 20, 0), 
                 datetime.datetime(2024, 3, 4, 17, 26, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 4, 19, 30, 0), 
                 datetime.datetime(2024, 3, 5, 7, 0, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 5, 7, 0, 0), 
                 datetime.datetime(2024, 3, 6, 15, 45, 0)])  
        
        # for '_everything', go until the end of the experiment. 
        if null_sfx == '_everything':
            # now add all of the remaining null periods
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 6, 17, 30, 0), 
                 datetime.datetime(2024, 3, 6, 19, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 6, 19, 00, 0), 
                 datetime.datetime(2024, 3, 7, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 7, 7, 00, 0), 
                 datetime.datetime(2024, 3, 7, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 7, 19, 00, 0), 
                 datetime.datetime(2024, 3, 8, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 8, 7, 00, 0), 
                 datetime.datetime(2024, 3, 8, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 8, 19, 00, 0), 
                 datetime.datetime(2024, 3, 9, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 9, 7, 00, 0), 
                 datetime.datetime(2024, 3, 9, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 9, 19, 00, 0), 
                 datetime.datetime(2024, 3, 10, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 10, 7, 00, 0), 
                 datetime.datetime(2024, 3, 10, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 10, 19, 00, 0), 
                 datetime.datetime(2024, 3, 11, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 11, 7, 00, 0), 
                 datetime.datetime(2024, 3, 11, 9, 30, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 12, 21, 00, 0), 
                 datetime.datetime(2024, 3, 13, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 12, 21, 00, 0), 
                 datetime.datetime(2024, 3, 13, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 3, 13, 11, 00, 0), 
                 datetime.datetime(2024, 3, 13, 19, 00, 0)])

        # declare all periods during which I was walking through the room
        walking_around_start_end_lst = []
        walking_around_start_end_lst.append( # scenario 1
            [datetime.datetime(2024, 3, 1, 14, 47, 0), 
             datetime.datetime(2024, 3, 1, 15, 17, 0)])
        walking_around_start_end_lst.append( # scenario 2
            [datetime.datetime(2024, 3, 13, 9, 30, 0), 
             datetime.datetime(2024, 3, 13, 9, 40, 0)])
        
    elif experiment_name == 'bonus':
        # declare all periods during which H0 was true
        null_start_end_lst = []
        if null_sfx == '' or null_sfx == 'everything':
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 8, 12, 45, 0),
                 datetime.datetime(2024, 4, 8, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 8, 19, 00, 0), 
                 datetime.datetime(2024, 4, 9, 7, 00, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 9, 19, 00, 0), 
                 datetime.datetime(2024, 4, 10, 7, 00, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 10, 7, 00, 0), 
                 datetime.datetime(2024, 4, 10, 9, 55, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 10, 18, 00, 0), 
                 datetime.datetime(2024, 4, 11, 7, 00, 0)])    
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 11, 7, 00, 0), 
                 datetime.datetime(2024, 4, 11, 9, 40, 0)])  
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 11, 12, 15, 0), 
                 datetime.datetime(2024, 4, 11, 17, 55, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 11, 18, 10, 0), 
                 datetime.datetime(2024, 4, 12, 7, 00, 0)]) 
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 12, 18, 00, 0), 
                 datetime.datetime(2024, 4, 13, 7, 00, 0)])       
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 13, 7, 00, 0), 
                 datetime.datetime(2024, 4, 13, 19, 00, 0)])                
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 13, 19, 00, 0), 
                 datetime.datetime(2024, 4, 14, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 14, 7, 00, 0), 
                 datetime.datetime(2024, 4, 14, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 14, 19, 00, 0), 
                 datetime.datetime(2024, 4, 15, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 15, 21, 15, 0), 
                 datetime.datetime(2024, 4, 16, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 16, 7, 00, 0), 
                 datetime.datetime(2024, 4, 16, 9, 40, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 16, 10, 50, 0), 
                 datetime.datetime(2024, 4, 16, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 16, 19, 00, 0), 
                 datetime.datetime(2024, 4, 17, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 17, 9, 45, 0), 
                 datetime.datetime(2024, 4, 17, 14, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 17, 16, 30, 0), 
                 datetime.datetime(2024, 4, 17, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 17, 19, 00, 0), 
                 datetime.datetime(2024, 4, 18, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 18, 7, 00, 0), 
                 datetime.datetime(2024, 4, 18, 10, 50, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 18, 12, 00, 0), 
                 datetime.datetime(2024, 4, 18, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 18, 19, 00, 0), 
                 datetime.datetime(2024, 4, 19, 7, 00, 0)])

       
        # for '_everything', go until the end of the experiment. Data of more
        # than a month!
        if null_sfx == '_everything':
            # now add all of the remaining null periods
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 19, 7, 00, 0), 
                 datetime.datetime(2024, 4, 19, 15, 35, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 19, 17, 00, 0), 
                 datetime.datetime(2024, 4, 20, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 20, 7, 00, 0), 
                 datetime.datetime(2024, 4, 20, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 20, 19, 00, 0), 
                 datetime.datetime(2024, 4, 21, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 21, 7, 00, 0), 
                 datetime.datetime(2024, 4, 21, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 21, 19, 00, 0), 
                 datetime.datetime(2024, 4, 22, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 22, 7, 00, 0), 
                 datetime.datetime(2024, 4, 22, 13, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 22, 15, 00, 0), 
                 datetime.datetime(2024, 4, 22, 20, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 22, 21, 30, 0), 
                 datetime.datetime(2024, 4, 23, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 23, 7, 00, 0), 
                 datetime.datetime(2024, 4, 23, 10, 40, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 23, 15, 30, 0), 
                 datetime.datetime(2024, 4, 23, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 23, 19, 00, 0), 
                 datetime.datetime(2024, 4, 24, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 24, 7, 00, 0), 
                 datetime.datetime(2024, 4, 24, 10, 30, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 24, 11, 45, 0), 
                 datetime.datetime(2024, 4, 24, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 24, 19, 00, 0), 
                 datetime.datetime(2024, 4, 25, 7, 40, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 25, 7, 00, 0), 
                 datetime.datetime(2024, 4, 25, 15, 25, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 25, 16, 45, 0), 
                 datetime.datetime(2024, 4, 25, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 25, 19, 00, 0), 
                 datetime.datetime(2024, 4, 26, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 26, 10, 50, 0), 
                 datetime.datetime(2024, 4, 26, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 26, 19, 00, 0),  
                 datetime.datetime(2024, 4, 27, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 27, 7, 00, 0), 
                 datetime.datetime(2024, 4, 27, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 27, 19, 00, 0),  
                 datetime.datetime(2024, 4, 28, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 28, 7, 00, 0), 
                 datetime.datetime(2024, 4, 28, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 28, 19, 00, 0),  
                 datetime.datetime(2024, 4, 29, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 29, 7, 00, 0), 
                 datetime.datetime(2024, 4, 29, 10, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 29, 11, 20, 0), 
                 datetime.datetime(2024, 4, 29, 18, 30, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 29, 20, 00, 0), 
                 datetime.datetime(2024, 4, 30, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 30, 7, 00, 0), 
                 datetime.datetime(2024, 4, 30, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 4, 30, 19, 00, 0), 
                 datetime.datetime(2024, 5, 1, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 5, 1, 7, 00, 0), 
                 datetime.datetime(2024, 5, 1, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 5, 1, 19, 00, 0), 
                 datetime.datetime(2024, 5, 2, 7, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 5, 2, 7, 00, 0), 
                 datetime.datetime(2024, 5, 2, 14, 45, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 5, 2, 16, 00, 0), 
                 datetime.datetime(2024, 5, 2, 19, 00, 0)])
            null_start_end_lst.append(
                [datetime.datetime(2024, 5, 2, 19, 00, 0), 
                 datetime.datetime(2024, 5, 3, 7, 00, 0)])

        # declare all periods during which I was walking through the room
        walking_around_start_end_lst = []
        walking_around_start_end_lst.append( # bonus_first_walk
            [datetime.datetime(2024, 4, 12, 13, 21, 0), 
             datetime.datetime(2024, 4, 12, 13, 48, 0)])
        walking_around_start_end_lst.append( # bonus_second_walk
            [datetime.datetime(2024, 4, 15, 20, 00, 0), 
             datetime.datetime(2024, 4, 15, 20, 18, 0)])

    else:
        print('Experiment name unknown. Error should have been caught '
              + 'before...')
        sys.exit()
    return (
        null_start_end_lst, walking_around_start_end_lst)


def get_experiment_parameters(experiment_name):
    """Return experiment-specific parameters.

    Parameters
    ----------
    experiment_name : String
        The name of the experiment.

    Returns
    -------
    tuple
        The experiment-specific parameters.
    """
    if experiment_name == 'eusipco':
        starting_time = datetime.datetime(2024, 2, 26, 18, 30, 0)
        tsWindowLength = 10
        tsEpochBufferDuration = 1000
        sensorSamplingTimeInterval = 500   
    elif experiment_name == 'bonus':
        starting_time = datetime.datetime(2024, 4, 8, 12, 45, 0)
        tsWindowLength = 10
        tsEpochBufferDuration = 1000
        sensorSamplingTimeInterval = 500   
    else:
        print("This experiment name is not known! Aborting.")
        sys.exit()
    tsEpochDuration = (
        tsWindowLength * sensorSamplingTimeInterval + tsEpochBufferDuration)
    return (starting_time, tsEpochDuration, tsWindowLength,
            sensorSamplingTimeInterval)
# %% event-dependent quantities
def get_event_start_end_times(experiment_name, evaluate_event, null_sfx):
    """returns start and end time of a given event.

    Parameters
    ----------
    experiment_name : string
        The experiment name
    evaluate_event : string
        The event name
    null_sfx : string
        The type of null distribution to be used, determines the null vector

    Returns
    -------
    list
        the event start and end times as datetime.datetime objects in a list.
    """
    (start_end_lst_H0,
     start_end_lst_H1_walking) = get_true_label_start_and_end_time_lsts(
        experiment_name, null_sfx)
    
    if experiment_name == 'eusipco':
        if evaluate_event == 'scenario_1':
            event_start_end_times = start_end_lst_H1_walking[5]
        elif evaluate_event == 'scenario_3' and null_sfx=='':
            event_start_end_times = start_end_lst_H0[10]
        elif evaluate_event == 'D_third_walk':
            event_start_end_times = start_end_lst_H1_walking[8]
    elif experiment_name == 'bonus':
        if (evaluate_event == 'bonus_first_walk'):
            event_start_end_times = start_end_lst_H1_walking[0]
        elif evaluate_event == 'bonus_second_walk':
            event_start_end_times = start_end_lst_H1_walking[1]
        elif evaluate_event == 'bonus_first_null':
            event_start_end_times = start_end_lst_H0[0]

    return event_start_end_times

# for some specific events and experiments, a type of ground truth exists
def get_ground_truth_crd(experiment_name, evaluate_event, dim):
    """specifies ground truth alternative grid points for some specific events
    and experiments

    Parameters
    ----------
    experiment_name : string
        The experiment name
    evaluate_event : string
        The event name
    dim : tuple of int
        the dimensions of the field

    Returns
    -------
    tuple
        containing the ground truth grid point arrays
    """
    if experiment_name == 'eusipco' and evaluate_event == 'scenario_1':
        # bottom right ground truth
        steady_ground_truth_br = [
            (7, 0), (8, 0), (9, 0), (10, 0), (11, 0),
            (7, 1), (8, 1), (9, 1), (10, 1), (11, 1), (12, 1), (13, 1),
            (14, 1), (15, 1), 
            (7, 2), (8, 2), (9, 2), (10, 2), (11, 2), (12, 2), (13, 2),
            (14, 2), (15, 2), (16, 2),
            (7, 3), (8, 3), (9, 3), (10, 3), (11, 3), (12, 3), (13, 3),
            (14, 3), (15, 3), (16, 3),
            (7, 4), (8, 4), (9, 4), (10, 4), (11, 4), (12, 4), (13, 4),
            (14, 4), (15, 4), (16, 4),
            (8, 5), (9, 5), (10, 5), (11, 5), (12, 5), (13, 5), (14, 5),
            (15, 5), (16, 5)]
        steady_ground_truth_br_arr = get_sen_loc_arrary(
            dim, steady_ground_truth_br)
        # top left ground truth
        steady_ground_truth_tl = [
            (1, 7), (2, 7), (3, 7),
            (1, 8), (2, 8), (3, 8), (4, 8),
            (1, 9), (2, 9), (3, 9), (4, 9), (5, 9),
            (2, 10), (3, 10), (4, 10), (5, 10), (6, 10),
            (2, 11), (3, 11), (4, 11), (5, 11), (6, 11),
            (2, 12), (3, 12), (4, 12), (5, 12), (6, 12),
            (2, 13), (3, 13), (4, 13), (5, 13), (6, 13),
            (2, 14), (3, 14), (4, 14), (5, 14), (6, 14),
            (0, 15), (1,15), (2, 15), (3, 15), (4, 15), (5, 15), (6, 15),
            (0, 16), (1, 16), (2, 16), (3, 16), (4, 16), (5, 16), (6, 16),
        ]
        steady_ground_truth_tl_arr = get_sen_loc_arrary(
            dim, steady_ground_truth_tl)
        return (steady_ground_truth_br_arr, steady_ground_truth_tl_arr)
    else: # ground truth only exists for above specified events and experiments
        return None, None

def get_ground_truth_r(experiment_name, evaluate_event, start_glob_time_at,
                       time_idx_vec, tsEpochDuration, dim, num_nodes):
    """Get the ground truth grid point indicators as well as vector with epochs
    in which ground truth is known.

    Parameters
    ----------
    experiment_name : string
        The experiment name
    evaluate_event : string
        The event name
    start_glob_time_at : _type_
        _description_
    time_idx_vec : numpy array
        The selected epoch indexes.
    tsEpochDuration : int
        The epoch duration.
    dim : tuple of int
        the dimensions of the field
    num_nodes : int
        The number of nodes in the network

    Returns
    -------
    tuple
        ground truth indicators for sensors and all grid points, epoch indexes
        in which ground truth is known.
    """
    
    (true_H1_crd_br, true_H1_crd_tl) = get_ground_truth_crd(
        experiment_name, evaluate_event, dim)
    
    r_tru = np.zeros((len(time_idx_vec), dim[0], dim[1])) + np.nan
    r_tru_sen = np.zeros((len(time_idx_vec), num_nodes)) + np.nan

    if experiment_name == 'eusipco' and evaluate_event == 'scenario_1':
        start_static_time, end_static_time = get_ground_truth_times(
            experiment_name, evaluate_event)
        start_to_end_static_idx_lst = start_end_to_index_list_renewed(
            [[start_static_time, end_static_time]], start_glob_time_at,
            tsEpochDuration)
        start_steady_mc_idx = np.where(
            time_idx_vec==start_to_end_static_idx_lst[0][0])[0][0]
        end_steady_mc_idc = np.where(
            time_idx_vec==start_to_end_static_idx_lst[0][-1])[0][0]
        mc_steady_idc_vec = np.arange(
            start_steady_mc_idx, end_steady_mc_idc, 1, dtype=int)

        for idx in mc_steady_idc_vec:
            this_run_truth = np.zeros(dim)
            this_run_truth[true_H1_crd_br[:, 1], true_H1_crd_br[:, 0]] = 1
            this_run_truth[true_H1_crd_tl[:, 1], true_H1_crd_tl[:, 0]] = 1
            r_tru[idx, :, :] = this_run_truth
            r_tru[idx, :, :] = this_run_truth
    elif evaluate_event == 'scenario_3' or evaluate_event == 'bonus_first_null':
        r_tru = np.zeros((len(time_idx_vec), dim[0], dim[1]))
        r_tru_sen = np.zeros((len(time_idx_vec), num_nodes))
        mc_steady_idc_vec = time_idx_vec
    else:
        r_tru = None
        r_tru_sen = None
        mc_steady_idc_vec = np.array([], dtype=int)
    return r_tru, r_tru_sen, mc_steady_idc_vec

def get_ground_truth_times(experiment_name, evaluate_event):
    """Returns the beginning and end of periods fpr which a ground truth is
    known.

    Parameters
    ----------
    experiment_name : string
        The experiment name
    evaluate_event : string
        The event name

    Returns
    -------
    tuple
        The start and end times of the ground truth periods.
    """
    if experiment_name == 'eusipco':
        if evaluate_event == 'scenario_1':
            start_static_time = datetime.datetime(2024, 3, 1, 14, 52, 0)
            end_static_time = datetime.datetime(2024, 3, 1, 15, 14, 0)
        else:
            start_static_time = None
            end_static_time = None
    else:
        start_static_time = None
        end_static_time = None
    return start_static_time, end_static_time

def get_selected_alternative(experiment_name, evaluate_event, null_sfx):
    """returns the selected alternative epoch index list and start/end times.

    Parameters
    ----------
    experiment_name : string
        The experiment name
    evaluate_event : string
        The event name

    Returns
    -------
    tuple
        the selected alternative epoch index list and start/end times.
    """
    (start_end_lst_H0,
     start_end_lst_H1_walking) = get_true_label_start_and_end_time_lsts(
        experiment_name, null_sfx)

    (start_glob_time_at, tsEpochDuration, _, _) = get_experiment_parameters(
        experiment_name)
    
    idx_lst_H0 = start_end_to_index_list_renewed(
        start_end_lst_H0, start_glob_time_at, tsEpochDuration)
    idx_lst_H1_walking = start_end_to_index_list_renewed(
        start_end_lst_H1_walking, start_glob_time_at, tsEpochDuration)
    if experiment_name == 'eusipco':
        if evaluate_event == 'scenario_3':
            selected_alternative_epochs = [idx_lst_H0[10]] # example null
            selected_alternative_start_end = start_end_lst_H0[10]
        elif evaluate_event == 'scenario_1':
            selected_alternative_epochs = [idx_lst_H1_walking[0]] # must be a list of
            # lists! So if only one alternative selected, put brackets around. If
            # more than one, dont do that
            selected_alternative_start_end = start_end_lst_H1_walking[0]
        elif evaluate_event == 'scenario_2':
            selected_alternative_epochs = [idx_lst_H1_walking[1]] # must be a list of
            # lists! So if only one alternative selected, put brackets around. If
            # more than one, dont do that
            selected_alternative_start_end = start_end_lst_H1_walking[1]
    elif experiment_name == 'bonus':
        if evaluate_event == 'bonus_example_null':
            selected_alternative_epochs = [idx_lst_H0[0]] # first_null
            selected_alternative_start_end = start_end_lst_H0[0]
        elif evaluate_event == 'bonus_first_walk':
            selected_alternative_epochs = [idx_lst_H1_walking[0]] # must be a list of
            # lists! So if only one alternative selected, put brackets around. If
            # more than one, dont do that
            selected_alternative_start_end = start_end_lst_H1_walking[0]
        elif evaluate_event == 'bonus_second_walk':
            selected_alternative_epochs = [idx_lst_H1_walking[1]] # must be a list of 
            # lists! So if only one alternative selected, put brackets around. If
            # more than one, dont do that
            selected_alternative_start_end = start_end_lst_H1_walking[1]
    return selected_alternative_epochs, selected_alternative_start_end