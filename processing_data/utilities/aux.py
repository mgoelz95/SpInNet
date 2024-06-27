# Auxiliary methods
# %% Setup: Imports
import numpy as np
import scipy.stats as stats
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.colors as colors
import matplotlib.patches as mpatches

from matplotlib.ticker import MaxNLocator

import datetime

import os
import sys
sys.path.append('..')

from utilities.tuda_colors import *

# from aux import *
from spatialmht.analysis import show_sensors_in_field

import requests
import time
import serial
import re
# %% setup: define my custom colormaps
# The color dictionairy for my linearly spaced color-map emphasizing small
# p-values. Setup such that yellow is exactly at 0.15
color_dic = {'red':   [(0.0,  0.0, 1.0),
                       (0.15, 1.0, 1.0),
                       (1.0,  0.0, 0.0)],

             'green': [(0.0,  0.0, 0.0),
                       (0.15, 1.0, 1.0),
                       (1.0,  1.0, 1.0)],

             'blue':  [(0.0,  0.0, 0.0),
                       (1.0,  0.0, 0.0)]}
my_cmap = colors.LinearSegmentedColormap('pval_map', color_dic)

color_dic_lfdrs = {'red':   [(0.0,  0.0, 1.0),
                            (0.3, 1.0, 1.0),
                            (1.0,  0.0, 0.0)],

                'green': [(0.0,  0.0, 0.0),
                       (0.3, 1.0, 1.0),
                       (1.0,  1.0, 1.0)],

             'blue':  [(0.0,  0.0, 0.0),
                       (1.0,  0.0, 0.0)]}
cm_lfdr = colors.LinearSegmentedColormap('lfdr_cmap', color_dic_lfdrs)

color_dic_prct = {'red':   [(0.0,  0.0, 1.0),
                            (1.0,  1.0, 1.0)],

                'green': [(0.0,  0.0, 1.0),
                            (1.0, 1.0, 0.0)],

                'blue':  [(0.0,  0.0, 1.0),
                           (1.0,  1.0, 0.0)]}
my_cmap2 = colors.LinearSegmentedColormap('prct', color_dic_prct)
# %% Setup and administration
def create_hist_legends_list(null_lst, walk_lst):
    """create legends list for histograms.

    Parameters
    ----------
    null_lst : list
        a list with null period start and end times.
    walk_lst : list
        a list with alternative periods start and end times where someone
        walked through the room. 

    Returns
    -------
    list
        of histogram legends
    """
    legends_lst = []
    for null in null_lst:
        legends_lst.append("Nobody there ({} - {})".format(
            null[0].strftime('%d.%m %H:%M'), null[1].strftime('%d.%m %H:%M')))
    for stroll in walk_lst:
        legends_lst.append("strolling around ({} - {})".format(
            stroll[0].strftime('%d.%m %H:%M'), stroll[1].strftime(
                '%d.%m %H:%M')))
    return legends_lst

def get_epoch(starting_time, objective_time, tsEpochDuration):
    """return which epoch we are in 

    Parameters
    ----------
    starting_time : datetime.datetime
        Start time where epoch idx = 0 was.
    objective_time : datetime.datetime
        The time for which the epoch is to be computed.
    tsEpochDuration : int
        The epoch duration.

    Returns
    -------
    int
        The epoch index.
    """
    time_delta = (
         int((objective_time - starting_time).total_seconds() * 1000)
         /tsEpochDuration)
    if time_delta < 0:
        print("ERROR! NEGATIVE TIME DELTA!")
        return None
    return int(time_delta)

def get_time(starting_time, epoch_idx, tsEpochDuration):
    """get the absolute time at a given epoch index.

    Parameters
    ----------
    starting_time : datetime.datetime
        The time at which the experiment started.
    epoch_idx : int
        The epoch index for which the absolute time is to be returned.
    tsEpochDuration : int
        The duration of one epoch in milliseconds.

    Returns
    -------
    datetime.datetime
        The absolute time.
    """
    return (starting_time
            + epoch_idx *datetime.timedelta(seconds=tsEpochDuration / 1000))

def is_notebook() -> bool:
    """Check if file is run in a jupyter notebook.

    Returns
    -------
    bool
        True if run in notebook, false otherwise.
    """
    try:
        shell = get_ipython().__class__.__name__
        if shell == 'ZMQInteractiveShell':
            return True   # Jupyter notebook or qtconsole
        elif shell == 'TerminalInteractiveShell':
            return False  # Terminal running IPython
        else:
            return False  # Other type (?)
    except NameError:
        return False      # Probably standard Python interpreter

def load_all_nodes(data_directory, time_idx, num_nodes=54, which_data="humid"):
    """Loads the data from all nodes and returns them as a DataFrame

    Parameters
    ----------
    data_directory : string
        The path to where the data is stored
    time_idx : numpy array
        vector of indexes for which data is to be loaded
    num_nodes : int, optional
        The number of nodes data is to be loaded for, by default 54
    which_data : str, optional
        Whether temperature of Humidity is to be loaded, by default "humid"

    Returns
    -------
    DataFrame
        The loaded data.
    """
    try:
        df = pd.read_csv(os.path.join(data_directory, 'Node1_data.csv'),
                           usecols=['epoch', which_data], index_col=0)
        df = df.loc[time_idx]
        df = df[df.index.duplicated(keep=False)==False]
        df = df.rename(columns={which_data: "Node1"})
    except (FileNotFoundError):
        print("No data for Node1 found!")
        d = {'epoch': time_idx, which_data: np.nan + np.zeros(time_idx.shape)}
        df = pd.DataFrame(data=d)
        df.set_index("epoch", inplace=True)
    except KeyError as e:
        # if not all epoch indexes have data available for node 1
        missing_keys = []
        msg = e.args[0]
        start_idx = 1
        end_idx = 1
        for s in np.arange(len(e.args[0])):
            end_idx = s
            if msg[s] == ']':
                missing_keys.append(int(msg[start_idx:end_idx]))
                break
            elif msg[s] == 's':
                missing_keys.append(int(msg[start_idx:end_idx]))
                start_idx = end_idx + 1
            elif msg[start_idx:s] == 'one of':
                # none of these epochs has data for the present node
                missing_keys = time_idx
                break
        missing_keys = np.array(missing_keys)
        missing_keys_idx = np.where(np.tile(
            time_idx[:, np.newaxis], [1, missing_keys.size]) == np.tile(
                missing_keys[np.newaxis, :], [time_idx.size, 1]))
        time_idx_available = np.delete(time_idx, missing_keys_idx)

        # now get the data from available epoch indexes
        df = df.loc[time_idx_available]
        df = df[df.index.duplicated(keep=False)==False]
        df = df.rename(columns={which_data: "Node1"})
    for node_idx in np.arange(2, num_nodes+1, 1):
        try:
            df_tmp = pd.read_csv(os.path.join(
                data_directory, 'Node{}_data.csv'.format(int(node_idx))),
                usecols=['epoch', which_data], index_col=0)
            df_tmp = df_tmp.loc[time_idx].rename(
                columns={which_data: "Node{}".format(int(node_idx))})
            df_tmp = df_tmp[df_tmp.index.duplicated(keep=False)==False]
            df = df.join(df_tmp, rsuffix="_{}".format(
                int(node_idx)), sort=True, how='outer')
        except (FileNotFoundError):
            print("No data for Node{} found!".format(node_idx))
            df['Node{}'.format(int(node_idx))] = np.nan
        except KeyError as e:
            # if not all epoch indexes have data available for node 1
            missing_keys = []
            msg = e.args[0]
            start_idx = 1
            end_idx = 1
            for s in np.arange(len(e.args[0])):
                end_idx = s
                if msg[s] == ']':
                    missing_keys.append(int(msg[start_idx:end_idx]))
                    break
                elif msg[s] == ',':
                    missing_keys.append(int(msg[start_idx:end_idx]))
                    start_idx = end_idx + 1
                elif msg[start_idx:s] == 'one of':
                    # none of these epochs has data for the present node
                    missing_keys = time_idx
                    break
            missing_keys = np.array(missing_keys)
            missing_keys_idx = np.where(np.tile(
                time_idx[:, np.newaxis], [1, missing_keys.size]) == np.tile(
                    missing_keys[np.newaxis, :], [time_idx.size, 1]))
            time_idx_available = np.delete(time_idx, missing_keys_idx)
                    # now get the data from available epoch indexes
            df_tmp = df_tmp.loc[time_idx_available].rename(
                columns={which_data: "Node{}".format(int(node_idx))})
            df_tmp = df_tmp[df_tmp.index.duplicated(keep=False)==False]
            df = df.join(df_tmp, rsuffix="_{}".format(
                int(node_idx)), sort=True, how='outer')

    # if tehre are duplicates, drop them and keep first.
    df = df.drop_duplicates(ignore_index=False)
    return df

