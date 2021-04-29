import numpy as np
import epoch

def calculate_svm(sample_values, epoch_time_interval=60, relative_to_time=None):
    """
    Calculate the mean(abs(SVM-1)) value for the given sample ndarray [[time_seconds, accel_x, accel_y, accel_z]]
    
    epoch_time_interval   -- seconds per epoch
    relative_to_time      -- None=align to start of data, 0=align to wall-clock time
    """

    # Split samples into epochs
    epochs = epoch.split_into_epochs(sample_values, epoch_time_interval, timestamps=timestamps, relative_to_time=relative_to_time)

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
        samples_svm = np.abs(samples_enmo)

        # Mean of the value
        epoch_value = np.mean(samples_svm)

        # Result
        result[epoch_index,0] = epoch_time
        result[epoch_index,1] = epoch_value

    return result
