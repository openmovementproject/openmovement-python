# Frequency filtering data
from scipy.signal import butter
from scipy.signal import lfilter
from scipy.signal import sosfilt

def filter(samples, sample_freq=None, low_freq=None, high_freq=None, order=4, type='butter', method='ba'):
    # method is 'ba' or 'sos'

    # Source sample frequency
    if sample_freq is None:
        sample_freq = samples.attrs['fs']

    limit_freq = sample_freq / 2

    if type == 'butter' and (low_freq is not None and high_freq is not None):
        filter = butter(order, [low_freq / limit_freq, high_freq / limit_freq], btype='bandpass', output=method)
    elif type == 'butter' and (low_freq is None and high_freq is not None):
        filter = butter(order, high_freq / limit_freq, btype='lowpass', output=method)
    elif type == 'butter' and (low_freq is not None and high_freq is None):
        filter = butter(order, low_freq / limit_freq, btype='highpass', output=method)
    else:
        raise Exception('Unknown filter type')

    if method == 'ba':
        b, a = filter
        results = lfilter(b, a, samples, axis=0)
    elif method == 'sos':
        sos = filter
        results = sosfilt(sos, samples, axis=0)
    else:
        raise Exception('Unknown filter method')
    
    return results