def load_data_single_node(filepath, time_idx=None, fullsize=False,
                          idx_header='epoch'):
    """Load a data file under the given path and return its content. Default:
    return the entire dataframe. If time_idx_vec is not None, returns values
    for given time indexes.

    Parameters
    ----------
    filename : string
        The filename of the data file to be accessed.
    time_idx_vec : 1D numpy array, optional
        The measurement indeces to be selected from the file, by default None.
        If None, everything is returned.
    fullsiz : bool
        TODO: Explain. The default is false.
    idx_header : string
        The name of the index column, needed as raw data csv files and regular  
        data csv files use different wordign ('index' vs 'epoch'). The default
        is 'epoch'.
    
    Returns
    -------
    dataframe
        Dataframe containing the desired values from the file.
    """
    # first loads the data frame from the given file path and then uses the
    # specified index to return the desired values
    df = pd.read_csv(filepath, sep=',', header=0, index_col=0)
    # drop duplicates
    df = (df.reset_index()
        .drop_duplicates(subset=idx_header, keep='last')
        .set_index(idx_header).sort_index())
    if time_idx is None:
        return df
    else:
        available_epochs = np.zeros(time_idx.shape, dtype=bool)
        for idx in range(len(time_idx)):
            available_epochs[idx] = time_idx[idx] in df.index
            
        indexed_df = df.loc[time_idx[available_epochs]]

        duplicates = indexed_df[indexed_df.index.duplicated(keep=False)]
        if duplicates.shape[0] > 0:
            #print("There were duplicates in {}!!".format(filepath))
            #print(duplicates)
            uniques = indexed_df[
                indexed_df.index.duplicated(keep=False)==False]
            #time.sleep(10)
            indexed_df = uniques
        if fullsize:
            # returns full-size p-value vector of humidity
            fullsize_df = pd.DataFrame({idx_header: [], 'temp': [],
                                        'humid': []}, dtype=int)

            for idx in range(len(time_idx)):
                new_row = {idx_header: int(time_idx[idx]), 'temp': np.nan,
                           'humid': np.nan}
                fullsize_df = pd.concat([fullsize_df, pd.DataFrame([new_row])],
                                        ignore_index=True)
            fullsize_df.set_index(idx_header, inplace=True)

            fullsize_df.loc[time_idx[available_epochs]] = df.loc[
                time_idx[available_epochs]]
            print("Doing fullsize")
            indexed_df = fullsize_df
        return indexed_df

def start_end_to_index_list(start_end_lst, global_start_time, data,
                            tsEpochDuration):
    epoch_lst = []
    for start_end in start_end_lst:
        this_time_period = []
        for idx in np.arange(
            get_epoch(global_start_time, start_end[0], tsEpochDuration),
            get_epoch(global_start_time, start_end[1], tsEpochDuration), 1):
            if idx in data.index.values:
                this_time_period.append(idx)
        epoch_lst.append(np.array(this_time_period))
    return epoch_lst

def start_end_to_index_list_renewed(start_end_lst, global_start_time,
                                    tsEpochDuration):
    """Turns a list with start and end time of a period into a list with all 
    epoch indexes of this period.

    Parameters
    ----------
    start_end_lst : list
        Contains start and end time of the period
    global_start_time : datetime.datetime
        The global start time of this experiment
    tsEpochDuration : int
        The duration of an epoch.

    Returns
    -------
    list
        The list of epochs in this period.
    """
    epoch_lst = []
    for start_end in start_end_lst:
        epoch_lst.append(np.arange(
            get_epoch(global_start_time, start_end[0], tsEpochDuration),
            get_epoch(global_start_time, start_end[1], tsEpochDuration), 1))
    return epoch_lst
# %% Data processing

def get_pvals_from_edfs(data_directory, edf_lst, null_sizes, tsWindowLength,
                        which_nodes, eval_idx_lst, which_data='humid'):
    data = load_all_nodes(data_directory, eval_idx_lst, which_data=which_data)
    eval_data = dither_aad(data, tsWindowLength)
    pval = eval_data.copy(deep=True) + np.nan
    for node, edf, size in zip(which_nodes, edf_lst, null_sizes):
        pval[node] = (((1-edf.evaluate(eval_data[node]))*(size))+1)/((size+1))
        pval[node][np.isnan(eval_data[node])] = np.nan
    return pval

def get_pvals_from_edfs_sgl_node(filepath, edf, null_size, time_idx, win_len,
                                 which_data='humid', scatter=False,
                                 fullsize=False):
    """Computes p-values from given edf for a single node.

    Parameters
    ----------
    filepath : string
        Path to where the data is stored.
    edf : scipy edf
        The edf of the node
    null_size : int
        Size of the edf.
    time_idx : numpy array
        The index of epochs for which p-values are to be computed
    win_len : int
        The number of samples per test statistic
    which_data : str, optional
        "temp" or "humid", by default 'humid'
    scatter : bool, optional
        True if a scatter plot of p-values is to be provided, by default False
    fullsize : bool, optional
        If the returned vector should be of the same size as time_idx. If False
        resulting p-val vector could be smaller than time_idx, if data is
        missing for certain epochs, by default False.

    Returns
    -------
    numpy array
        The p-values
    """
    data = load_data_single_node(filepath, time_idx=time_idx,
                                 fullsize=fullsize)[which_data]
    eval_data = dither_aad(data, win_len)
    pval = np.zeros(time_idx.shape)
    pval =  (((1-edf.evaluate(eval_data))*(null_size)) + 1)/((null_size + 1))
    pval[np.isnan(eval_data)] = np.nan
    if scatter:
        plt.figure()
        plt.scatter(eval_data, pval)
    return pval

def get_unique_vals_and_counters(data, win_len):
    # removing nans
    data_no_nan = data[~np.isnan(data)]
    data_relevant = np.round(data_no_nan*win_len, decimals=2) / win_len
    unique, counts = np.unique(data_relevant, return_counts=True)
    return unique, counts, data_relevant

