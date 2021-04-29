import numpy as np

def split_into_epochs(sample_values, timestamps=None, epoch_time_interval=60, is_relative_to_first=False):
    """
    Split the given in any given format, e.g. (time,accel_x,accel_y,accel_y,*_)
    ...based on the timestamps array (will use the first column if not given)
    ...into an array of epochs of the specified time interval.
    """
    # Use the first column if timestamps not given
    if timestamps is None:
        timestamps = sample_values[:,0]

    # Optionally make the epochs start with the first sample; otherwise use absolute time
    epoch_time_offset = 0
    if is_relative_to_first:
        epoch_time_offset = timestamps[0]

    # Must use 1D timestamps
    if timestamps.ndim != 1:
        raise Exception('Timestamps can only be one-dimensional')

    # Check there is a timestamps for each sample
    if timestamps.shape[0] != sample_values.shape[0]:
        print('WARNING: Expected timestamps to be same length as samples')
        if timestamps.shape[0] < sample_values.shape[0]:
            raise Exception('Each sample must have a timestamps')

    # The below algorithm requires at least two samples
    if sample_values.shape[0] <= 1:
        return [sample_values]

    # Quantize into interval numbers
    epoch_time_index = (timestamps - epoch_time_offset) // epoch_time_interval
    
    # Calculate a mask where the index has changed from the previous one
    epoch_is_different_index = np.concatenate(([False], epoch_time_index[1:] != epoch_time_index[0:-1]))

    # Find the index of each change of epoch
    epoch_indices = np.nonzero(epoch_is_different_index)[0]

    # Split into epochs
    epochs = np.array_split(sample_values, epoch_indices, axis=0)

    del epoch_time_index
    del epoch_is_different_index
    del epoch_indices

    return epochs
