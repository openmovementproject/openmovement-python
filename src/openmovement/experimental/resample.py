import numpy as np
import pandas as pd

def resample(sample_values, frequency=None, value_interpolation_mode=1, maximum_missing=7*24*60*60):
    """
    Resample the given ndarray data (e.g. [[time,accel_x,accel_y,accel_y,*_]])
    ...to the fixed frequency specified, based on the time column, interpolating the values as specified.

    :param frequency: fixed frequency required (by default, the configured rate from sample_values.attrs['fs'] will be used, if available)
    :param value_interpolation_mode: 1=nearest, 2=linear, 3=cubic
    :param maximum_missing: maximum missing data to fill (None=do not fill)
    """
    raise NotImplementedError("Not implemented")
    ## TODO: calculate GCD (divisor) of in- and out-frequency, upsample 1:P (P=outFrequency/divisor), low-pass filter at intermediate frequency (inFrequency * P), downsample Q:1 (Q=resampler->inFrequency / divisor).
    pass


