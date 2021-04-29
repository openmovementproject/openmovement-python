import numpy as np

def split_into_epochs(sample_values, epoch_time_interval=60, is_relative_to_first=False):
    """
    Split the given data in format: (time,accel_x,accel_y,accel_y,*_)
    ...into an array of epochs of the specified time interval.
    """
    # Optionally make the epochs start with the first sample; otherwise use absolute time
    epoch_time_offset = 0
    if is_relative_to_first:
        epoch_time_offset = timestamps[0]

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

    return epochs
