#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Python script to process the data recorded with SiNet that has been stored 
as a csv files before. The results this data processing are stored in pickle
files which enables subsequent analysis and plotting.

PLEASE CITE THE CORRESPONDING PAPERS IF YOU USE THIS CODE IN YOUR WORK!

    [Goelz2024EUSIPCO]:
        Gölz et al., "Spatial Inference Network: Indoor Proximity
        Detection via Multiple Hypothesis Testing"
        DOI: TBA
    [Goelz2022a]
        Gölz et al. "Multiple Hypothesis Testing Framework for Spatial Signals"
        DOI: 10.1109/TSIPN.2022.3190735

@author: Martin Goelz
"""
# =============================================================================
# Instructions on how to use this file to recreate the results from
# [Goelz2024EUSIPCO].
#   1) Adjust data_directory to match your local path to where data is stored.
#   2) Chose experiment_name and evaluate_event according to what event p-vals
#      are to be calculated for.
#   3) Execute script and move then to produce_results.py
# =============================================================================
# %% setup: imports
import numpy as np

import pandas as pd

import os
import sys 
import datetime

from utilities.tuda_colors import *
from utilities.aux import (get_active_node_nam_lst,
                           start_end_to_index_list_renewed,
                           create_hist_legends_list, learn_all_null_edfs,
                           get_pvals_from_edfs_sgl_node)
from utilities.physical_setup import (
    dim, sen_loc_arr, get_experiment_parameters,
    get_true_label_start_and_end_time_lsts, get_selected_alternative)

# %% setup: user-defined parameters
experiment_name = 'bonus'  # the name of the conducted experiment
# Parameter values are specific to the experiment_name, so whenever you change
# parameters, make sure to use a different experiment_name

# This following event is what p-values are being computed for
evaluate_event = "bonus_second_walk" # options are:
# for eusipco: scenario_{1, 2, 3}
# for bonus: bonus_example_null, bonus_first_walk, bonus_second_walk

active_node_idc = np.arange(54)  # the indexes of the used nodes. There are at
# most 54 nodes.

null_sfx = ''  # a suffix that can be used to discriminate between different
# choices for the null distribution. implemented choices are:
#       '':         which uses any data point labelled as when H0 was true
#                   during the first ten days of the experiment
#       '_everything': Uses data from the entire duration of the experiment,
#                      depending on when the experiment was terminated.

# Define the set of nodes for which things are to be investigated. Either a 
# list with node names or "all" to select all active nodes
selected_nodes = [
    "Node4", "Node11", "Node5", "Node25", "Node24", "Node15", "Node33"]
selected_nodes = 'all' # this selects all active nodes for investigation

 # %% setup: automated initializations
data_directory = os.path.join("..", "csv", experiment_name)

# Under this name, the pickle file with the p-values for further processing
# will be stored.
file_name = evaluate_event + null_sfx

dat_path = os.path.join('..', 'data')

os.makedirs(dat_path, exist_ok=True)

# %% setup: processing user inputs
print("Running " + evaluate_event + null_sfx)

active_node_nam = get_active_node_nam_lst(active_node_idc)

(start_glob_time_at, tsEpochDuration,
 tsWindowLength, _) = get_experiment_parameters(experiment_name)

if isinstance(selected_nodes, str) and selected_nodes == 'all':
    selected_nodes = active_node_nam

# %% setup: Define H0 and H1 periods for the different experiments
(start_end_lst_H0,
 start_end_lst_H1_walking) = get_true_label_start_and_end_time_lsts(
     experiment_name, null_sfx)

idx_lst_H0 = start_end_to_index_list_renewed(
    start_end_lst_H0, start_glob_time_at, tsEpochDuration)
idx_lst_H1_walking = start_end_to_index_list_renewed(
    start_end_lst_H1_walking, start_glob_time_at, tsEpochDuration)

# create legends list
legends_lst = create_hist_legends_list(
    start_end_lst_H0, start_end_lst_H1_walking)

# flat all null index 
complete_idx_lst_H0 = np.array(
    [idx for idx_vec in idx_lst_H0 for idx in idx_vec])

# select alternative for the given event
(selected_alternative_epochs,
 selected_alternative_start_end) = get_selected_alternative(
     experiment_name, evaluate_event, null_sfx)

# %% Learn the empirical null distributions for all selected nodes
edf_lst, null_sizes = learn_all_null_edfs(
    data_directory, idx_lst_H0, tsWindowLength, selected_nodes,
    which_data="humid")

# %% Compute p-values under alternative from learned empirical nulls
pvals_emp_alt = []
for alt_idx_lst in selected_alternative_epochs:
    pvals_this_alt = {}
    for (node, edf, null_size) in zip(selected_nodes, edf_lst, null_sizes):
        pvals_this_alt[node] = get_pvals_from_edfs_sgl_node(
            os.path.join(data_directory, node + '_data.csv'), 
            edf, null_size, alt_idx_lst, tsWindowLength, which_data="humid",
            scatter=False, fullsize=True)
    pvals_emp_alt.append(pvals_this_alt)

# %% Initializing the things needed to create a pickle file with this data
# (only to be done once for each scenario!)
fd_dim = dim

sen_cds = np.zeros(
    (len(selected_alternative_epochs[0]), len(selected_nodes), 2), dtype=int)
p = np.zeros((len(selected_alternative_epochs[0]), len(selected_nodes)))
for node_idx, node in enumerate(selected_nodes):
    p[:, node_idx] = pvals_emp_alt[0][node]
    sen_cds[:, node_idx, :] = np.tile(sen_loc_arr[node_idx][np.newaxis, :],
                                      [len(selected_alternative_epochs[0]), 1])

# %% Save pickle file
custom_pval = pd.DataFrame(
            {"fd_dim": [fd_dim],
            "p": [p],
            "sen_cds": [sen_cds],
            "null_edf_sizes": [null_sizes],
            #"r_tru": [r_tru]  # This line is optional! Only if you
            # have a ground truth!
            })

custom_pval.to_pickle(os.path.join(dat_path, file_name + '.pkl'))
