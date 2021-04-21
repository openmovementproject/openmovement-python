from math import sqrt

# "constants"
WTV_EPOCH_TIME = 30 * 60    # 30 minutes
WTV_NUM_AXES = 3            # Triaxial data
# Non-wear if std-dev <3mg for at least 2 of the 3 axes
WTV_STD_CUTOFF = 0.003
WTV_STD_MIN_AXES = 2
# Non-wear if value range <50mg for at least 2 of the 3 axes
WTV_RANGE_CUTOFF = 0.050
WTV_RANGE_MIN_AXES = 2



# Informed by: https://www.johndcook.com/blog/standard_deviation/
class RunningStats:
    def __init__(self):
        self.clear()

    def clear(self):
        self.n = 0

    def add(self, x):
        self.n += 1
        if self.n == 1:
            self.newM = x
            self.newS = 0
            self.min = x
            self.max = x
        else:
            self.newM = self.oldM + (x - self.oldM) / self.n
            self.newS = self.oldS + (x - self.oldM) * (x - self.newM)
            if (x < self.min):
                self.min = x
            if (x > self.max):
                self.max = x
        self.oldM = self.newM
        self.oldS = self.newS

    def count(self):
        return self.n

    def mean(self):
        if self.n > 0:
            return self.newM
        else:
            return 0

    def variance(self):
        if self.n > 1:
            return self.newS / (self.n - 1)
        else:
            return 0
    
    def stddev(self):
        return sqrt(self.variance())

    def range(self):
        if self.n > 0:
            return self.max - self.min
        else:
            return 0


class CalcWtv:
    """
    An iterator to calculate the Wear-Time Validation (30-minute epochs) for a given iterator yielding [time_seconds, x, y, z].
    options['alignment']  # offset to align epoch; None=align to start of data; 0=align to wall-clock time

    Based on the method by van Hees et al in PLos ONE 2011 6(7), 
      "Estimation of Daily Energy Expenditure in Pregnant and Non-Pregnant Women Using a Wrist-Worn Tri-Axial Accelerometer".
    
    Accelerometer non-wear time is estimated from the standard deviation and range of each accelerometer axis, 
    calculated for consecutive blocks of 30 minutes.
    A block was classified as non-wear time if the standard deviation was less than 3.0 mg 
    (1 mg = 0.00981 m*s-2) for at least two out of the three axes,
    or if the value range, for at least two out of three axes, was less than 50 mg.
    """

    def __init__(self, input, options):
        self.input = input
        self.options = options

        # Epoch alignment offset, e.g. 0=Align epochs since start; None=Align from start of data
        self.alignment = self.options.get('alignment', None)

        self.ended = False

        self.current_epoch_id = None
        self.current_epoch_time = None

        self.count = 0
        #self.axisSum = [0] * WTV_NUM_AXES
        #self.axisSumSquared = [0] * WTV_NUM_AXES
        #self.axisMax = [0] * WTV_NUM_AXES
        #self.axisMin = [0] * WTV_NUM_AXES
        self.runningStats = []
        for axis in range(0, WTV_NUM_AXES):
            self.runningStats.append(RunningStats())


    # Iterate on self
    def __iter__(self):
        return self
    
    def __next__(self):
        while True:
            time = None
            if not self.ended:
                try:
                    values = next(self.input)
                    time = values[0]
                except StopIteration:
                    self.ended = True

            # If epoch alignment is None, align to start of data stream
            if self.alignment is None and time is not None:
                self.alignment = -time

            # Determine which epoch we are in
            next_epoch_id = None
            next_epoch_time = None
            if time is not None:
                next_epoch_id = (time + self.alignment) // WTV_EPOCH_TIME
                next_epoch_time = (next_epoch_id * WTV_EPOCH_TIME) - self.alignment

            # If the epoch has changed, emit the previous result
            result = None
            if next_epoch_id != self.current_epoch_id:
                # Have a result to calculate
                if self.count > 0:
                    # Per-axis std-dev and range
                    count_stddev_low = 0
                    count_range_low = 0
                    for axis in range(0, WTV_NUM_AXES):

                        # Naive standard deviation 
                        #stddev = sqrt((self.axisSumSquared[axis] / self.count) - ((self.axisSum[axis] / self.count) ** 2))
                        #value_range = self.axisMax[axis] - self.axisMin[axis]

                        # Use the running stats version and ignore the naive variance 
                        stddev = self.runningStats[axis].stddev()
                        value_range = self.runningStats[axis].range()
                        
                        #import datetime
                        #print('@' + datetime.datetime.fromtimestamp(self.current_epoch_time, tz=datetime.timezone.utc).isoformat(sep=' ')[0:19] + '/' + str(axis) + ' -- stddev=' + str(stddev) + ' -- running_stddev=' + str(running_stddev) + ' -- range=' + str(value_range))

                        if stddev < WTV_STD_CUTOFF:
                            count_stddev_low += 1

                        if value_range < WTV_RANGE_CUTOFF:
                            count_range_low += 1

                    # Determine if a non-wear chunk
                    if count_stddev_low >= WTV_STD_MIN_AXES or count_range_low >= WTV_RANGE_MIN_AXES:
                        is_worn = 0
                    else:
                        is_worn = 1

                    result = (self.current_epoch_time, is_worn)

                # Start new epoch
                self.count = 0
                for axis in range(0, WTV_NUM_AXES):
                    #self.axisSum[axis] = 0
                    #self.axisSumSquared[axis] = 0
                    #self.axisMax[axis] = 0
                    #self.axisMin[axis] = 0
                    self.runningStats[axis].clear()
                self.current_epoch_id = next_epoch_id
                self.current_epoch_time = next_epoch_time

            # Add to current epoch
            if time is not None:
                for axis in range(0, WTV_NUM_AXES):
                    value = values[axis + 1]
                    #self.axisSum[axis] += value
                    #self.axisSumSquared[axis] += value * value
                    #if self.count == 0 or value < self.axisMin[axis]: self.axisMin[axis] = value
                    #if self.count == 0 or value > self.axisMax[axis]: self.axisMax[axis] = value
                    self.runningStats[axis].add(value)
                self.count += 1

            # Return result
            if result is not None:
                return result
            
            if time is None:
                raise StopIteration