def learn_all_null_edfs(data_directory, null_idx_lst, win_len, which_nodes,
                        which_data='humid'):
    """Learn all null edfs for the given list of null indexes and nodes.

    Parameters
    ----------
    data_directory : string
        The path to where the data is stored.
    null_idx_lst : list
        List of null epoch indexes.
    win_len : int
        number of samples used for computing one test statistic
    which_nodes : list
        Names of the nodes we process
    which_data : str, optional
        "humid" or "temp", by default 'humid'

    Returns
    -------
    tuple
        list of scipy edf objects and ints with the sizes of these edfs.
    """
    all_null_idx = np.array(
        [idx for idx_vec in null_idx_lst for idx in idx_vec])
    edf_lst = []
    null_sizes = np.zeros(len(which_nodes))
    for (idx, node) in enumerate(which_nodes):
        data_for_this_node = load_data_single_node(
            os.path.join(data_directory, node + "_data.csv"),
            time_idx=all_null_idx)[which_data]
        #data_for_this_node = data[node].loc[all_null_idx].values
        data_for_this_node_cont = dither_aad(data_for_this_node,
                                                     win_len)
        edf_obj, size = learn_null_edf(data_for_this_node_cont)
        edf_lst.append(edf_obj.cdf)
        null_sizes[idx] = size
        print("Learned EDF of {}".format(node))
    return edf_lst, null_sizes

def learn_null_edf(data):
    null_data_no_nan = data[~np.isnan(data)]
    edf = stats.ecdf(null_data_no_nan)
    return edf, len(null_data_no_nan)

def make_sq_continuous(vals, win_len, which_dat="humid"):
    #dither data - disclaimer: not really sure if that is actual dithering. 
    # I am just adding uniformly distributed noise to the test statistics
    if which_dat == "humid":
        cont_dat = vals + (stats.uniform.rvs(
            loc=-(.02)**2* win_len/2, scale=(.02)**2*win_len, size=vals.shape))
    elif which_dat == 'temp':
        # TODO: Check if this does the job
        cont_dat = vals + (stats.uniform.rvs(loc=-(.015**2), scale=(0.03)**2,
                                             size=vals.shape))
    cont_dat[cont_dat<0] = cont_dat[cont_dat<0] * -1
    return cont_dat

def dither_aad(vals, win_len, which_dat="humid"):
    """dither data the mean - add uniformly distributed noise to the values.
    Loc and scale of noise chosen such that there is as little distortion as
    possible while having no "holes" in the histogram. Different loc and scale
    for temp and rH, as sensor precisions are different.

    Parameters
    ----------
    vals : numpy array
        The discrete values to be dithered.
    which_dat : str, optional
        "humid" or "temp", depending on what shall be dithered, by default
        "humid".

    Returns
    -------
    numpy array
        The continuous values.
    """
    if which_dat == "humid":
        cont_dat = vals + (stats.uniform.rvs(loc=-.01, scale=0.02,
                                             size=vals.shape)) / win_len
    elif which_dat == 'temp':
        cont_dat = vals + (stats.uniform.rvs(loc=-.015, scale=0.03,
                                             size=vals.shape)) / win_len
    # aad can never be negative.
    cont_dat[cont_dat<0] = cont_dat[cont_dat<0] * -1
    return cont_dat

# %% Visualization
def initialize_double_map(sensor_map, cmap_lst, vmin=0, vmax=1,
                          figsize=(8,8), cbar_lst=[True, False]):
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    im = []
    cbar = []
    for ax, cmap, show_cbar in zip(axes, cmap_lst, cbar_lst):
        this_im = ax.imshow(sensor_map, cmap=cmap, origin="lower", vmin=vmin,
                            vmax=vmax)
        im.append(this_im)
        if show_cbar:
            cbar.append(plt.colorbar(this_im, fraction=0.046, pad=0.04))
        ax.set_xlabel('$x$-coordinate')
        ax.set_ylabel('$y$-coordinate')
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.xaxis.get_major_locator().set_params(integer=True)
    fig.suptitle("sensor locations")
    return fig, axes, im, cbar

def initialize_map(sensor_map, cmap=my_cmap, vmin=0, vmax=1, figsize=(8,8),
                   cbar=True):
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    im = ax.imshow(sensor_map, cmap=cmap, origin="lower", vmin=vmin, vmax=vmax)
    if cbar:
        cbar = fig.colorbar(im, fraction=0.046, pad=0.04)

    ax.set_xlabel('$x$-coordinate')
    ax.set_ylabel('$y$-coordinate')
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.xaxis.get_major_locator().set_params(integer=True)
    fig.suptitle("sensor locations")
    return fig, ax, im, cbar

def plot_av_det_prob(
        det_res_lst, dim, start_av, end_av, time_idx_vec, global_start_time,
        tsEpochDuration, sen_cds, res_names, anchor_cds=np.zeros((0, 2)),
        figsize=(8,8), **kwargs):
    """Plot the average detection probability per grid point over the given
    time period.

    Parameters
    ----------
    det_res_lst : list
        The list of detection results to be visualized
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    start_av : datetime.datetime
        The starting time
    end_av : datetime.datetime
        The end time
    time_idx_vec : _type_
        _description_
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    res_names  : list
        List with strings of the result names.
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """

    start_to_end_av_idx_lst = start_end_to_index_list_renewed(
        [[start_av, end_av]], global_start_time, tsEpochDuration)
    start_av_mc_idx = np.where(
        time_idx_vec == start_to_end_av_idx_lst[0][0])[0][0]
    end_av_mc_idc = np.where(
        time_idx_vec == start_to_end_av_idx_lst[0][-1])[0][0]
    mc_av_idc_vec = np.arange(start_av_mc_idx, end_av_mc_idc, 1, dtype=int)
    v = np.linspace(-.1, 2.0, 15, endpoint=True)

    for res, nam in zip(det_res_lst, res_names):
        fig, ax = plt.subplots()
        if not anchor_cds.shape==(0,2):
            show_sensors_in_field(
                np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5,
                linewidth=.5, ax=ax, fill=True, edgecolor='white',
                facecolor="k")
            show_sensors_in_field(np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5,
                              color='black', linewidth=1.5, ax=ax)
        im = ax.imshow(np.mean(
            res.r_det[mc_av_idc_vec, :], axis=0).reshape(dim), cmap='hot_r',
            vmin=0, vmax=1, origin='lower')
        cbar = fig.colorbar(im, fraction=0.046, pad=0.04)
       #cbar.set_ticks(np.arange(0, 1.1, .1))
        #im.set_clim(0, .2)
        ax.set_title('Detection percentage {} - {}, {}'.format(
            start_av.strftime('%H:%M'), end_av.strftime('%H:%M'), nam))
        ax.set_xlabel('$x$-coordinate')
        ax.set_ylabel('$y$-coordinate')
        ax.yaxis.get_major_locator().set_params(integer=True)
        ax.xaxis.get_major_locator().set_params(integer=True)

def plot_data_map(fig, ax, data):
    im = ax.imshow(data, origin="lower")
    cbar = fig.colorbar(im)
    fig.canvas.draw_idle()
    return im, cbar

