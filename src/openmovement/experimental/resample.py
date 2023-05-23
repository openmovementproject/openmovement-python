import math
import numpy as np
import pandas as pd
import scipy

from openmovement.process.filter import filter

def resample_fixed(sample_values, in_frequency=None, out_frequency=None, interpolation_mode='linear'):
    """
    Resample a fixed-rate ndarray data (e.g. [[accel_x,accel_y,accel_y,*_]]) to the specified frequency.

    :param sample_values: (multi-axis) fixed rate data to resample
    :param in_frequency: input data frequency (the nominal rate from sample_values.attrs['fs'] will be used, if available)
    :param out_frequency: output frequency required
    :param interpolation_mode: 'nearest', 'linear', 'cubic', 'quadratic', etc.
    """

    # Defaults
    if in_frequency is None:
        if hasattr(data, 'dtype') and hasattr(data.dtype, 'metadata') and data.dtype.metadata != None and 'fs' in data.dtype.metadata:
            in_frequency = data.dtype.metadata['fs']
        elif hasattr(data, 'attrs') and 'fs' in data.attrs:
            in_frequency = data.attrs['fs']
    if out_frequency is None:
        out_frequency = in_frequency

    # Check valid frequencies
    if in_frequency is None or out_frequency is None:
        raise Exception("RESAMPLE: Invalid input/output frequency")

    # Calculate
    divisor = math.gcd(in_frequency, out_frequency)
    if len(sample_values.shape) == 1:
        multi_axis = 0
    else:
        multi_axis = sample_values.shape[1]

    # Calculate: Upsample: 1:P; Downsample: Q:1
    up_sample = out_frequency // divisor
    down_sample = in_frequency // divisor
    intermediateFrequency = in_frequency * up_sample
    
    # Calculate: Low-pass filter
    lowPass = 0
    if out_frequency < in_frequency:
        lowPass = out_frequency / 2

    # Display plan
    print('RESAMPLE: gcd %d; %d axes; %d samples; in %d Hz; upsample 1:%d; intermediate %d Hz; low-pass %d Hz; downsample %d:1; out %d Hz;' % (divisor, multi_axis, sample_values.shape[0], in_frequency, up_sample, intermediateFrequency, lowPass, down_sample, out_frequency))
    data = sample_values
    print(data)
    
    # Upsample: 1:P
    if up_sample > 1 and len(data) > 0:
        # Count to ensure 1:N interpolation samples line up with source data
        intermediateCount = (len(data) - 1) * up_sample + 1
        print('RESAMPLE: Upsample: %d axes - %d samples at %d Hz --> 1:%d --> %d samples at %d Hz' % (multi_axis, len(data), in_frequency, up_sample, intermediateCount, intermediateFrequency))
        # ...
        inIndex = np.linspace(0, 1, len(data))
        outIndex = np.linspace(0, 1, intermediateCount)
        if multi_axis > 0:
            up_sampled_data = np.empty([intermediateCount, multi_axis])
            for axis in range(0, multi_axis):
                up_sampled_data[:,axis] = scipy.interpolate.interp1d(inIndex, data[:,axis], kind=interpolation_mode)(outIndex)
            data = up_sampled_data
        else:
            data = scipy.interpolate.interp1d(inIndex, data, kind=interpolation_mode)(outIndex)
        print(data)
    else:
        print('RESAMPLE: Upsample not required')

    # Low-pass filter
    if lowPass > 0:
        print('RESAMPLE: Low-pass filter at %d Hz (intermediate at %d Hz, output at %d Hz)' % (lowPass, intermediateFrequency, out_frequency))
        data = filter(data, sample_freq=intermediateFrequency, low_freq=None, high_freq=lowPass)    # order=4, type='butter', method='ba'
        print(data)
    else:
        print('RESAMPLE: Low-pass filter not required (output frequency is >= input frequency)')

    # Downsample: Q:1
    if down_sample > 1 and len(data) > 0:
        outputCount = (len(data) - 1) // down_sample + 1
        print('RESAMPLE: Downsample: %d axes - %d samples at %d Hz --> %d:1 --> %d samples at %d Hz' % (multi_axis, len(data), intermediateFrequency, down_sample, outputCount, out_frequency))
        if multi_axis > 0:
            data = data[::down_sample,:]
        else:
            data = data[::down_sample]
        print(data)
    else:
        print('RESAMPLE: Downsample not required')

    return data



