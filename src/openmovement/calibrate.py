"""
Open Movement Accelerometer Calibration
Dan Jackson, 2014-2021
Based on a C implementation by Dan Jackson/Nuls Hammerla 2014,
Based on a Matlab implementation by Nils Hammerla 2014,
Inspired by the algorithm in the GGIR package (http://cran.r-project.org/web/packages/GGIR/) by Vincent T van Hees, Zhou Fang, Jing Hua Zhao.
"""

import cwa_load

import numpy as np
from numpy.lib.stride_tricks import sliding_window_view


def find_stationary_points(samples, sample_rate, temperature=None, verbose=False):
    if verbose: print('Finding stationary points...', flush=True)

    # Parameters
    axis_std_threshold = 0.013
    window_duration = 10

    # Samples should be triaxial
    axes = samples.shape[1]
    if axes != 3:
        print('WARNING: Only designed to find stationary points in triaxial accelerometer data (%d-axis)' % axes)

    # Use zero when temperature not used
    if temperature is None:
        print('WARNING: Temperature not being used for calibration')
        temperature = np.zeros(samples.shape[0])

    # Must use 1D temperature
    if temperature.ndim != 1:
        raise Exception('Temperature can only be one-dimensional')

    # Check there is a temperature for each sample
    if temperature.shape[0] != samples.shape[0]:
        print('WARNING: Expected temperature to be same length as samples')
        if temperature.shape[0] < samples.shape[0]:
            raise Exception('When the temperature is used, each sample must have a temperature')

    # Divide into windows (window/sample/axis), (based on configured rate rather than actual)
    num_axes = samples.shape[1]
    window_size = int(sample_rate * window_duration)
    num_windows = samples.shape[0] // window_size
    covered_samples = num_windows * window_size
    windows = np.reshape(samples[0:covered_samples,:], (num_windows, -1, num_axes))
    windows_temperature = np.reshape(temperature[0:covered_samples], (num_windows, -1))

    # Transpose (axis/window/sample)
    per_axis_windows = np.transpose(windows, axes=[2,0,1])

    # Per-axis standard deviation below threshold, and all axes below threshold
    per_axis_window_std_below_threshold = np.std(per_axis_windows, axis=2) < axis_std_threshold
    windows_all_axes_std_below_threshold = np.sum(per_axis_window_std_below_threshold, axis=0) >= num_axes

    # Mean axis values and mean temperature
    per_axis_window_mean = np.mean(per_axis_windows,axis=2)
    windows_mean_temperature = np.mean(windows_temperature, axis=1)

    # Selected windows (window/axis)
    selected_window_mean = per_axis_window_mean[:,windows_all_axes_std_below_threshold].transpose()
    selected_window_temperature = windows_mean_temperature[windows_all_axes_std_below_threshold]

    # Stationary periods: (mean_x, mean_y, mean_z, temperature)
    stationary_periods = np.c_[ selected_window_mean, selected_window_temperature ]

    if verbose: print('...done (%d)' % stationary_periods.shape[0], flush=True)

    return stationary_periods
    

def calculate_calibration(stationary_points):
    
    pass

def apply_calibration(sample_values, calibration):
    pass

def main():
    filename = '../../_local/sample.cwa'
    #filename = '../../_local/mixed_wear.cwa'
    #filename = '../../_local/AX6-Sample-48-Hours.cwa'
    #filename = '../../_local/AX6-Static-8-Day.cwa'
    #filename = '../../_local/longitudinal_data.cwa'
    with cwa_load.CwaData(filename, verbose=True, include_gyro=False, include_temperature=True) as cwa_data:
        sample_values = cwa_data.get_sample_values()    # time,accel_x,accel_y,accel_z,*_,temperature

        sample_rate = cwa_data.get_sample_rate()
        stationary_points = find_stationary_points(sample_values[:,2:5], sample_rate, sample_values[:,-1], verbose=True)
        #print(stationary_points)

        calibration = calculate_calibration(stationary_points)
        print(calibration)

        #apply_calibration(sample_values)
        #print(sample_values)

        print('Done')
        
    print('End')

if __name__ == "__main__":
    main()