def plot_evolution_all_lfdrs(
        lfdr_lst, dim, epochs_to_show, global_start_time, tsEpochDuration,
        sen_cds, met_names, anchor_cds=np.zeros((0, 2)), click=False,
        time_between_updates=.5, sen_only=True, figsize=(8,8), **kwargs):
    """Plots lfdrs of different methods in parallel to enable an epoch-by-epoch
    comparison between methods.

    Parameters
    ----------
    lfdr_lst : list
        list of lfdrs for all methods
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    met_names : list
        The names of the different methods.
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    sen_only : bool, optional
        If only sensor lfdrs to be shown, by default True
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """
    if sen_only:
        fullsize_lfdrs = []
        for lfdrs in lfdr_lst:
            fullsize_this_lfdrs = np.zeros(
                (lfdrs.shape[0], dim[0], dim[1])) + np.nan
            fullsize_this_lfdrs[:, sen_cds[:, 1], sen_cds[:, 0]] = lfdrs
            fullsize_lfdrs.append(fullsize_this_lfdrs)
        lfdr_lst = fullsize_lfdrs
    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_cds[:, 1], sen_cds[:, 0]] = 1
    
    fig_lst = []
    ax_lst = []
    im_lst = []
    for lfdrs in lfdr_lst:
        fig, ax, im, _ = initialize_map(
            sensor_map, cmap=cm_lfdr, figsize=figsize)
        fig_lst.append(fig)
        ax_lst.append(ax)
        im_lst.append(im)
        if not anchor_cds.shape==(0,2):
            show_sensors_in_field(
                np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5,
                linewidth=.5, ax=ax, fill=True, edgecolor='white',
                facecolor="k")
        show_sensors_in_field(np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5,
                              color='black', linewidth=1, ax=ax)


    for fig in fig_lst:
        fig.canvas.draw_idle()
    plt.pause(1)

    for it, i in enumerate(epochs_to_show):
        new_im_lst = []
        for lfdrs, im, ax, fig, name in zip(
            lfdr_lst, im_lst, ax_lst, fig_lst, met_names):
            im.remove()
            dmap = np.zeros(dim) + np.nan
            dmap = lfdrs[it, :].reshape(dim)

            im = plot_pval_map(fig, ax, dmap, cmap=cm_lfdr)
            new_im_lst.append(im)

            fig.suptitle("{} - epoch: {} / Time: {}".format(
                name, i, get_time(global_start_time, i, tsEpochDuration)))

        get_next_frame(it)
        im_lst = new_im_lst

