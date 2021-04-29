import numpy as np
import epoch

def calculate_svm(sample_values, epoch_time_interval=60, relative_to_time=None):
    """
    Calculate the mean(abs(SVM-1)) value for the given sample ndarray [[time_seconds, accel_x, accel_y, accel_z]]
    epoch_time_interval   -- seconds per epoch
    relative_to_time      -- None=align to start of data, 0=align to wall-clock time
    """

    # Split into (timestamp) and (accel_x,accel_y,accel_z)
    timestamps = sample_values[:,0]
    samples = sample_values[:,1:4]

    # Calculate Euclidean norm minus one 
    samples_enmo = np.sqrt(np.sum(samples * samples, axis=1)) - 1
    # This scalar vector magnitude approach takes the absolute value
    samples_svm = np.abs(samples_enmo)

    # Split SVM into epochs
    (epochs, epoch_indices) = epoch.split_into_epochs(samples_svm, epoch_time_interval, timestamps=timestamps, relative_to_time=relative_to_time, return_indices=True)

    # Take mean of SVM
    num_epochs = len(epochs)
    mean_svm = np.empty(num_epochs)
    for epoch_index in range(num_epochs):
        this_epoch = epochs[epoch_index]
        mean_svm[epoch_index] = np.mean(this_epoch)

    # Locate timestamp for each epoch
    epoch_timestamps = np.take(timestamps, epoch_indices)

    # Create a result of (time,value)
    result = np.column_stack((epoch_timestamps,mean_svm))

    return result
