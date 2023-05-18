import math
import numpy as np
import pandas as pd

def resample(sample_values, inFrequency=None, outFrequency=None, value_interpolation_mode=1, maximum_missing=7*24*60*60):
    """
    Resample the given ndarray data (e.g. [[time,accel_x,accel_y,accel_y,*_]])
    ...to the fixed frequency specified, based on the time column, interpolating the values as specified.

    :param frequency: fixed frequency required (by default, the configured rate from sample_values.attrs['fs'] will be used, if available)
    :param value_interpolation_mode: 1=nearest, 2=linear, 3=cubic
    :param maximum_missing: maximum missing data to fill (None=do not fill)
    """

    # Calculate GCD of in- and out-frequency
    divisor = math.gcd(inFrequency, outFrequency)

    # Calculate: Upsample: 1:P; Downsample: Q:1
    upSample = outFrequency / divisor
    downSample = inFrequency / divisor
    intermediateFrequency = inFrequency * upSample
    
    # Calculate: Low-pass filter
    lowPass = 0
    if outFrequency < inFrequency:
        lowPass = outFrequency / 2

    print('RESAMPLE: (gcd %d) in %d Hz; upsample 1:%d; intermediate %d Hz; low-pass %d Hz; downsample %d:1; out %d Hz;' % (divisor, inFrequency, upSample, intermediateFrequency, lowPass, downSample, outFrequency))

    raise NotImplementedError("Not implemented")
    pass


if __name__ == "__main__":
    resample(np.array([[1,2,3,4,5],[2,3,4,5,6],[3,4,5,6,7]]), 100, 30)
