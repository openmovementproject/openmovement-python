import math
import numpy as np
import pandas as pd
import scipy

from openmovement.process.filter import filter

def resample_fixed(sample_values, inFrequency=None, outFrequency=None, interpolation_mode='linear'):
    """
    Resample a fixed-rate ndarray data (e.g. [[accel_x,accel_y,accel_y,*_]]) to the specified frequency.

    :param sample_values: (multi-axis) fixed rate data to resample
    :param inFrequency: input data frequency (the nominal rate from sample_values.attrs['fs'] will be used, if available)
    :param outFrequency: output frequency required
    :param interpolation_mode: 'nearest', 'linear', 'cubic', 'quadratic', etc.
    """

    # Defaults
    if inFrequency is None:
        inFrequency = sample_values.attrs['fs']
    if outFrequency is None:
        outFrequency = inFrequency

    # Calculate
    divisor = math.gcd(inFrequency, outFrequency)
    if len(sample_values.shape) == 1:
        multiAxis = 0
    else:
        multiAxis = sample_values.shape[1]

    # Calculate: Upsample: 1:P; Downsample: Q:1
    upSample = outFrequency // divisor
    downSample = inFrequency // divisor
    intermediateFrequency = inFrequency * upSample
    
    # Calculate: Low-pass filter
    lowPass = 0
    if outFrequency < inFrequency:
        lowPass = outFrequency / 2

    # Display plan
    print('RESAMPLE: gcd %d; %d axes; %d samples; in %d Hz; upsample 1:%d; intermediate %d Hz; low-pass %d Hz; downsample %d:1; out %d Hz;' % (divisor, multiAxis, sample_values.shape[0], inFrequency, upSample, intermediateFrequency, lowPass, downSample, outFrequency))
    data = sample_values
    print(data)
    
    # Upsample: 1:P
    if upSample > 1 and len(data) > 0:
        # Count to ensure 1:N interpolation samples line up with source data
        intermediateCount = (len(data) - 1) * upSample + 1
        print('RESAMPLE: Upsample: %d axes - %d samples at %d Hz --> 1:%d --> %d samples at %d Hz' % (multiAxis, len(data), inFrequency, upSample, intermediateCount, intermediateFrequency))
        # ...
        inIndex = np.linspace(0, 1, len(data))
        outIndex = np.linspace(0, 1, intermediateCount)
        if multiAxis > 0:
            upsampled_data = np.empty([intermediateCount, multiAxis])
            for axis in range(0, multiAxis):
                upsampled_data[:,axis] = scipy.interpolate.interp1d(inIndex, data[:,axis], kind=interpolation_mode)(outIndex)
            data = upsampled_data
        else:
            data = scipy.interpolate.interp1d(inIndex, data, kind=interpolation_mode)(outIndex)
        print(data)
    else:
        print('RESAMPLE: Upsample not required')

    # Low-pass filter
    if lowPass > 0:
        print('RESAMPLE: Low-pass filter at %d Hz (intermediate at %d Hz, output at %d Hz)' % (lowPass, intermediateFrequency, outFrequency))
        data = filter(data, sample_freq=intermediateFrequency, low_freq=None, high_freq=lowPass)    # order=4, type='butter', method='ba'
        print(data)
    else:
        print('RESAMPLE: Low-pass filter not required (output frequency is >= input frequency)')

    # Downsample: Q:1
    if downSample > 1 and len(data) > 0:
        outputCount = (len(data) - 1) // downSample + 1
        print('RESAMPLE: Downsample: %d axes - %d samples at %d Hz --> %d:1 --> %d samples at %d Hz' % (multiAxis, len(data), intermediateFrequency, downSample, outputCount, outFrequency))
        if multiAxis > 0:
            data = data[::downSample,:]
        else:
            data = data[::downSample]
        print(data)
    else:
        print('RESAMPLE: Downsample not required')

    return data



def resample_time(sample_values, frequency=None, interpolation_mode='nearest', earliest_time=None, latest_time=None, maximum_missing=7*24*60*60):
    """
    Resample the given ndarray data (e.g. [[time,accel_x,accel_y,accel_y,*_]]) to be at the fixed frequency specified, 
      based on the time column, interpolating the values as required.
      
    Returns chunks of data separated by gaps exceeding the maximum_missing seconds, or where time is not monotonically increasing.

    :param frequency: fixed frequency required (by default, the configured sample rate from sample_values.attrs['fs'] will be used, if available)
    :param interpolation_mode: 'nearest', 'linear', 'cubic', 'quadratic', etc.
    :param maximum_missing: maximum missing data (seconds) to fill as empty
    """

    # Not implemented
    raise NotImplementedError("Time-based resampling not implemented")



if __name__ == "__main__":
    data = resample_fixed(np.array([100,101,102,103,104,105,106,107,108,109,110]), 100, 30)
    print(data)

    data = resample_fixed(np.array([
            [100,200,300],
            [101,201,301],
            [102,202,302],
            [103,203,303],
            [104,204,304],
            [105,205,305],
            [106,206,306],
            [107,207,307],
            [108,208,308],
            [109,209,309],
            [110,210,310],
        ]), 100, 30)
    print(data)