def plot_evolution_all_rej(
        det_res_lst, dim, epochs_to_show, global_start_time, tsEpochDuration,
        sen_cds, name_lst, anchor_cds=np.zeros((0, 2)), click=False,
        time_between_updates=.5, sen_only=True, figsize=(8,8), **kwargs):
    """Plots decisions of different methods in parallel to enable an
    epoch-by-epoch comparison between methods.

    Parameters
    ----------
    det_res_lst : list
        list of detectionResult s of all methods
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    name_lst : list
        The names of the different methods.
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    sen_only : bool, optional
        If only sensor lfdrs to be shown, by default True
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """
    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    legend_lst = []
    col_lst = []
    dat_lst = []

    cmap_det_lst = []
    for det_res in det_res_lst:
        if np.sum(np.isnan(det_res.r_tru)) == np.prod(det_res.r_det.shape):
            legend_lst.append(['non-discovery', 'discovery'])
            col_lst.append(['#FFFFFF', TUDa_6d])
            dat_lst.append([det_res.r_det==0, det_res.r_det==1])
        else:
            legend_lst.append(['correct non-discovery', 'correct discovery',
                              'false discovery', 'missed discovery'])
            col_lst.append(['#FFFFFF', TUDa_4b, TUDa_9b, '#555555'])
            dat_lst.append([det_res.u, det_res.s, det_res.v, det_res.t])        

    # Set up the colormap
    for this_col_lst in col_lst:
        cmap_det_lst.append([colors.to_rgb(x) for x in this_col_lst])

    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_cds[:, 1], sen_cds[:, 0]] = 1
    
    fig_lst = []
    ax_lst = []
    im_lst = []
    for this_cmap in cmap_det_lst:
        fig, ax, im, _ = initialize_map(
            sensor_map, cmap='binary', figsize=figsize, cbar=False)
        fig_lst.append(fig)
        ax_lst.append(ax)
        im_lst.append(im)

        fig.canvas.draw_idle()
        if not anchor_cds.shape==(0,2):
            show_sensors_in_field(
                np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5,
                linewidth=.5, ax=ax, fill=True, edgecolor='white',
                facecolor="k")
        show_sensors_in_field(np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5,
                              color='black', linewidth=1.5, ax=ax)

    plt.pause(1)

    for it, i in enumerate(epochs_to_show):
        new_im_lst = []
        for fig, im, dat, cmap_det, legend, ax, name in zip(
            fig_lst, im_lst, dat_lst, cmap_det_lst, legend_lst, ax_lst,
            name_lst):
            im.remove()

            if sen_only:    
                dmap = np.zeros(dim, dtype=int)
                for idx, this_dat in enumerate(dat):
                    dmap[sen_cds[this_dat[it]==1, 1],
                         sen_cds[this_dat[it]==1, 0]] = idx
            else:
                dmap = np.zeros(np.prod(dim), dtype=int)
                for idx, this_dat in enumerate(dat):
                    dmap[this_dat[it]==1] = idx
                dmap = dmap.reshape(dim)
    
            dat_to_show = np.array([[cmap_det[i] for i in j] for j in dmap])
            new_im_lst.append(ax.imshow(dat_to_show, origin="lower"))
            patches = [mpatches.Patch(color=cmap_det[i],label=legend[i])
                       for i, entry in enumerate(cmap_det)]
            ax.legend(handles=patches)

            fig.canvas.draw_idle()

            fig.suptitle("{} - epoch: {} / Time: {}".format(
                    name, i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)
        im_lst = new_im_lst

def plot_evolution_all_side_by_side(
        det_res_lst, lfdr_lst, dim, epochs_to_show, global_start_time,
        tsEpochDuration, sen_cds, name_lst, anchor_cds=np.zeros((0, 2)),
        click=False, time_between_updates=.5,
        sen_only=True, figsize=(8,8), **kwargs):
    """Plot the evolution of detection results and lfdrs side-by-side.

    Parameters
    ----------
    det_res_lst : list
        list of detectionResult s of all methods
    lfdr_lst : list
        list of lfdrs for all methods
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    name_lst : list
        The names of the different methods.
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    sen_only : bool, optional
        If only sensor lfdrs to be shown, by default True
    figsize : tuple, optional
        The size of the figures, by default (8,8).

    """

    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    if sen_only:
        fullsize_lfdrs = []
        for lfdrs in lfdr_lst:
            fullsize_this_lfdrs = np.zeros(
                (lfdrs.shape[0], dim[0], dim[1])) + np.nan
            fullsize_this_lfdrs[:, sen_cds[:, 1], sen_cds[:, 0]] = lfdrs
            fullsize_lfdrs.append(fullsize_this_lfdrs)
        lfdr_lst = fullsize_lfdrs

    legend_lst = []
    col_lst = []
    dat_lst = []


    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_cds[:, 1], sen_cds[:, 0]] = 1
    
    fig_lst = []
    ax_lst = []
    im_lst = []
    for this in lfdr_lst:
        fig, ax, im, _ = initialize_double_map(
            sensor_map, [my_cmap, 'binary'], figsize=figsize,
            cbar_lst=[True, False])
        fig_lst.append(fig)
        ax_lst.append(ax)
        im_lst.append(im)

        fig.canvas.draw_idle()

        for subax in ax:
            if not anchor_cds.shape == (0,2):
                show_sensors_in_field(
                    np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5,
                    linewidth=.5, ax=subax, fill=True, edgecolor='white',
                    facecolor="k")
            show_sensors_in_field(
                np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5, color='black',
                linewidth=1, ax=subax)

    plt.pause(1)

    for it, i in enumerate(epochs_to_show):
        new_im_lst = []
        legend_lst = []
        col_lst = []
        dat_lst = []
        for det_res in det_res_lst:
            if np.sum(np.isnan(det_res.r_tru[it])) == np.prod(dim):
                legend_lst.append(['non-discovery', 'discovery'])
                col_lst.append(['#FFFFFF', TUDa_6d])
                dat_lst.append([det_res.r_det[it]==0, det_res.r_det[it]==1])
            else:
                legend_lst.append(['correct non-discovery',
                                   'correct discovery', 'false discovery',
                                   'missed discovery'])
                col_lst.append(['#FFFFFF', TUDa_4b, TUDa_9b, '#555555'])
                dat_lst.append([
                    det_res.u[it], det_res.s[it], det_res.v[it],
                    det_res.t[it]])

        cmap_det_lst = []
        # Set up the colormap
        for this_col_lst in col_lst:
            cmap_det_lst.append([colors.to_rgb(x) for x in this_col_lst])
        for fig, im, lfdrs, dat, cmap_det, legend, ax, name in zip(
            fig_lst, im_lst, lfdr_lst, dat_lst, cmap_det_lst, legend_lst,
            ax_lst, name_lst):
            # Taking care of the lfdrs
            im[0].remove()
            dmap = np.zeros(dim) + np.nan
            dmap = lfdrs[it, :].reshape(dim)
            
            lfdr_im = plot_pval_map(fig, ax[0], dmap, cmap=cm_lfdr)

            # Taking care of the discoveries
            im[1].remove()
            dmap = np.zeros(dim) + np.nan
            dmap = lfdrs[it, :].reshape(dim)

            if sen_only:    
                dmap = np.zeros(dim, dtype=int)
                for idx, this_dat in enumerate(dat):
                    dmap[sen_cds[this_dat==1, 1],
                         sen_cds[this_dat==1, 0]] = idx
            else:
                dmap = np.zeros(np.prod(dim), dtype=int)
                for idx, this_dat in enumerate(dat):
                    dmap[this_dat==1] = idx
                dmap = dmap.reshape(dim)
    
            dat_to_show = np.array([[cmap_det[w] for w in j] for j in dmap])
            res_im = ax[1].imshow(dat_to_show, origin="lower")
            patches = [mpatches.Patch(color=cmap_det[w],label=legend[w])
                       for w, entry in enumerate(cmap_det)]
            ax[1].legend(handles=patches)

            new_im_lst.append([lfdr_im, res_im])
            fig.canvas.draw_idle()

            fig.suptitle("{} - epoch: {} / Time: {}".format(
                    name, i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)
        im_lst = new_im_lst

def plot_evolution_lfdrs(
        lfdrs, dim, epochs_to_show, global_start_time, tsEpochDuration,
        sen_cds, name, anchor_cds=np.zeros((0, 2)), click=False,
        time_between_updates=.5, sen_only=True, figsize=(8,8), **kwargs):
    """Plot the evolution of lfdrs over epochs.

    Parameters
    ----------
    lfdrs : numpy array
        The lfdrs to be visualized.
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    name : string
        The method name
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    sen_only : bool, optional
        If only sensor lfdrs to be shown, by default True
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """

    if sen_only:
        fullsize_lfdrs = np.zeros((lfdrs.shape[0], dim[0], dim[1])) + np.nan
        fullsize_lfdrs[:, sen_cds[:, 1], sen_cds[:, 0]] = lfdrs
        lfdrs = fullsize_lfdrs
    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_cds[:, 1], sen_cds[:, 0]] = 1
    
    fig, ax, im, _ = initialize_map(sensor_map, cmap=cm_lfdr, figsize=figsize)
    fig.canvas.draw_idle()

    if not anchor_cds.shape == (0, 2):
        show_sensors_in_field(
            np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5, linewidth=.5,
            ax=ax, fill=True, edgecolor='white', facecolor="k")

    show_sensors_in_field(np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5,
                          color='black', linewidth=1, ax=ax)

    plt.pause(1)

    fig_hist, ax_hist = plt.subplots()
    counts, bins, bars = ax_hist.hist(
        stats.uniform.rvs(size=1000), density=True, bins=30)

    for it, i in enumerate(epochs_to_show):
        _ = [b.remove() for b in bars]
        im.remove()

        counts, bins, bars = ax_hist.hist(
            lfdrs[it, :].flatten(), density=True,
            bins=np.array([0, .02, .04, .06, .08, .1, .125, .15, .175, .2, .25,
                           .3, .35, .5, .6, .7, .8, 1]),       
            color=TUDa_1b)
        fig_hist.canvas.draw_idle()

        dmap = np.zeros(dim) + np.nan
        dmap = lfdrs[it, :].reshape(dim)

        im = plot_pval_map(fig, ax, dmap, cmap=cm_lfdr)

        fig.suptitle("{} - epoch: {} / Time: {}".format(
                name, i, get_time(global_start_time, i, tsEpochDuration)))
        fig_hist.suptitle("{} - epoch: {} / Time: {}".format(name,
            i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)

def plot_evolution_pvals(data_directory, start_plot_at, end_plot_at,
                         global_start_time, tsEpochDuration, tsWindowLength,
                         sen_loc_arr, dim, edf_lst, null_sizes, which_nodes,
                         click=False, which_data="humid", figsize=(8,8),
                         time_between_updates=.5, **kwargs):
    """Plot the evolution of p-values over time (room map and histogram).

    Parameters
    ----------
    data_directory : string
        Path to the data.
    start_plot_at : datetime.datetime
        The absolute time at which we start.
    end_plot_at : datetime.datetime
        The absolute time at which we end.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_loc_arr : numpy array
        The sensor location coordinates.
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    edf_lst : list
        List of scipy EDFs, one per node.
    null_sizes : numpy array
        The number of samples per EDF.
    which_nodes : list
        The nodes for which things are supposed to be plotted. 
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    which_data : str, optional
        "humid" or "temp", by default "humid"
    figsize : tuple, optional
        _description_, by default (8,8)
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    """
    start_epoch = get_epoch(global_start_time, start_plot_at, tsEpochDuration)
    end_epoch = get_epoch(global_start_time, end_plot_at, tsEpochDuration)
    try:
        epochs_to_show = np.arange(start_epoch, end_epoch, 1)
    except TypeError:
        # in case start_epoch is smaller than 0
        epochs_to_show = np.arange(0, end_epoch, 1)

    pval = get_pvals_from_edfs(
        data_directory, edf_lst, null_sizes, tsWindowLength, which_nodes,
        epochs_to_show, which_data=which_data)

    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_loc_arr.T[1], sen_loc_arr.T[0]] = 1
    
    fig, ax, im, cbar = initialize_map(sensor_map, figsize=figsize)
    fig.canvas.draw_idle()
    plt.pause(1)

    fig_hist, ax_hist = plt.subplots()
    counts, bins, bars = ax_hist.hist(stats.uniform.rvs(size=1000),
                                      density=True, bins=30)
    ax_hist.set_ylabel('PDF')
    ax_hist.set_xlabel(r'$p$')

    for it, i in enumerate(epochs_to_show):
        try:
            _ = [b.remove() for b in bars]
        except ValueError:
            print("")
        im.remove()

        try:
            new_counts, new_bins, new_bars = ax_hist.hist(
                pval.loc[i].values, density=True,
                bins=np.array([0, .02, .04, .06, .08, .1, .125, .15, .175, .2,
                                .25, .3, .35, .5, .6, .7, .8, 1]),       
                color=TUDa_1b)
            counts, bins, bars = new_counts, new_bins, new_bars
        except KeyError:
            print("")
        fig_hist.canvas.draw_idle()

        dmap = np.zeros(dim) + np.nan
        try:
            dmap[sen_loc_arr.T[1], sen_loc_arr.T[0]] = pval.loc[i].values
        except KeyError:
            print('No Node has data for epoch {}'.format(i))

        im = plot_pval_map(fig, ax, dmap)

        fig.suptitle("Epoch: {} / Time: {}".format(
            i, get_time(global_start_time, i, tsEpochDuration)))
        fig_hist.suptitle("Epoch: {} / Time: {}".format(
            i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)

def plot_evolution_pvals_fd(
        fd, epochs_to_show, global_start_time, tsEpochDuration, sen_loc_arr,
        click=False, which_data="humid", time_between_updates=.5,
        figsize=(8,8), **kwargs):
    """Plot the evolution of p-values over time (room map and histogram) when
    a SpatialFiekd object is given.

    Parameters
    ----------
    fd : CustomSpatialField
        The spatial field to be dealt with.
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_loc_arr : numpy array
        The sensor location coordinates.
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    which_data : str, optional
        "humid" or "temp", by default "humid"
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """
    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    sensor_map = np.zeros(fd.dim, dtype=bool) + np.nan
    sensor_map[sen_loc_arr.T[1], sen_loc_arr.T[0]] = 1
    
    fig, ax, im, _ = initialize_map(sensor_map, figsize=figsize)
    fig.canvas.draw_idle()
    plt.pause(1)

    fig_hist, ax_hist = plt.subplots()
    counts, bins, bars = ax_hist.hist(stats.uniform.rvs(size=1000),
                                      density=True, bins=30)

    for it, i in enumerate(epochs_to_show):
        _ = [b.remove() for b in bars]
        im.remove()

        counts, bins, bars = ax_hist.hist(
            fd.p[it, :], density=True,
            bins=np.array([0, .02, .04, .06, .08, .1, .125, .15, .175, .2, .25,
                           .3, .35, .5, .6, .7, .8, 1]),       
            color=TUDa_1b)
        fig_hist.canvas.draw_idle()

        dmap = np.zeros(fd.dim) + np.nan
        dmap = fd.p[it, :].reshape(fd.dim)

        im = plot_pval_map(fig, ax, dmap)

        fig.suptitle("Epoch: {} / Time: {}".format(
            i, get_time(global_start_time, i, tsEpochDuration)))
        fig_hist.suptitle("Epoch: {} / Time: {}".format(
            i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)

def plot_evolution_raw_data(
        data_directory, start_plot_at, end_plot_at, global_start_time,
        tsEpochDuration, sen_loc_arr, evaluate_event, click=False,
        which_data="humid", time_between_updates=.5, dim=(20, 20), **kwargs):
    """Plot the evolution of AAD over time. 

    Parameters
    ----------
    data_directory : string
        Path to the data.
    start_plot_at : datetime.datetime
        The absolute time at which we start.
    end_plot_at : datetime.datetime
        The absolute time at which we end.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_loc_arr : numpy array
        The sensor locations.
    evaluate_event : string
        The event name
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    which_data : str, optional
        "humid" or "temp", by default "humid"
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    """
    start_epoch = get_epoch(global_start_time, start_plot_at, tsEpochDuration)
    end_epoch = get_epoch(global_start_time, end_plot_at, tsEpochDuration)
    try:
        epochs_to_show = np.arange(start_epoch, end_epoch, 1)
    except TypeError:
        # in case start_epoch is smaller than 0
        epochs_to_show = np.arange(0, end_epoch, 1)

    data = load_all_nodes(
        data_directory, epochs_to_show, which_data=which_data)

    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    sensor_map = np.zeros(dim, dtype=bool)
    sensor_map[sen_loc_arr.T[1], sen_loc_arr.T[0]] = 1
    
    fig, ax, im, cbar = initialize_map(sensor_map)
    fig.canvas.draw_idle()
    plt.pause(1)

    for it, i in enumerate(epochs_to_show):
        cbar.remove()
        im.remove()

        dmap = np.zeros(dim) + np.nan
        try:
            dmap[sen_loc_arr.T[1], sen_loc_arr.T[0]] = data.loc[i].values
        except KeyError:
            print('No Node has data for epoch {}'.format(i))
        # dont visualize sensors on the windowsill as those have higher
        # variations and without normalization, the colorbar will most of the
        # time not be sensitive enough to really see higher than usual values
        #  in other nodes anymore
        dmap[sen_loc_arr[45][1], sen_loc_arr[45][0]] = np.nan 
        dmap[sen_loc_arr[38][1], sen_loc_arr[38][0]] = np.nan 
        dmap[sen_loc_arr[44][1], sen_loc_arr[44][0]] = np.nan 
        dmap[sen_loc_arr[43][1], sen_loc_arr[43][0]] = np.nan 
        im, cbar = plot_data_map(fig, ax, dmap)

        fig.suptitle("Epoch: {} / Time: {}".format(
            i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)

def plot_evolution_rej(
        det_res, dim, epochs_to_show, global_start_time, tsEpochDuration,
        sen_cds, name, anchor_cds=np.zeros((0, 2)), click=False,
        time_between_updates=.5, sen_only=True, figsize=(8,8), **kwargs):
    """Plots the evolution of detection results for given epochs.

    Parameters
    ----------
    det_res : DetectionResult
        The detection result to be visualized
    dim : tuple, optional
        The dimension of the grid of the room, for our data the default
        (20, 20).
    epochs_to_show : numpy array
        The epoch indexes to be plotted.
    global_start_time : datetime.datetime
        The absolute time when this experiment started
    tsEpochDuration : int
        The epoch duration.
    sen_cds : numpy array
        The sensor location coordinates.
    name : string
        The name of the method
    anchor_cds : numpy array, optional
        The coordinates of the anchors (where H0 is known to be true), by
        default np.zeros((0, 2))
    click : bool, optional
        If advancing to next epoch by clicking a key is desired, by default
        False.
    time_between_updates : float, optional
        When click is false, this time dictates how long it takes to the next
        transission, by default .5.
    sen_only : bool, optional
        If only sensor lfdrs to be shown, by default True
    figsize : tuple, optional
        The size of the figures, by default (8,8).
    """

    if not click:
        next_frame_time = 1/(np.arange(epochs_to_show.size) + 1)
        next_frame_time = np.ones(epochs_to_show.size) * time_between_updates
        # is numpy array
        def get_next_frame(i):
            plt.pause(next_frame_time[i])
    else:
        print("Press any key for advancing to next epochs!")
        def get_next_frame(i):
            plt.waitforbuttonpress()

    if np.sum(np.isnan(det_res.r_tru)) == np.prod(det_res.r_det.shape):
        legend_lst = ['non-discovery', 'discovery']
        col_lst = ['#FFFFFF', TUDa_6d]
        dat = [det_res.r_det==0, det_res.r_det==1]
    else:
        legend_lst = ['correct non-discovery', 'correct discovery',
                      'false discovery', 'missed discovery']
        col_lst = ['#FFFFFF', TUDa_4b, TUDa_9b, '#555555']
        dat = [det_res.u, det_res.s, det_res.v, det_res.t]

    # Set up the colormap
    cmap_det = [colors.to_rgb(x) for x in col_lst]

    sensor_map = np.zeros(dim, dtype=bool) + np.nan
    sensor_map[sen_cds[:, 1], sen_cds[:, 0]] = 1
    
    fig, ax = plt.subplots(1, 1, figsize=figsize)
    im = ax.imshow(sensor_map, cmap='binary', origin="lower", vmin=0, vmax=1)
    ax.set_xlabel('x coordinate')
    ax.set_ylabel('y coordinate')
    ax.yaxis.get_major_locator().set_params(integer=True)
    ax.xaxis.get_major_locator().set_params(integer=True)
    fig.suptitle("sensor locations")

    fig.canvas.draw_idle()

    if not anchor_cds.shape == (0, 2):
        show_sensors_in_field(
            np.array([anchor_cds[:, 1], anchor_cds[:, 0]]) -.5, linewidth=.5,
            ax=ax, fill=True, edgecolor='white', facecolor="k")

    show_sensors_in_field(np.array([sen_cds[:, 1], sen_cds[:, 0]]) -.5,
                          color='black', linewidth=1, ax=ax)

    plt.pause(1)

    for it, i in enumerate(epochs_to_show):
        im.remove()

        if sen_only:    
            dmap = np.zeros(dim, dtype=int)
            for idx, this_dat in enumerate(dat):
                dmap[sen_cds[this_dat[it]==1, 1],
                     sen_cds[this_dat[it]==1, 0]] = idx
        else:
            dmap = np.zeros(np.prod(dim), dtype=int)
            for idx, this_dat in enumerate(dat):
                dmap[this_dat[it]==1] = idx
            dmap = dmap.reshape(dim)
    
        dat_to_show = np.array([[cmap_det[i] for i in j] for j in dmap])
        im = ax.imshow(dat_to_show, origin="lower")
        patches = [mpatches.Patch(color=cmap_det[i],label=legend_lst[i])
                   for i, entry in enumerate(cmap_det)]
        ax.legend(handles=patches)

        # cbar = fig.colorbar(im)
        fig.canvas.draw_idle()

        fig.suptitle("{} - epoch: {} / Time: {}".format(
                name, i, get_time(global_start_time, i, tsEpochDuration)))
        get_next_frame(it)

def plot_pval_map(fig, ax, data, cmap=my_cmap, vmin=0, vmax=1):
    im = ax.imshow(data, origin="lower", vmin=vmin, vmax=vmax, cmap=my_cmap)
    # cbar = fig.colorbar(im)
    fig.canvas.draw_idle()
    return im#, cbar

def plot_sensor_hist(which_nodes, data_directory, legends, time_idx_lst,
                     humid=True, temp=False, continuous=False, win_len=10,
                     **kwargs):
    """Plot one histogram per sensor.

    Parameters
    ----------
    which_nodes : list
        List of nodes to work with 
    data_directory : string
        Where the data is stored
    legends : list
        List of legend labels
    time_idx_lst : list
        List of epoch indexes for which the data is to be shown
    humid : bool, optional
        If true, humidity is shown, by default True.
    temp : bool, optional
        If true, temperature is shown, by default False
    continuous : bool, optional
        If true, data is dithered before plotting, by default False
    win_len : int, optional
        The number of measurements used for calculating a test statisc, by
        default 10.

    Returns
    -------
    tuple
        figure and axes with the histogram.
    """
    for node in which_nodes:
        if humid and temp:
            fig, axes = plt.subplots(1, 2)
        else:
            fig, axes = plt.subplots(1, 1)
        for time_idx in time_idx_lst:
            if continuous:
                axes = read_in_data_and_plot_hist_cont(
                    node, data_directory, legends, win_len, time_idx, axes,
                    **kwargs)

            else:
                axes = read_in_data_and_plot_hist(
                    node, data_directory, legends, time_idx, axes,
                    **kwargs)
        fig.suptitle(node)
    return fig, axes

def read_in_data_and_plot_hist(node, data_directory, legends,
                               time_idx=None, axes=None, humid=True,
                               temp=False, **kwargs):
    if axes is None:
        if humid and temp:
            fig, axes = plt.subplots(1, 2)
        else:
            fig, axes = plt.subplots(1, 2)
    if humid and temp:
        df = load_data_single_node(
            os.path.join(data_directory, node + '_data.csv'), time_idx)
        df.hist(grid=False, column='humid', ax=axes[0], density=True,
                alpha=.75, **kwargs)
        df.hist(grid=False, column='temp', ax =axes[1], density=True,
                alpha=0.75, **kwargs)
        axes[0].legend(legends)
        axes[1].legend(legends)
    elif humid:
        df = load_data_single_node(os.path.join(
            data_directory, node + '_data.csv'), time_idx)
        df.hist(grid=False, column='humid', ax=axes, density=True, alpha=.75,
                **kwargs)
        axes.legend(legends)
    elif temp:
        df = load_data_single_node(os.path.join(
            data_directory, node + '_data.csv'), time_idx)
        df.hist(grid=False, column='temp', ax =axes, density=True,
                alpha=0.75, **kwargs)
        axes.legend(legends)
    return axes

def read_in_data_and_plot_hist_cont(node, data_directory, legends, win_len,
                                    time_idx=None, axes=None, humid=True,
                                    temp=False, **kwargs):
    if axes is None:
        if humid and temp:
            fig, axes = plt.subplots(1, 2)
        else:
            fig, axes = plt.subplots(1, 2)
    if humid and temp:
        df = load_data_single_node(
            os.path.join(data_directory, node + '_data.csv'), time_idx)
        df["humid"] = dither_aad(df["humid"], win_len, which_dat="humid")
        df.hist(grid=False, column='humid', ax=axes[0], density=True,
                alpha=.75, **kwargs)
        df["temp"] = dither_aad(df["temp"], win_len, which_dat="temp")
        df.hist(grid=False, column='temp', ax =axes[1], density=True,
                alpha=0.75, **kwargs)
        axes[0].legend(legends)
        axes[1].legend(legends)
    elif humid:
        df = load_data_single_node(os.path.join(
            data_directory, node + '_data.csv'), time_idx)
        df["humid"] = dither_aad(df["humid"], win_len, which_dat="humid")
        df.hist(grid=False, column='humid', ax=axes, density=True, alpha=.75,
                **kwargs)
        axes.legend(legends)
    elif temp:
        df = load_data_single_node(os.path.join(
            data_directory, node + '_data.csv'), time_idx)
        df["temp"] = dither_aad(df["temp"], win_len, which_dat="temp")
        df.hist(grid=False, column='temp', ax =axes, density=True, alpha=0.75,
                **kwargs)
        axes.legend(legends)
    return axes

# %% Working with the physical network setup and the experiments
def get_active_node_nam_lst(active_node_idc):
    """Returns a list of strings with the node names currently active.

    Parameters
    ----------
    active_node_idc : 1d numpy array
        Vector of indexes of active sensors.

    Returns
    -------
    list
        List of strings with active node names.
    """
    active_node_nam = []
    for n in active_node_idc:
        active_node_nam.append("Node" + str(n + 1))
    return active_node_nam

def get_sen_loc_arrary(dim, sen_loc):
    """Returns the given list of sensor locations as a numpy array.

    Parameters
    ----------
    dim : tuple
        Number of grid points in (x,y) direction
    sen_loc : list
        List of integer tuples with sensor locations in (x,y) format

    Returns
    -------
    numpy array
        The len(sen_loc) x 2 numpy array with one sensor location per row.
    """
    sen_loc_arr = np.zeros((len(sen_loc), 2), dtype=int)
    for sen_idx in range(len(sen_loc)):
        sen_loc_arr[sen_idx, :] = sen_loc[sen_idx]
    return sen_loc_arr

# %% Processing stored data



# %% Running the fusion center
def calculate_current_epoch_index(time_now, time_at_start, epoch_duration):
    """Calculates the current epoch index from current given time, start of
    global time and duration of an epoch.

    Parameters
    ----------
    time_now : datetime.datetime
        The current time.
    time_at_start : datetime.datetime
        The start of the global time.
    epoch_duration : int
        The duration of one epoch in milliseconds.

    Returns
    -------
    int
        The current epoch index.
    """
    if datetime.datetime.now() > time_at_start:
        epoch_idx = int(int((time_now - time_at_start).total_seconds() * 1000)
                        / epoch_duration)
    else:
        epoch_idx = -1
    return epoch_idx

def create_csv_datafile(filename):
    """This function creates an empty csv data file to store the test
    statistics from a node received by the fusion center and stores it under
    the given absolute filename.

    Parameters
    ----------
    filename : String
        The desired filename
    """
    df = pd.DataFrame({'epoch': [], 'temp': [], 'humid': []})
    df.to_csv(filename, index=False)

def restart_serial(spn):
    """Returns if given serial port name is accessible. 

    Parameters
    ----------
    spn : String
        The serial port name in question.

    Returns
    -------
    serial.Serial or None
        If the serial port name is accessible, return new serial.Serial object
        representing the FC's Arduino nano. Else returns None.
    """
    try:
        fc = serial.Serial(spn, 9600, timeout=1)
        return fc
    except OSError:
        return None

def pass_time_to_nano(fc, start_glob_time_at, tsEpochDuration, nano_pn_lst,
                      wait_for_serial_seconds):
    """Passes the current global time to the arduino nano.

    Parameters
    ----------
    fc : serial.Serial
        The object representing the fc receiver microcontroller (arduino nano)
    start_glob_time_at : datetime.datetime
        The start of the global time.
    tsEpochDuration : int
        The duration of one epoch in milliseconds.
    nano_pn_lst : list of String
        The list of all potential port names of the Arduino Nano.
    wait_for_serial_seconds : int
        the number of seconds after which we reboot if finding a serial was not
        successful.
    Returns
    -------
    serial.Serial
        Serial object representing the port to which the Nano is attached. Must
        be returned here, as object might change while in this function.
    """

    # Initialize, needed for making sure we are at beginnig of epoch
    prevEpochIdx = calculate_current_epoch_index(
        datetime.datetime.now(), start_glob_time_at, tsEpochDuration)
    
    globTimePattern = r'^Enter globTimeInput'

    time_passed_to_nano = False

    start_passing_at_time = datetime.datetime.now()
    while not time_passed_to_nano:
        currentEpochIdx = calculate_current_epoch_index(
            datetime.datetime.now(), start_glob_time_at,
            tsEpochDuration)
        if currentEpochIdx >= 0:
            try:
                # now wait for the start of the next epoch to get perfect sync
                if currentEpochIdx > prevEpochIdx:
                    print(
                        "Seconds passed since start of global time: {}".format(
                        int((datetime.datetime.now()
                             - start_glob_time_at).total_seconds())))
                    while True:
                        if (
                            (datetime.datetime.now() -
                             start_passing_at_time).seconds
                             > wait_for_serial_seconds):
                            return None
                        if fc.in_waiting > 0:
                            line = fc.readline().decode().strip()
                            print(line)
                            if re.match(globTimePattern, line):
                                fc.write("{}".format(int((
                                    datetime.datetime.now()
                                    -start_glob_time_at).total_seconds()
                                    * 1000)).encode())
                                print(fc.readline().decode().strip())
                                break
                    time_passed_to_nano = True
            except OSError:
                # when there is nothing found on the serial port
                print("Connection to serial was lost. Waiting for serial...")
                serial_found = False
                while not serial_found:
                    for cand_pn in nano_pn_lst:
                        fc = restart_serial(cand_pn)
                        if fc is not None:
                            print("Serial found!")
                            serial_found = True
                            break
                time_passed_to_nano = False
                prevEpochIdx = calculate_current_epoch_index(
                    datetime.datetime.now(), start_glob_time_at,
                    tsEpochDuration)
        else:
            print("Global time starts only at {}".format(start_glob_time_at))
            prevEpochIdx = currentEpochIdx
    return fc

def reboot(rebooter):
    """Reboot the nano microcontroller by triggering the reset pin via the
    rebooter Uno.

    Parameters
    ----------
    rebooter : serial.Serial
        The object representing the rebooter microcontroller (arduino uno)
    """
    time.sleep(2)
    rebooter.write("1".encode())
    time.sleep(5)# this is crucial! Need to wait a bit for the pin to fire.

def send_telegram_message(message):
    """Sends the given message to subscribers of the telegram bot.

    Parameters
    ----------
    message : String
        The message to be send via the telegram bot
    """
    bot_token = "INSERTYOUROWNBOTTOKEN"  if you want to have a telegram bot, otherwise comment out
    chat_id = "INSERTYOUR CHATID"
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message}
    response = requests.post(url, json=payload)
    #if response.status_code == 200:
        #print("Telegram-Nachricht erfolgreich gesendet.")
    #else:
    #    print("Fehler beim Senden der Telegram-Nachricht.")

def write_data_buffer_to_csv(data_buffer, this_node, data_directory,
                             backup_directory, backup_key):
    """This function writes the current data buffer of the fusion center to a
    csv file.

    Parameters
    ----------
    data_buffer : numpy array
        array of size M x 3, where M is the number of epochs the FC currently
        has data buffered for. First, second and third column are epoch index,
        temperature and humidity test statistics, respectively.
    this_node : int
        the number of the node the data was received from.
    data_directory : String
        The absolute path were the file should be stored.
    backup_directory : String
        The absolute path were the backup file should be stored.
    backup_key : String
        Previously generated string that makes the backup file unique.
    """
    # create filename
    filename = 'Node' + str(this_node) + '_data'
    abs_filename = os.path.join(data_directory, filename + '.csv')
    abs_filename_backup = os.path.join(
        backup_directory, filename + '_' + backup_key + '.csv')

    # check if file exists, otherwise create new
    if not os.path.exists(data_directory):
        os.makedirs(data_directory)
    if not os.path.exists(backup_directory):
        os.makedirs(backup_directory)

    if not os.path.exists(abs_filename):
        create_csv_datafile(abs_filename)
    if not os.path.exists(abs_filename_backup):
        create_csv_datafile(abs_filename_backup)

    # first load existing files
    df = pd.read_csv(abs_filename)
    df_backup = pd.read_csv(abs_filename_backup)

    # now append data in buffer to data frame created from existing file
    for i in np.arange(data_buffer.shape[0]):
        if (data_buffer[i, 0] != 0):
            new_row = {'epoch': int(data_buffer[i, 0]),
                       'temp': data_buffer[i, 1], 'humid': data_buffer[i, 2]}
            df =  pd.concat([df, pd.DataFrame([new_row])], ignore_index = True)
            df_backup =  pd.concat([df_backup, pd.DataFrame([new_row])],
                                   ignore_index = True)

    # save dataframe of old and new data into file
    df.to_csv(abs_filename, index=False, mode='w')
    df_backup.to_csv(abs_filename_backup, index=False, mode='w')

