from math import sqrt

class CalcSvm:
    """
    An iterator to calculate the SVM value for a given iterator yielding [time_seconds, x, y, z].
    options['epoch_size'] # seconds per epoch
    options['alignment']  # offset to align epoch; None=align to start of data; 0=align to wall-clock time
    """

    def __init__(self, input, options):
        self.input = input
        self.options = options

        # Epoch size (default 1 minute)
        self.epoch_size = self.options.get('epoch_size', 60)

        # Epoch alignment offset, e.g. 0=Align epochs since start; None=Align from start of data
        self.alignment = self.options.get('alignment', None)

        self.current_epoch_id = None
        self.current_epoch_time = None
        self.ended = False

        # Status
        self.count = 0
        self.sum = 0


    # Iterate on self
    def __iter__(self):
        return self
    
    def __next__(self):
        while True:
            time = None
            if not self.ended:
                try:
                    [time, x, y, z, *_] = next(self.input)
                except StopIteration:
                    self.ended = True

            # If epoch alignment is None, align to start of data stream
            if self.alignment is None and time is not None:
                self.alignment = -time

            # Determine which epoch we are in
            next_epoch_id = None
            next_epoch_time = None
            if time is not None:
                next_epoch_id = (time + self.alignment) // self.epoch_size
                next_epoch_time = (next_epoch_id * self.epoch_size) - self.alignment

            # If the epoch has changed, emit the previous result
            result = None
            if next_epoch_id != self.current_epoch_id:
                if self.count > 0:
                    # Return mean SVM
                    value = self.sum / self.count
                    result = (self.current_epoch_time, value)
                self.sum = 0
                self.count = 0
                self.current_epoch_id = next_epoch_id
                self.current_epoch_time = next_epoch_time

            # Calculate SVM and add to current epoch
            if time is not None:
                en = sqrt((x * x) + (y * y) + (z * z))
                enmo = en - 1
                svm = abs(enmo)
                self.sum += svm
                self.count += 1

            # Return result
            if result is not None:
                return result
            
            if time is None:
                raise StopIteration

