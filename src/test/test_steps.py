"""
Bing Zhai's step count implementation (https://github.com/bzhai/AFAR) 
of the Verisense Step Count algorithm (https://github.com/ShimmerEngineering/Verisense-Toolbox/tree/master/Verisense_step_algorithm)
modifications by Dan Jackson.
"""

# --- HACK: Allow the test to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

import numpy as np
import pandas as pd
import math


## TODO: Move steps to own code in 'process'
## TODO: Automatically resample to 15 Hz if required
## TODO: Analysis should preserve given timestamps

def find_peak(acc, peak_win_len=3):
    """
    :param acc: accelerometer raw data
    :param peak_win_len: window len to detect peak
    :return: peak_info: a matrix with shape: (len(acc)/peak_win_len, 5)
            # peak_info[,0] - peak location
            # peak_info[,1] - acc magnitude
            # peak_info[,2] - periodicity (samples)
            # peak_info[,3] - similarity
            # peak_info[,4] - continuity
    """
    half_k = np.round(peak_win_len / 2).astype(int)
    segments = np.floor(acc.shape[0] / peak_win_len).astype(int)
    peak_info = np.empty((segments, 5))
    peak_info[:] = np.inf
    for i in np.arange(segments):
        start_idx = i * peak_win_len
        end_idx = start_idx + peak_win_len - 1
        tmp_loc_a = np.argmax(acc[start_idx:end_idx+1])
        tmp_loc_b = i * peak_win_len + tmp_loc_a
        start_idx_ctr = tmp_loc_b - half_k
        if start_idx_ctr < 0:
            start_idx_ctr = 0
        end_idx_ctr = tmp_loc_b + half_k
        if end_idx_ctr > len(acc):
            end_idx_ctr = len(acc)
        check_loc = np.argmax(acc[start_idx_ctr:end_idx_ctr+1])
        if check_loc == half_k:
            peak_info[i, 0] = tmp_loc_b
            peak_info[i, 1] = np.max(acc[start_idx:end_idx+1])
    peak_info = peak_info[~np.in1d(peak_info[:, 0], np.inf)]
    return peak_info


def filter_magnitude(peak_info, mag_thres=1.2):
    peak_info = peak_info[peak_info[:, 1] > mag_thres]
    return peak_info


def calc_periodicity(peak_info, period_min=5, period_max=15):
    """
    calculate the period
    :param peak_info:
    :param period_min:
    :param period_max:
    :return:
    """
    num_peaks = peak_info.shape[0]
    # calculate periodicity
    peak_info[:num_peaks-1, 2] = np.diff(peak_info[:, 0])
    peak_info = peak_info[peak_info[:, 2] > period_min]
    peak_info = peak_info[peak_info[:, 2] < period_max]
    return peak_info


def calc_similarity(peak_info, sim_thres=-0.5):
    """
    # calculate similarity for all peaks
    :param peak_info: the step peak table, the similarity will be calculated based on column 2 and store the results in
    column 3. We calculate the difference between every two peaks and consider it as the similarity.
    :param sim_thres: the threshold used to cut off the difference(a.k.a similarity)
    :return: a 5D matrix contains filtered similarity data
    """

    num_peaks = len(peak_info[:, 1])
    peak_info[:(num_peaks-2), 3] = -np.abs(peak_info[:, 1][2:] - peak_info[:, 1][:-2])
    peak_info = peak_info[peak_info[:, 3] > sim_thres]
    peak_info = peak_info[~np.in1d(peak_info[:, 3], np.inf)]
    # num_peaks = len(peak_info[:,1])
    return peak_info


def filter_by_continue_threshold_variance_threshold(peak_info, acc, cont_win_size=3, cont_thres=4, var_thres=0.001):
    """
    Calculate the continuity by a given window length, then calculate the variance and filter the data by
    a given threshold
    :param peak_info: a 5D matrix
    :param cont_win_size: continue window len
    :param cont_thres: continue threshold
    :param var_thres: variance threshold
    :param fs: frequency of accelerometer data
    :return: all_steps: step count list
    """
    end_for = len(peak_info[:,2])-1
    for i in np.arange(cont_thres-1, end_for):
        v_count = 0
        for x in np.arange(1, cont_thres+1):
            if np.var(acc[int(peak_info[i-x+1, 0]):int(peak_info[i-x+2, 0]+1)], ddof=1) > var_thres:
                v_count = v_count + 1
        if v_count >= cont_win_size:
            peak_info[i, 4] = 1
        else:
            peak_info[i, 4] = 0
    peak_info = peak_info[peak_info[:, 4] == 1, 0]
    return peak_info


def counts_peaks(peak_info, acc, fs=15):
    """
    count the peaks from
    :param peak_info:
    :param fs:
    :return:
    """
    peak_info_count = np.ceil(peak_info/fs).astype(int).tolist()
    peak_info_count_dict = dict((x, peak_info_count.count(x)) for x in set(peak_info_count))
    all_steps = pd.Series(np.arange(np.floor(acc.shape[0]/fs).astype(int)))
    all_steps = all_steps.map(peak_info_count_dict).fillna(0)
    return all_steps


