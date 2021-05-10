import numpy as np

def split_into_epochs(sample_values, epoch_time_interval, timestamps=None, relative_to_time=None, return_indices=False):
    """
    Split the given ndarray data (e.g. [[time,accel_x,accel_y,accel_y,*_]])
    ...based on the timestamps array (will use the first column if not given)
    ...into a list of epochs of the specified time interval.
    """

    # The method requires at least two samples
    if sample_values.shape[0] <= 0:
        if return_indices:
            return ([], np.zeros(0,dtype=int))
        else:
            return []
    if sample_values.shape[0] <= 1:
        if return_indices:
            return ([sample_values], np.zeros(1,dtype=int))
        else:
            return [sample_values]

    # Use the first column if timestamps not given
    if timestamps is None:
        timestamps = sample_values[:,0]

    # Determine if timestamps are datetime64 (rather than seconds-since-epoch)
    is_dt64 = np.issubdtype(timestamps.dtype, np.datetime64)

    # If using datetime64, ensure epoch_time_interval is a np.timedelta64
    if is_dt64 and not np.issubdtype(epoch_time_interval, np.timedelta64):
        epoch_time_interval = np.timedelta64(epoch_time_interval, 's')

    # relative_to_time: None means the epochs start with the first sample; otherwise they  use a fixed epoch in seconds (e.g. 0=wall clock time)
    if epoch_time_offset is None:
        epoch_time_offset = timestamps[0]
    elif is_dt64:
        epoch_time_offset = relative_to_time
    else:
        epoch_time_offset = np.datetime64(relative_to_time, 's')

    # Must use 1D timestamps
    if timestamps.ndim != 1:
        raise Exception('Timestamps can only be one-dimensional')

    # Check there is a timestamps for each sample
    if timestamps.shape[0] != sample_values.shape[0]:
        print('WARNING: Expected timestamps to be same length as samples')
        if timestamps.shape[0] < sample_values.shape[0]:
            raise Exception('Each sample must have a timestamps')

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

    if return_indices:
        # Include index of first epoch
        epoch_indices = np.insert(epoch_indices, 0, [0], axis=None)
        return (epochs, epoch_indices)
    else:
        del epoch_indices
        return epochs



def _split_into_blocks_reshape_ndarray(sample_values, epoch_size_samples):
    """
    Returns a reshaped ndarray view of the given ndarray sample data (e.g. [[time,accel_x,accel_y,accel_y,*_]]) 
    as blocks of equal count samples.  As the blocks must be of a fixed size, any remainder is discarded.
    """
    sample_count = sample_values.shape[0]
    num_axes = None
    if sample_values.ndim > 1:
        num_axes = sample_values.shape[1]
    num_windows = sample_count // epoch_size_samples
    covered_sample_count = num_windows * epoch_size_samples
    if num_axes is not None:
        epochs = np.reshape(sample_values[0:covered_sample_count,:], (num_windows, -1, num_axes))
    else:
        epochs = np.reshape(sample_values[0:covered_sample_count], (num_windows, -1))
    return epochs


def _split_into_blocks_dataframe(sample_values, epoch_size_samples):
    num_windows = (len(sample_values) + epoch_size_samples - 1) // epoch_size_samples
    epochs = np.array_split(sample_values, num_windows)
    return epochs


def _split_into_blocks_generic(sample_values, epoch_size_samples):
    """
    Split an array into blocks of the specified size, the last block may be smaller.
    """
    num_windows = (len(sample_values) + epoch_size_samples - 1) // epoch_size_samples
    epochs = [None] * num_windows
    for index in range(len(epochs)):
        epochs[index] = sample_values[index * epoch_size_samples:(index + 1) * epoch_size_samples]
    return epochs


def split_into_blocks(sample_values, epoch_size_samples):
    """
    Returns a the given sample_values as blocks of epoch_size_samples.
    If an ndarray, non-full blocks are not included.
    """
    if isinstance(sample_values, numpy.ndarray):
        epochs = _split_into_blocks_reshape_ndarray(sample_values, epoch_size_samples)
    elif isinstance(sample_values, pd.DataFrame):
        epochs = _split_into_blocks_dataframe(sample_values, epoch_size_samples)
    else:
        epochs = _split_into_blocks_generic(sample_values, epoch_size_samples)
    return epochs