def resample_time(samples, frequency=None, interpolation_mode='nearest', start_time=None, end_time=None, maximum_missing=7*24*60*60):
    """
    Resample the given ndarray data (e.g. [[time,accel_x,accel_y,accel_y,*_]]) to be at the fixed frequency specified, 
      based on the time column, interpolating the sample values as required.
      
    TODO: Returns chunks of data separated by gaps exceeding the maximum_missing seconds, or where time is not monotonically increasing.

    :param samples: timestamped samples (e.g. [[time,accel_x,accel_y,accel_y,*_]])
    :param frequency: fixed frequency required, or None to attempt to detect the input frequency, or a list of allowed frequencies to find the nearest match.
    :param interpolation_mode: 'nearest', 'linear', 'cubic', 'quadratic', etc.
    :param maximum_missing: TODO: maximum missing data (seconds) to fill as empty
    """

    # Defaults
    if frequency is None:
        if hasattr(samples, 'dtype') and hasattr(samples.dtype, 'metadata') and samples.dtype.metadata != None and 'fs' in samples.dtype.metadata:
            frequency = samples.dtype.metadata['fs']
        elif hasattr(samples, 'attrs') and 'fs' in samples.attrs:
            frequency = samples.attrs['fs']

    # Determine start/end times
    if start_time is None and len(samples) > 0:
        start_time = samples[0,0]
    if end_time is None and len(samples) > 0:
        end_time = samples[-1,0]
    
    # Estimate sample frequency
    if len(samples) > 1:
        frequency_estimate = (len(samples) - 1) / (end_time - start_time)
    else:
        frequency_estimate = 0
    # Snap estimate to allowed values
    if hasattr(frequency, "__len__"):
        frequency_estimate = min(frequency, key=lambda freq : abs(freq - frequency_estimate))
        frequency = None
    # Use estimate if no frequency specified
    if frequency is None:
        frequency = frequency_estimate

    # Check valid frequencies
    if frequency is None:
        raise Exception("RESAMPLE: Invalid output frequency")
    
    # Number of output samples required
    if end_time == start_time:
        sample_count = 1
    elif end_time > start_time:
        sample_count = math.ceil((end_time - start_time) * frequency) + 1
    else:
        sample_count = 0

    # TODO: Detect chunks of data separated by gaps exceeding the maximum_missing seconds, or where time is not monotonically increasing.
    
    print("RESAMPLE: %d incoming samples from times %d-%d to %d outgoing samples at %d Hz" % (len(samples), start_time, end_time, sample_count, frequency))

    in_timestamps = samples[:,0]
    out_timestamps = start_time + np.arange(0, sample_count) / frequency

    num_axes = samples.shape[1] - 1

    #rate_type = np.dtype(float, metadata={"fs": frequency})
    resampled_data = np.empty([sample_count, num_axes + 1]) # dtype=rate_type

    resampled_data[:,0] = out_timestamps
    for axis in range(1, num_axes + 1):
        resampled_data[:,axis] = scipy.interpolate.interp1d(in_timestamps, samples[:,axis], kind=interpolation_mode)(out_timestamps)

    #samples.attrs['fs'] = frequency

    return resampled_data


if __name__ == "__main__":
    # data = resample_fixed(np.array([100,101,102,103,104,105,106,107,108,109,110]), 100, 30)
    # print(data)

    # data = resample_fixed(np.array([
    #         [100,200,300],
    #         [101,201,301],
    #         [102,202,302],
    #         [103,203,303],
    #         [104,204,304],
    #         [105,205,305],
    #         [106,206,306],
    #         [107,207,307],
    #         [108,208,308],
    #         [109,209,309],
    #         [110,210,310],
    #     ]), 100, 30)
    # print(data)

    data = resample_time(np.array([
            [10.0,100,200,300],
            [10.1,101,201,301],
            [10.2,102,202,302],
            [10.3,103,203,303],
            [10.4,104,204,304],
            [10.5,105,205,305],
            [10.6,106,206,306],
            [10.7,107,207,307],
            [10.8,108,208,308],
            [10.9,109,209,309],
            [11.0,110,210,310],
        ]))
    print(data)
