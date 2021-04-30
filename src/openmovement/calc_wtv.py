import numpy as np
import epoch

# Constants
WTV_EPOCH_TIME = 30 * 60    # 30 minutes
WTV_NUM_AXES = 3            # Triaxial data
# Non-wear if std-dev <3mg for at least 2 of the 3 axes
WTV_STD_CUTOFF = 0.003
WTV_STD_MIN_AXES = 2
# Non-wear if value range <50mg for at least 2 of the 3 axes
WTV_RANGE_CUTOFF = 0.050
WTV_RANGE_MIN_AXES = 2

def calculate_wtv(sample_values, epoch_time_interval=WTV_EPOCH_TIME, relative_to_time=None):
    """
    Calculate the Wear-Time Validation (30-minute epochs) for a given sample ndarray [[time_seconds, accel_x, accel_y, accel_z]].

    Based on the method by van Hees et al in PLos ONE 2011 6(7), 
      "Estimation of Daily Energy Expenditure in Pregnant and Non-Pregnant Women Using a Wrist-Worn Tri-Axial Accelerometer".
    
    Accelerometer non-wear time is estimated from the standard deviation and range of each accelerometer axis, 
    calculated for consecutive blocks of 30 minutes.
    A block was classified as non-wear time if the standard deviation was less than 3.0 mg 
    (1 mg = 0.00981 m*s-2) for at least two out of the three axes,
    or if the value range, for at least two out of three axes, was less than 50 mg.

    epoch_time_interval   -- seconds per epoch (the algorithm is defined for 30 minutes)
    relative_to_time      -- None=align to start of data, 0=align to wall-clock time
    """

    if epoch_time_interval != WTV_EPOCH_TIME:
        eprint('WARNING: WTV algorithm is defined for %d minutes (but using %d minutes)' % (WTV_EPOCH_TIME, epoch_time_interval))

    # Split samples into epochs
    epochs = epoch.split_into_epochs(sample_values, epoch_time_interval, relative_to_time=relative_to_time)

    # Calculate each epoch
    num_epochs = len(epochs)
    result = np.empty((num_epochs,2))
    for epoch_index in range(num_epochs):
        this_epoch = epochs[epoch_index]

        # Epoch start time and sample data
        epoch_time = this_epoch[0,0]
        samples = this_epoch[:,1:4]
        
        # Per-axis/sample standard deviation and range
        stddev = np.std(samples, axis=0)
        value_range = np.ptp(samples, axis=0)

        # Count axes
        count_stddev_low = np.sum(stddev < WTV_STD_CUTOFF)
        count_range_low = np.sum(value_range < WTV_RANGE_CUTOFF)

        # Determine if worn
        if count_stddev_low >= WTV_STD_MIN_AXES or count_range_low >= WTV_RANGE_MIN_AXES:
            epoch_value = 0
        else:
            epoch_value = 1

        # Result
        result[epoch_index,0] = epoch_time
        result[epoch_index,1] = epoch_value

    return result
