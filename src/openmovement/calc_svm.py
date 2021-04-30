import numpy as np
import openmovement.epoch

# TODO: Add options for frequency filtering
# def _butter_bandpass_filter(samples, sample_freq, low_freq, high_freq, order=4, method='ba'):
#     from scipy.signal import butter
#     limit_freq = sample_freq / 2
#     low = low_freq / limit_freq
#     high = high_freq / limit_freq

#     if method == 'ba':
#         from scipy.signal import lfilter
#         b, a = butter(order, [low, high], btype='band', output='ba')
#         results = lfilter(b, a, samples, axis=0)
#     elif method == 'sos':
#         from scipy.signal import sosfilt
#         sos = butter(order, [low, high], btype='band', output='sos')
#         results = sosfilt(sos, samples, axis=0)
#     else:
#         raise Exception('Unknown filter method')

#     return results


def calculate_svm(sample_values, epoch_time_interval=60, truncate=False, relative_to_time=None):
    """
    Calculate the mean(abs(SVM-1)) value for the given sample ndarray [[time_seconds, accel_x, accel_y, accel_z]]
    
    epoch_time_interval   -- seconds per epoch
    relative_to_time      -- None=align to start of data, 0=align to wall-clock time
    truncate              -- Use max(SVM-1,0) rather than abs(SVM-1)
    """

    # Split samples into epochs
    epochs = openmovement.epoch.split_into_epochs(sample_values, epoch_time_interval, relative_to_time=relative_to_time)

    # Calculate each epoch
    num_epochs = len(epochs)
    result = np.empty((num_epochs,2))
    for epoch_index in range(num_epochs):
        this_epoch = epochs[epoch_index]

        # Epoch start time and sample data
        epoch_time = this_epoch[0,0]
        samples = this_epoch[:,1:4]
        
        # Calculate Euclidean norm minus one 
        samples_enmo = np.sqrt(np.sum(samples * samples, axis=1)) - 1

        # This scalar vector magnitude approach takes the absolute value
        if truncate:
            samples_svm = samples_enmo
            samples_svm[samples_svm < 0] = 0
        else:
            samples_svm = np.abs(samples_enmo)

        # Mean of the value
        epoch_value = np.mean(samples_svm)

        # Result
        result[epoch_index,0] = epoch_time
        result[epoch_index,1] = epoch_value

    return result
