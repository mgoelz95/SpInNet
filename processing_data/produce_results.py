#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Takes p-values for a certain experiment and event previous computed and
stored via process_sensor_data_to_pvals.py and applies lfdr-smom and all its
variants to obtain the areas of anomalous signal behavior. Also contains a
variety of plotting capabilities.

PLEASE CITE THE CORRESPONDING PAPERS IF YOU USE THIS CODE IN YOUR WORK!

    [Goelz2024EUSIPCO]:
        Gölz et al., "Spatial Inference Network: Indoor Proximity
        Detection via Multiple Hypothesis Testing"
        DOI: TBA
    [Goelz2022a]
        Gölz et al. "Multiple Hypothesis Testing Framework for Spatial Signals"
        DOI: 10.1109/TSIPN.2022.3190735
    [Goelz2022b]
        Gölz et al. "Improving inference for spatial signals by contextual
        false discovery rates"
        DOI: 10.1109/ICASSP43922.2022.9747596
    [Goelz2022c]
        Gölz et al. "Estimating Test Statistic Distributions for Multiple
        Hypothesis Testing in Sensor Networks"
        DOI: 10.1109/CISS53076.2022.9751186

@author: Martin Goelz
"""
# =============================================================================
# Instructions on how to use this file to recreate the results from
# [Goelz2024EUSIPCO].
#   1) Run process_data.py first for the experiment and event that you are 
#      interested in!
#   2) Similar to process_data.py, adjust the paths to the stored data and the
#      location to where you want to store results if necessary.
#   3) Then run this script. Might take a while, depending on the power of your
#      machine.
#   4) Finally, compare the plots to the plots from the paper. They are the
#      same! (Slight variations due different random numbers are expected).
# =============================================================================
 # %% setup: imports
import numpy as np
import scipy.stats as stats
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as colors

from scipy.ndimage import uniform_filter1d

import datetime

import sys
import os

from utilities.tuda_colors import *
from utilities.aux import (
    is_notebook, start_end_to_index_list_renewed, plot_evolution_raw_data,
    plot_evolution_pvals_fd, plot_evolution_lfdrs, plot_evolution_all_lfdrs,
    plot_evolution_rej, plot_evolution_all_rej,
    plot_evolution_all_side_by_side, plot_av_det_prob)
from utilities.physical_setup import (
    sen_loc_arr as sen_loc,
    anchor_loc_arr as imported_anchor_loc,
    get_experiment_parameters, get_event_start_end_times, get_ground_truth_crd,
    get_ground_truth_r)
from utilities.parameters import get_par_smom, get_par_spa_var

import spatialmht.field_handling as fd_hdl
import spatialmht.lfdr_estimation as lfdr_est
import spatialmht.detectors as det
import spatialmht.analysis as anal

# %% setup: things needed for VSCode
if is_notebook():
    get_ipython().run_line_magic('matplotlib', 'ipympl')
else:
    plt.ion() # Needed in VSCode

# %% setup: user-defined parameters
experiment_name = 'bonus'  # the name of the conducted experiment
# Parameter values are specific to the experiment_name, so whenever you change
# parameters, make sure to use a different experiment_name

# This following event is what p-values are being computed for
evaluate_event = "bonus_first_walk" # options are:
# for eusipco: scenario_{1, 2, 3}
# for bonus: bonus_example_null, bonus_first_walk, bonus_second_walk

null_sfx = ''  # a suffix that can be used to discriminate between different
# choices for the null distribution. implemented choices are:
#       '':         which uses any data point labelled as when H0 was true
#                   during the first ten days of the experiment
#       '_everything': Uses data from the entire duration of the experiment,
#                      depending on when the experiment was terminated.

# simulation parameters
use_anchors = True # If true, lfdr =1 in places where we know that null is true
# Should always be true.
ma_filter_len = 3 # number of epochs across which moving average filter is
# applied to lfdrs. 3 works well usually (when one epoch is 6 seconds long).
# reasoning: a person cannot just spawn or disappear -> moving average filter
# adjusts lfdr to spatio-temporally smooth nature of observed phenomenon

# Specify here all nominal FDR levels that results shall be computed for!
alp_vec = np.array([0.01, 0.02, 0.05, 0.07, 0.10, 0.15, 0.2, .25, .3])

# plotting parameters
show_alp_val = 0.1 # showing the detection maps for this target FDR level

figsize = (12.5, 7.5)
 #%% setup: user input - which things to plot
# lfdr plots
plot_raw_data_evol = False
plot_pval_evol = False
plot_lfdr_evol = False
plot_lfdr_sen_evol = False
plot_all_lfdr_sen_evol = False
plot_all_lfdr_evol = False
plot_lfdr_evol_ma = False 

# rejection plots
plot_sen_rej_evol = False
plot_rej_evol = False
plot_all_sen_rej_evol = False
plot_all_rej_evol = False
plot_rej_evol_ma = False

# side by side plots
plot_all_sen_sbs_evol = False
plot_all_sbs_evol = False

# ma vs non-ma
plot_sen_evol_ma_vs_non_ma = False
plot_evol_ma_vs_non_ma = False

 # %% setup: automated initializations
FD_SCEN = evaluate_event + null_sfx

print("Running " + FD_SCEN)

FIELD_MODE = "custom"  # Do not change. Has to be custom to process real-world
# data. 
SEN_CFG = FIELD_MODE  # Do not change this.

if use_anchors:
    anchor_nam = 'all-anchors'
else:
    anchor_nam = ''

# paths
data_directory = os.path.join("..", "csv", experiment_name)

dat_path = os.path.join('..', 'data', FD_SCEN)

if use_anchors:
    res_path = os.path.join('..', 'results', FD_SCEN, SEN_CFG, anchor_nam)
else:    
    res_path = os.path.join('..', 'results', FD_SCEN, SEN_CFG)

# create dat_path if doesnt exist
if not os.path.isdir(dat_path):
    os.makedirs(dat_path, exist_ok=True)
# create res_path if dont exist
if not os.path.isdir(res_path):
    os.makedirs(res_path, exist_ok=True)

# plot parameters
show_alp_vec_idx = np.where(alp_vec == show_alp_val)[0][0]

# experiment and event-related things
(start_glob_time_at, tsEpochDuration,
 tsWindowLength, _) = get_experiment_parameters(experiment_name)
event_start_end_times = get_event_start_end_times(
    experiment_name, evaluate_event, null_sfx)

# create measurement time vector
time_idx_vec = start_end_to_index_list_renewed(
    [event_start_end_times], start_glob_time_at, tsEpochDuration)
time_idx_vec = time_idx_vec[0]

# %% setup: load data and field properties
# load the field
stored_fd_info = pd.read_pickle(os.path.join(dat_path, '..', FD_SCEN + '.pkl'))
fd, est_fd = fd_hdl.rd_in_fds(FD_SCEN, SEN_CFG, dat_path)
fully_loaded = fd.n == est_fd.n

all_node_names = []
max_num_nodes = 54
available_nodes = np.ones(max_num_nodes, dtype=bool)

dim = stored_fd_info["fd_dim"][0]
sen_loc_arr = stored_fd_info["sen_cds"][0]
num_nodes = sen_loc_arr.shape[1]

# create list of all node names
for n in np.arange(num_nodes):
    all_node_names.append("Node" + str(n +1))

if anchor_nam == 'all-anchors':
    anchor_loc = imported_anchor_loc
else:
    anchor_loc = []

# %% setup: define ground truth for steady scenarios
(true_H1_crd_br, true_H1_crd_tl) = get_ground_truth_crd(
    experiment_name, evaluate_event, dim)

r_tru, r_tru_sen, mc_steady_idc_vec = get_ground_truth_r(
    experiment_name, evaluate_event, start_glob_time_at, time_idx_vec,
    tsEpochDuration, dim, num_nodes)

if r_tru is not None:
    fd.r_tru = r_tru.reshape(len(time_idx_vec), np.prod(dim))

# %% load or calculate the lfdrs for all my lfdr estimation methods
# first make sure smom parameters have been stored, otherwise create pickle
# file with the parameters in the data path
get_par_smom(dat_path)
# now do the same for the spatial varying null probability parameters (needed
# for clfdrs)
get_par_spa_var(dat_path)

# load lfdrs at sensors and interpolated lfdrs
[lfdrs_sen_smom, f_p_sen_smom, f1_p_sen_smom, pi0_sen_smom,
ex_time_sen_smom] = (lfdr_est.est_lfdrs(
    est_fd, res_path, True, "smom",
    [dat_path, 50, 'stan', None, 1]))

lfdrs_ipl_smom = lfdr_est.ipl_lfdrs(
    res_path, 'smom-sen',
    np.concatenate(
        [lfdrs_sen_smom, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)

# EM
[lfdrs_sen_smom_em, f_p_sen_smom_em, f1_p_sen_smom_em, pi0_sen_smom_em,
    ex_time_sen_smom_em] = (lfdr_est.est_lfdrs(
        est_fd, res_path, True, "smom-em",
        [50, 1e-5]))
lfdrs_ipl_smom_em = lfdr_est.ipl_lfdrs(
    res_path, 'smom-em-sen',
    np.concatenate(
        [lfdrs_sen_smom_em, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)

# spatially varying prior without EM
[clfdrs_sen_smom_sls, pi0_sen_smom_sls] = (lfdr_est.est_clfdrs(
    est_fd, res_path, True, "smom-sls",
    [dat_path, 50, 'stan', 'smom-sen']))
[clfdrs_sen_smom_sns, pi0_sen_smom_sns] = (lfdr_est.est_clfdrs(
    est_fd, res_path, True, "smom-sns",
    [dat_path, 50, 'stan', 'smom-sen']))
clfdrs_ipl_smom_sls = lfdr_est.ipl_lfdrs(
    res_path, 'smom-sen-sls',
    np.concatenate(
        [clfdrs_sen_smom_sls, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)
clfdrs_ipl_smom_sns = lfdr_est.ipl_lfdrs(
    res_path, 'smom-sen-sns',
        np.concatenate(
        [clfdrs_sen_smom_sns, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)
# spatially varying prior with EM
[clfdrs_sen_smom_em_sls, pi0_sen_smom_em_sls] = (lfdr_est.est_clfdrs(
    est_fd, res_path, True, "smom-sls",
    [dat_path, 50, 'stan', 'smom-em-sen']))
[clfdrs_sen_smom_em_sns, pi0_sen_smom_em_sns] = (lfdr_est.est_clfdrs(
    est_fd, res_path, True, "smom-sns",
    [dat_path, 50, 'stan', 'smom-em-sen']))
clfdrs_ipl_smom_em_sls = lfdr_est.ipl_lfdrs(
    res_path, 'smom-em-sen-sls',
    np.concatenate(
        [clfdrs_sen_smom_em_sls, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)
clfdrs_ipl_smom_em_sns = lfdr_est.ipl_lfdrs(
    res_path, 'smom-em-sen-sns',
    np.concatenate(
        [clfdrs_sen_smom_em_sns, np.ones((fd.n_MC, len(anchor_loc)))], axis=1),
    np.concatenate([est_fd.sen_cds,
        np.tile(anchor_loc[np.newaxis, :, :], [fd.n_MC, 1, 1])], axis=1),
    est_fd.dim, fd.n)

# %% apply moving average filter to sensor lfdrs and interpolated lfdrs
# concatenate all different typoes of sensor lfdrs in one list
met_names = ['smom', 'smom-em', 'sms-sls', 'smom-sns', 'smom-em-sls',
            'smom-em-sns']
all_lfdrs_sen = [
    lfdrs_sen_smom, lfdrs_sen_smom_em, clfdrs_sen_smom_sls,
    clfdrs_sen_smom_sns, clfdrs_sen_smom_em_sls, clfdrs_sen_smom_em_sns]
all_lfdrs_ipl = [
    lfdrs_ipl_smom, lfdrs_ipl_smom_em, clfdrs_ipl_smom_sls,
    clfdrs_ipl_smom_sns, clfdrs_ipl_smom_em_sls, clfdrs_ipl_smom_em_sns]
# apply moving average filter
all_lfdrs_sen_ma = []

for lfdrs, name in zip(all_lfdrs_sen, met_names):
    all_lfdrs_sen_ma_this_node = np.zeros((fd.n_MC, num_nodes)) + np.nan
    for sen_idx in np.arange(num_nodes):
        nan_borders = np.concatenate([
            np.array([-1]), np.where(np.isnan(lfdrs[:, sen_idx]))[0],
            np.array([fd.n_MC])])
        for border_idx in np.arange(0, len(nan_borders)-1):
            try:
                all_lfdrs_sen_ma_this_node[nan_borders[
                    border_idx]+1:nan_borders[border_idx+1], sen_idx] = (
                        uniform_filter1d(
                            lfdrs[nan_borders[border_idx]+1:nan_borders[
                                border_idx+1], sen_idx], size=ma_filter_len,
                                origin=int(ma_filter_len/2), mode='nearest',
                                axis=0))
            except ValueError:
                all_lfdrs_sen_ma_this_node[nan_borders[
                    border_idx]+1:nan_borders[border_idx+1], sen_idx] = (
                        uniform_filter1d(
                            lfdrs[nan_borders[border_idx]+1:nan_borders[
                                border_idx+1], sen_idx], size=ma_filter_len,
                                origin=int(ma_filter_len/2)-1, mode='nearest',
                                axis=0))
    all_lfdrs_sen_ma.append(all_lfdrs_sen_ma_this_node)

all_lfdrs_ipl_ma = []
try:
    for lfdrs, name in zip(all_lfdrs_ipl, met_names):
        all_lfdrs_ipl_ma.append(uniform_filter1d(
            lfdrs, size=ma_filter_len, origin=int(ma_filter_len/2),
            mode='nearest', axis=0))
except:
    for lfdrs, name in zip(all_lfdrs_ipl, met_names):
        all_lfdrs_ipl_ma.append(uniform_filter1d(
            lfdrs, size=ma_filter_len, origin=int(ma_filter_len/2)-1,
            mode='nearest', axis=0))

# %% create the detection results
# lfdrs and interpolated lfdrs
det_res_sen_smom = det.apply_lfdr_detection(
    lfdrs_sen_smom, est_fd.r_tru, alp_vec, 'lfdr-sMoM at sensors',
    sen=True)
det_res_ipl_smom = det.apply_lfdr_detection(
    lfdrs_ipl_smom, fd.r_tru, alp_vec, 'lfdr-sMoM at all grid points',
    sen=False)

# em
det_res_sen_smom_em = det.apply_lfdr_detection(
    lfdrs_sen_smom_em, est_fd.r_tru, alp_vec, 'lfdr-sMoM-EM at sensors',
    sen=True)
det_res_ipl_smom_em = det.apply_lfdr_detection(
    lfdrs_ipl_smom_em, fd.r_tru, alp_vec,
    'lfdr-sMoM-EM at all grid points', sen=False)

# spatially varying prior
det_res_sen_smom_sls = det.apply_lfdr_detection(
    clfdrs_sen_smom_sls, est_fd.r_tru, alp_vec,
    'clfdr-sMoM-SLS at sensors', sen=True)
det_res_sen_smom_sns = det.apply_lfdr_detection(
    clfdrs_sen_smom_sns, est_fd.r_tru, alp_vec,
    'clfdr-sMoM-SNS at sensors', sen=True)
det_res_ipl_smom_sls = det.apply_lfdr_detection(
    clfdrs_ipl_smom_sls, fd.r_tru, alp_vec,
    'clfdr-sMoM-SLS at all grid points', sen=False)
det_res_ipl_smom_sns = det.apply_lfdr_detection(
    clfdrs_ipl_smom_sns, fd.r_tru, alp_vec,
    'clfdr-sMoM-SNS at all grid points', sen=False)

# spatially varying prior with EM
det_res_sen_smom_em_sls = det.apply_lfdr_detection(
    clfdrs_sen_smom_em_sls, est_fd.r_tru, alp_vec,
    'clfdr-sMoM-EM-SLS at sensors', sen=True)
det_res_sen_smom_em_sns = det.apply_lfdr_detection(
    clfdrs_sen_smom_em_sns, est_fd.r_tru, alp_vec,
    'clfdr-sMoM-EM-SNS at sensors', sen=True)
det_res_ipl_smom_em_sls = det.apply_lfdr_detection(
    clfdrs_ipl_smom_em_sls, fd.r_tru, alp_vec,
    'clfdr-sMoM-EM-SLS at all grid points', sen=False)
det_res_ipl_smom_em_sns = det.apply_lfdr_detection(
    clfdrs_ipl_smom_em_sns, fd.r_tru, alp_vec,
    'clfdr-sMoM-EM-SNS at all grid points', sen=False)

# concatenate all sensor detection results in one list
all_res_sen = [det_res_sen_smom, det_res_sen_smom_em, det_res_sen_smom_sls,
det_res_sen_smom_sns, det_res_sen_smom_em_sls, det_res_sen_smom_sns]

# concatenate all ipl detection results in one list
all_res_ipl = [det_res_ipl_smom, det_res_ipl_smom_em, det_res_ipl_smom_sls,
det_res_ipl_smom_sns, det_res_ipl_smom_em_sls, det_res_ipl_smom_sns]

# Moving average detection results
all_res_sen_ma = []
all_res_ipl_ma = []
for lfdrs_sen, lfdrs_ipl, name in zip(
    all_lfdrs_sen_ma, all_lfdrs_ipl_ma, met_names):
    all_res_sen_ma.append(det.apply_lfdr_detection(
        lfdrs_sen, est_fd.r_tru, alp_vec, name + 'at sensors',
        sen=True))
    all_res_ipl_ma.append(det.apply_lfdr_detection(
        lfdrs_ipl, fd.r_tru, alp_vec, name + 'at all grid point',
        sen=True))

# %% Evolution plots: raw data, p-values and lfdrs
if plot_raw_data_evol and not is_notebook():
     plot_evolution_raw_data(data_directory, event_start_end_times[0],
                            event_start_end_times[1], start_glob_time_at,
                            tsEpochDuration, sen_loc_arr[0],
                            evaluate_event, click=True, which_data="humid",
                            time_between_updates=int(tsEpochDuration/1000),
                            dim=dim)
if plot_pval_evol and not is_notebook():
    plot_evolution_pvals_fd(fd, time_idx_vec, start_glob_time_at, tsEpochDuration,
                            sen_loc_arr[0], click=True,
                            time_between_updates=int(tsEpochDuration/1000))

if plot_lfdr_sen_evol and not is_notebook():
    for sensor_lfdr, name in zip(all_lfdrs_sen, met_names):
        plot_evolution_lfdrs(
            sensor_lfdr, fd.dim, time_idx_vec, start_glob_time_at,
            tsEpochDuration, fd.sen_cds[0, :].astype(int), name,
            anchor_cds=anchor_loc, click=True, sen_only=True,
            time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

if plot_lfdr_evol and not is_notebook():
    for sensor_lfdr, name in zip(all_lfdrs_ipl, met_names):
        plot_evolution_lfdrs(
            sensor_lfdr, fd.dim, time_idx_vec, start_glob_time_at,
            tsEpochDuration, fd.sen_cds[0, :].astype(int), name,
            anchor_cds=anchor_loc, click=True, sen_only=False,
            time_between_updates=int(tsEpochDuration/1000), figsize=figsize)
        
if plot_all_lfdr_sen_evol and not is_notebook():
    plot_evolution_all_lfdrs(
        all_lfdrs_sen, fd.dim, time_idx_vec, start_glob_time_at,
        tsEpochDuration, fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True, sen_only=True,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

if plot_all_lfdr_evol and not is_notebook():
    plot_evolution_all_lfdrs(
        all_lfdrs_ipl, fd.dim, time_idx_vec, start_glob_time_at,
        tsEpochDuration, fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

# %% Evolution plots: Detection results
if plot_sen_rej_evol and not is_notebook():
    for det_res, name in zip(all_res_sen, met_names):
        plot_evolution_rej(det_res[show_alp_vec_idx], fd.dim, time_idx_vec,
                           start_glob_time_at, tsEpochDuration, sen_loc_arr[0],
                           name, anchor_cds=anchor_loc,
                           sen_only=True, click=True)

if plot_rej_evol and not is_notebook():
    for det_res, name in zip(all_res_ipl, met_names):
        plot_evolution_rej(det_res[show_alp_vec_idx], fd.dim, time_idx_vec,
                           start_glob_time_at, tsEpochDuration, sen_loc_arr[0],
                           name, anchor_cds=anchor_loc,
                           sen_only=False, click=True)

if plot_all_sen_rej_evol and not is_notebook():
    all_res_sen_sel = [x[show_alp_vec_idx] for x in all_res_sen]
    plot_evolution_all_rej(
        all_res_sen_sel, fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True,
        sen_only=True, time_between_updates=int(tsEpochDuration/1000),
        figsize=figsize)

if plot_all_rej_evol and not is_notebook():
    all_res_sel = [x[show_alp_vec_idx] for x in all_res_ipl]
    plot_evolution_all_rej(
        all_res_sel, fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)
# %% side by side test
if plot_all_sbs_evol and not is_notebook():
    all_res_sel = [x[show_alp_vec_idx] for x in all_res_ipl]
    plot_evolution_all_side_by_side(all_res_sel, all_lfdrs_ipl,
        fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

# %% Plot all moving average results side-by-side
ma_met_names = [x + " ma" for x in met_names]
if plot_all_sen_sbs_evol and not is_notebook():
    all_res_sel = [x[show_alp_vec_idx] for x in all_res_sen_ma]
    plot_evolution_all_side_by_side(all_res_sel, all_lfdrs_sen_ma,
        fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), ma_met_names,
        anchor_cds=anchor_loc, click=True, sen_only=True,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

if plot_all_sbs_evol and not is_notebook():
    all_res_sel = [x[show_alp_vec_idx] for x in all_res_ipl_ma]
    plot_evolution_all_side_by_side(all_res_sel, all_lfdrs_ipl_ma,
        fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), ma_met_names, anchor_cds=anchor_loc,
        click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

# %% Plot moving average ipl lfdrs
# select method of choice
all_lfdrs_sel = [all_lfdrs_ipl_ma[4]]
met_names_this_plt = ['smom-em-sls-ma']

if plot_lfdr_evol_ma and not is_notebook():
    plot_evolution_all_lfdrs(
        all_lfdrs_sel, fd.dim, time_idx_vec, start_glob_time_at,
        tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names_this_plt, anchor_cds=anchor_loc,
        click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)

# %% Plot moving average ipl rej
# select method of choice
all_res_sel = [all_res_ipl_ma[4][show_alp_vec_idx]]
met_names_this_plt = ['smom-em-sls-ma']

if plot_rej_evol_ma and not is_notebook():
    plot_evolution_all_rej(
        all_res_sel, fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names,
        anchor_cds=anchor_loc, click=True, sen_only=False,
        time_between_updates=int(tsEpochDuration/1000), figsize=figsize)
# %% Plot moving average vs non-moving average sen side by side for smom-em-sls
# and standard smom-em (without clfdr)
all_res_sel = [all_res_sen[1][show_alp_vec_idx],
                all_res_sen[4][show_alp_vec_idx],
                all_res_sen_ma[1][show_alp_vec_idx],
                all_res_sen_ma[4][show_alp_vec_idx]]
all_lfdrs_sel = [all_lfdrs_sen[1], all_lfdrs_sen[4], all_lfdrs_sen_ma[1],
                    all_lfdrs_sen_ma[4]]
if plot_sen_evol_ma_vs_non_ma and not is_notebook():
    met_names_this_plt = [
        'smom-em', 'smom-em-sls', 'smom-em-ma', 'smom-em-sls-ma']
    plot_evolution_all_side_by_side(all_res_sel, all_lfdrs_sel,
        fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names_this_plt,
        anchor_cds=anchor_loc, click=True,
        sen_only=True, time_between_updates=int(tsEpochDuration/1000),
        figsize=figsize)
    
# %% Plot moving average vs non-moving average ipl side by side for smom-em-sls
# and standard smom-em (without clfdr)
all_res_sel = [all_res_ipl[1][show_alp_vec_idx],
                all_res_ipl[4][show_alp_vec_idx],
                all_res_ipl_ma[1][show_alp_vec_idx],
                all_res_ipl_ma[4][show_alp_vec_idx]]
all_lfdrs_sel = [all_lfdrs_ipl[1], all_lfdrs_ipl[4], all_lfdrs_ipl_ma[1],
                    all_lfdrs_ipl_ma[4]]
met_names_this_plt = ['smom-em', 'smom-em-sls', 'smom-em-ma', 'smom-em-sls-ma']
if plot_evol_ma_vs_non_ma and not is_notebook():
    plot_evolution_all_side_by_side(all_res_sel, all_lfdrs_sel,
        fd.dim, time_idx_vec, start_glob_time_at, tsEpochDuration,
        fd.sen_cds[0, :].astype(int), met_names_this_plt,
        anchor_cds=anchor_loc, click=True,
        sen_only=False, time_between_updates=int(tsEpochDuration/1000),
        figsize=figsize)

# %% Compute "localization probability" and FDRs
# localization probability: Percentage of epochs, in wich someone was detected
# somewhere within the ground true area (calculated independently for top left
# and bottom right).
all_res_sel = [all_res_ipl[1][show_alp_vec_idx],
                all_res_ipl[4][show_alp_vec_idx],
                all_res_ipl_ma[1][show_alp_vec_idx],
               all_res_ipl_ma[4][show_alp_vec_idx]]
met_names_res = ['smom-em', 'smom-em-sls', 'smom-em-ma', 'smom-em-sls-ma']

if experiment_name == 'eusipco' and evaluate_event == 'scenario_1':
    br_detected = np.zeros((len(all_res_sel), len(mc_steady_idc_vec)))
    tl_detected = np.zeros((len(all_res_sel), len(mc_steady_idc_vec)))
    for idx, res in enumerate(all_res_sel):
        for mc_idx, mc in enumerate(mc_steady_idc_vec):
            br_detected[idx, mc_idx] = np.any(res.r_det[mc].reshape(dim)[
                true_H1_crd_br[:, 1], true_H1_crd_br[:, 0]])
            tl_detected[idx, mc_idx] = np.any(res.r_det[mc].reshape(dim)[
                true_H1_crd_tl[:, 1], true_H1_crd_tl[:, 0]])
        print("--------- Nominal FDR: {} | FDR/TL Loc prob".format(
            alp_vec[show_alp_vec_idx]) + "/BR loc prob---------")
        print("{}: {:.2f} / {:.2f} / {:.2f} ".format(
            met_names_res[idx], np.mean(res.fdp[mc_steady_idc_vec]),
            np.mean(tl_detected[idx, :]), np.mean(br_detected[idx, :])))
        print("")
elif evaluate_event == 'scenario_3' or 'bonus_example_null':
    for idx, res in enumerate(all_res_sel):
        print("--------- Nominal FDR: {} | FDR  ---------".format(
            alp_vec[show_alp_vec_idx]))
        print("{}: {:.2f}  ".format(met_names_res[idx], res.fdr))
        print("")  
# %% Show discovery heatmaps
# can be used to detect "hot spots" where discoveries often take place
# -> either for assessing match with ground truth or for finding a path!
if experiment_name == 'eusipco':
    if evaluate_event == 'scenario_1':
        start_av_time = datetime.datetime(2024, 3, 1, 14, 52, 0)
        end_av_time = datetime.datetime(2024, 3, 1, 15, 14, 0)
    elif evaluate_event == 'scenario_2':
        start_av_time = datetime.datetime(2024, 3, 13, 9, 33, 0)
        end_av_time = datetime.datetime(2024, 3, 13, 9, 38, 0)
    elif evaluate_event == 'scenario_3':
        start_av_time = event_start_end_times[0]
        end_av_time = event_start_end_times[1]
elif experiment_name == 'bonus':
    if evaluate_event == 'bonus_first_walk':
        start_av_time = datetime.datetime(2024, 4, 12, 13, 24, 0)
        end_av_time = datetime.datetime(2024, 4, 12, 13, 46, 0)
    elif evaluate_event == 'bonus_second_walk':
        start_av_time = datetime.datetime(2024, 4, 15, 20, 2, 50)
        end_av_time = datetime.datetime(2024, 4, 15, 20, 16, 0)
    elif evaluate_event == 'bonus_example_null':
        start_av_time = event_start_end_times[0]
        end_av_time = event_start_end_times[1]
# probably quite useful to illustrate a walking path

plot_av_det_prob(
    all_res_sel, dim, start_av_time, end_av_time, time_idx_vec,
    start_glob_time_at, tsEpochDuration, fd.sen_cds[0, :].astype(int),
    met_names_res, anchor_cds=anchor_loc, figsize=figsize)