def step_counts_per_sec(raw_acc, peak_win_len=3, period_min=5, period_max=15, fs=15, mag_thres=1.2, cont_win_size=3, cont_thres = 4, var_thres = 0.001):
    """
    # peak_info[,0] - peak location
    # peak_info[,1] - acc magnitude
    # peak_info[,2] - periodicity (samples)
    # peak_info[,3] - similarity
    # peak_info[,4] - continuity
    :param raw_acc:  raw accelerometer data consists of x,y,z readings at 15 hz sampling rate shape: [num_sample, 3]
    :param peak_win_len: window length of peak detection algorithms
    :param period_min: minimum period number
    :param period_max: maximum period number
    :param fs: sampling frequency (algorithm defined at 15 Hz)
    :param mag_thres: magnitude threshold for vector magnitude sqrt(x^2+y^2+z^2)
    :param cont_win_size:  window length for calculating continuity
    :param cont_thres: continuity threshold
    :param var_thres: variance threshold
    :return: a pandas series with steps counted for every second
    """
    acc = np.sqrt(np.power(raw_acc[:,0],2) + np.power(raw_acc[:,1],2) + np.power(raw_acc[:,2],2))
    peak_data = find_peak(acc, peak_win_len)
    peak_data = filter_magnitude(peak_data, mag_thres)
    peak_data = calc_periodicity(peak_data, period_min, period_max)
    peak_data = calc_similarity(peak_data, sim_thres=-0.5)
    peak_data = filter_by_continue_threshold_variance_threshold(peak_data, acc, cont_win_size, cont_thres, var_thres)
    peak_data = counts_peaks(peak_data, acc, fs)
    return peak_data





def testEnsureSampleData(csvDataFile, rdsDataFile = None, rdsSourceUrl = None, sourceFs = 15):
    """
    Ensure the sample timestamped .csv data file exists, 
    otherwise convert from the original .rds source (downloaded if required).
    """
    import os

    # If .csv file doesn't exist yet, but an .rds source file is given, convert it from the .rds source
    if not os.path.isfile(csvDataFile) and rdsDataFile is not None:

        # If .rds file doesn't exist yet, but a URL is given, download it from the source URL
        if not os.path.isfile(rdsDataFile) and rdsSourceUrl is not None:

            # Download the .rds data
            print('DOWNLOADING: ' + rdsSourceUrl)
            import requests
            data = requests.get(rdsSourceUrl)

            # Store to an .rds file
            print('STORING: ' + rdsDataFile)
            with open(rdsDataFile, 'wb') as file:
                file.write(data.content)

        # Read the .rds file
        print('READING: ' + rdsDataFile)
        import pyreadr
        rawXYZ = pyreadr.read_r(rdsDataFile)[None].values

        # Generate timestamps
        time = np.arange(rawXYZ.shape[0]) / sourceFs
        timedXYZ = np.insert(rawXYZ, 0, time, axis=1)

        # Write a .csv file
        print('WRITING: ' + csvDataFile)
        np.savetxt(csvDataFile, timedXYZ, delimiter=',', fmt='%f')


# TODO: From step count module?
requiredFs = 15

def testSteps(sourceFile, expectedSteps):
    import openmovement.load.multi_load as multi_load

    print('LOADING: ' + sourceFile)
    with multi_load.MultiData(sourceFile) as data:
        timedXYZ = data.get_sample_values()
        sourceFs = data.get_sample_rate()
        print('SOURCE-RATE: ' + str(sourceFs))

        ## Resample timestamped data to 15 Hz for step algorithm
        if sourceFs != requiredFs:
            if sourceFs > 2 * requiredFs:
                filterFreq = requiredFs / 2
                print('FILTER: Low-pass filter, cut-off @%f Hz...' % filterFreq)
                from openmovement.process.filter import filter
                timedXYZ[:, 1:4] = filter(timedXYZ[:, 1:4], sourceFs, high_freq=filterFreq)
                print(timedXYZ)

            sourceCount = timedXYZ.shape[0]
            destNum = math.floor((requiredFs * sourceCount) // sourceFs)
            indexes = np.linspace(start=0, stop=sourceCount, num=destNum, endpoint=False, dtype=int)
            print('RESAMPLE: Nearest from %f samples @%fHz (%f s) to %f samples @%fHz (%f s)' % (sourceCount, sourceFs, sourceCount / sourceFs, destNum, requiredFs, destNum / requiredFs))
            timedXYZ = np.take(timedXYZ, indexes, axis=0)

        rawXYZ = timedXYZ[:,1:4]
        print(rawXYZ)

        print('CALCULATING...')
        totalSteps = sum(step_counts_per_sec(rawXYZ))
        print('TOTAL: %f (expected %f)' % (totalSteps, expectedSteps))
    

# Test function
def main():
    import os
    import pathlib

    sourceDir = pathlib.Path(__file__).resolve().parent

    # Future?: Test against full sample data: http://cecas.clemson.edu/tracking/PedometerData/PedometerData.zip

    # Sample data file (relative path to source file)
    dataPath = os.path.join(sourceDir, '..', '..', '_local', 'data')
    csvDataFile = os.path.join(dataPath, 'acc_xyz_for_step_counts.csv')
    rdsDataFile = os.path.join(dataPath, 'acc_xyz_for_step_counts.rds')
    sourceFs = 15     # 15 Hz
    rdsSourceUrl = 'https://github.com/bzhai/AFAR/blob/main/acc_xyz_for_step_counts.rds?raw=true'
    expectedSteps = 5874
    testEnsureSampleData(csvDataFile, rdsDataFile, rdsSourceUrl, sourceFs)

    testSteps(csvDataFile, expectedSteps)

    testDataFile = os.path.join(sourceDir, '..', '..', '_local', 'data', '610steps.cwa')
    testExpectedSteps = 610
    testSteps(testDataFile, testExpectedSteps)


if __name__ == '__main__':
    main()
