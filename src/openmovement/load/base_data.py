"""
Base class for timeseries data loader
"""

from abc import ABC, abstractmethod

class BaseData(ABC):

    def __init__(self, filename, verbose=False):
        """
        Construct a data object from a file.

        :param filename: The path to the source file.
        :param verbose: Output more detailed information.
        """
        self.verbose = verbose
        # check if filename is an array of bytes or a string
        self.full_buffer = None
        self.filename = None
        if isinstance(filename, bytes):
            self.full_buffer = filename
            if self.verbose: print('File data provided: ' + str(len(self.full_buffer)), flush=True)
        else:
            self.filename = filename
            if self.verbose: print('Filename provided, will load data: ' + self.filename, flush=True)

    def _read_data(self):
        if self.full_buffer is not None:
            if self.verbose: print('File data already read...', flush=True)
            return

        if (self.filename is None):
            raise Exception('No filename/data provided?')
            return

        if self.verbose: print('Opening file...', flush=True)
        self.fh = open(self.filename, 'rb')
        try:
            import mmap
            self.full_buffer = mmap.mmap(self.fh.fileno(), 0, access=mmap.ACCESS_READ)
            if self.verbose: print('...mapped ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)
        except Exception as e:
            print('WARNING: Problem using mmap (' + str(e) +') - falling back to reading whole file...', flush=True)
            self.full_buffer = self.fh.read()
            if self.verbose: print('...read ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)


    # Nothing to do at start of 'with'
    def __enter__(self):
        return self
        
    # Close handle at end of 'with'
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    # Close handle when destructed
    def __del__(self):
        self.close()

    # Iterate
    def __iter__(self):
        return iter(self.get_sample_values())

    @abstractmethod
    def close(self):
        pass

    @abstractmethod
    def get_sample_values(self):
        """
        Get the sample values as a single ndarray.

        :returns: An ndarray of (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
                  where 'time' is in seconds since the epoch.
        """
        pass

    @abstractmethod
    def get_samples(self, use_datetime64=True):
        """
        Return an DataFrame for (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)

        :param use_datetime64: (Default) time is in datetime64[ns]; otherwise in seconds since the epoch.
        """
        pass

    # Time of first sample (seconds since epoch)
    @abstractmethod
    def get_start_time(self):
        pass

    @abstractmethod
    def get_sample_rate(self):
        pass

    # The total number of samples (only an estimate if not all loaded)
    @abstractmethod
    def get_num_samples(self):
        pass

