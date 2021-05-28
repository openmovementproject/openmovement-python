import csv
import re
import datetime
import time

import numpy as np
import pandas as pd


# Normalize the column labels (e.g. 'Time' to 'time'; 'Accel-X (g)' to 'accel_x'; 'Gyro-Z (d/s)' to 'gyro_z')
def _normalize_label(label):
    if label is None:
        return None     # Or '' ?
    
    # Remove any strings in parentheses (e.g. units)
    reRemoveBracketed = re.compile('\(.*?\)')
    label = reRemoveBracketed.sub('', label)

    # Remove any multiple spaces
    reRemoveMultipleSpace = re.compile(' +')
    label = reRemoveMultipleSpace.sub(' ', label)

    # Remove any leading/trailing spaces
    label = label.strip()

    # Substitute spaces and hyphens with an underscore
    label = label.replace(' ', '_')
    label = label.replace('-', '_')

    # Enforce lower case
    label = label.lower()

    return label


# Convert a timestamp-with-no-timezone into a datetime (using UTC even though unknown zone, alternative is naive datetime which is assumed to be in the current local computer's time)
def _csv_datetime(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


# Convert a timestamp-with-no-timezone into a ISO-ish string representation (using UTC even though unknown zone, alternative is naive datetime which is assumed to be in the current local computer's time)
def _csv_datetime_string(time):
    if not isinstance(time, datetime.datetime):
        time = _csv_datetime(time)
    return time.isoformat(sep=' ')[0:19]


# Convert a timestamp-with-no-timezone into a ISO-ish string representation with milliseconds (using UTC even though unknown zone, alternative is naive datetime which is assumed to be in the current local computer's time)
def _csv_datetime_ms_string(time):
    if not isinstance(time, datetime.datetime):
        time = _csv_datetime(time)
    return time.isoformat(sep=' ',timespec='milliseconds')[0:23]


class CsvData:
    """
    Timeseries .CSV data.
    The first row can contain column headers.
    If there is a timestamp, it must be in the first column.
    If the timestamp is an ISO-ish date/time string, it is parsed as a time since the 1970 epoch date (in seconds, but as a datetime64[ns] by default for pandas).
    If the timestamp is numeric, the 'start_time' option may be added as an offset to apply in seconds.
    No timezone information is known (can treat as a UTC time to correctly recover the local date and time of day).
    All other columns must be numeric.
    """

    def _read_data(self):
        if self.verbose: print('Opening CSV file...', flush=True)
        self.fh = open(self.filename, 'rb')
        try:
            import mmap
            self.full_buffer = mmap.mmap(self.fh.fileno(), 0, access=mmap.ACCESS_READ)
            if self.verbose: print('...mapped ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)
        except Exception as e:
            print('WARNING: Problem using mmap (' + str(e) +') - falling back to reading whole file...', flush=True)
            self.full_buffer = self.fh.read()
            if self.verbose: print('...read ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)

    def _parse_header(self):
        if self.verbose: print('Parsing header...', flush=True)

        # Take an initial chunk of data to inspect
        initial_chunk = self.full_buffer[0:4096].decode(encoding='utf-8')
        if len(initial_chunk) == 0:
            raise Exception('File has no data')
        initial_lines = initial_chunk.splitlines()
        if len(initial_lines) < 2:
            raise Exception('File has insufficient data (or initial header/row too long)')

        # Open to inspect header and data format
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(initial_chunk)

        # Process the first CSV row
        self.header = None
        csv_reader = csv.reader(initial_lines, dialect) # quoting=csv.QUOTE_NONNUMERIC
        if sniffer.has_header(initial_chunk):
            self.header = next(csv_reader)
        try:
            first_row = next(csv_reader)
        except StopIteration:
            first_row = []

        # Number of columns
        self.num_columns = len(first_row)

        # If no header, create a numerically-labelled header
        if self.header is None:
            self.has_header = False
            self.header = list(map(str, list(range(0, self.num_columns))))
        else:
            self.has_header = True

        # Derive labels from header
        self.labels = list(map(_normalize_label, self.header))

        # RegExp to match a formatted absolute date/time (an optional 'T', optional fractions of a second, optional 'Z' or timezone offset)
        date_time_re = re.compile('^\d\d\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[-+]\d\d:\d\d)?$')

        # Decide the type of timestamps we have based on the column heading or data format
        if self.num_columns > 0 and date_time_re.match(first_row[0]):
            self.timestamps_absolute = True     # Timestamps are absolute date/times
            if self.verbose: print('Timestamps: absolute')
        elif len(self.header) > 0 and (_normalize_label(self.header[0]) == 'time' or self.force_time):
            self.timestamps_absolute = False    # Timestamps are numeric
            if self.verbose: print('Timestamps: numeric')
        else:
            self.timestamps_absolute = None     # Timestamps are missing
            if self.verbose: print('Timestamps: none')
        
        # Use a standard label for first column
        if self.timestamps_absolute is not None:
            self.labels[0] = 'time'


    def _parse_data(self):
        if self.timestamps_absolute == True:
            if self.verbose: print('Parsing data (timestamps)...', flush=True)
            # Read timestamped data with Pandas (slightly faster than numpy)
            pd_data = pd.read_csv(
                self.full_buffer, 
                parse_dates=[0], # parse_dates=['date_utc'], 
                infer_datetime_format=True, 
                sep=',', 
                usecols=list(range(0, self.num_columns)),
                header=None,        # We've already inspected the headers
                skiprows=[0] if self.has_header else [],
                names=self.labels,
            )
            # Standardized to create a single ndarray -- convert from datetime64[ns] to time since epoch in seconds
            pd_data.iloc[:,0] = pd.to_numeric(pd_data.iloc[:,0]) / 1e9
        else:
            if self.verbose: print('Parsing data (non/numeric timestamps)...', flush=True)
            # Read numeric or non-timestamped data with Pandas
            pd_data = pd.read_csv(
                self.full_buffer, 
                infer_datetime_format=True, 
                sep=',', 
                usecols=list(range(0, self.num_columns)),
                header=None,        # We've already inspected the headers
                skiprows=[0] if self.has_header else [],
                names=self.labels,
            )

        self.sample_values = pd_data.to_numpy()

            
    def _interpret_samples(self):
        if self.verbose: print('Interpreting samples...', flush=True)

        # If we don't have any timestamps, but do have an assumed frequency, synthesize relative timestamps
        if self.timestamps_absolute is None and self.assumed_frequency is not None:
            if self.verbose: print('Timestamps: synthesize->numeric')
            timestamps = np.arange(self.sample_values.shape[0]) / self.assumed_frequency
            self.sample_values = np.insert(self.sample_values, 0, timestamps, axis=1)
            self.timestamps_absolute = False

        # Where timestamps are relative, add any supplied start time
        if self.timestamps_absolute == False and self.start_time != 0:
            if self.verbose: print('Timestamps: numeric + offset')
            self.sample_values[:,0] += self.start_time

        # Start by taking the assumed frequency
        self.frequency = self.assumed_frequency

        # Where possible, estimate the sample frequency from the timestamps
        # Can't assume that the data is uninterrupted, so not just the inverse of the mean frequency from the overall duration divided by number of samples
        if self.timestamps_absolute is not None and self.sample_values.shape[0] > 1:
            # Consider the timestamps (in seconds)
            timestamps = self.sample_values[:,0]
            # Sample N pairs of adjacent times linearly throughout the data
            num_pairs = 100
            first_index = 0
            last_index = timestamps.shape[0] - 1    # each index must form a pair with the subsequent one
            sample_index = (np.arange(0, num_pairs) * ((last_index - first_index) / num_pairs) + first_index).astype(int)
            # Calculate the interval between subsequent indexes
            intervals = timestamps[sample_index + 1] - timestamps[sample_index]
            # Take the median value as the interval
            median_interval = np.median(intervals)
            # The frequency estimate is the inverse
            self.frequency = round(1.0 / median_interval, 0)

            if self.verbose: print('Frequency estimate: ' + str(self.frequency))


    def __init__(self, filename, verbose=False, force_time=False, start_time=0, assumed_frequency=None):
        """
        :param filename: The path to the .CSV file
        :param verbose: Output more detailed information.
        :param force_time: Force first column to be treated as time even if it doesn't look like an absolute timestamp and doesn't have a column header similar to 'time'.
        :param start_time: Seconds since the epoch to use as an initial time to use for relative numeric (rather than absolute) timestamps, or where the time is missing.
        :param assumed_frequency: Sampling frequency to assume if no timestamps are given.
        """
        self.filename = filename
        self.verbose = verbose
        self.force_time = force_time
        self.start_time = start_time
        self.assumed_frequency = assumed_frequency

        self.all_data_read = False

        self._read_data()
        self._parse_header()
        if self.verbose: print('...initialization done.', flush=True)


    # Current model reads all of the data in one go (and releases the file)
    def _ensure_all_data_read(self):
        start_time = time.time()
        if self.all_data_read:
            return
        self.all_data_read = True
        self._parse_data()
        self._interpret_samples()

        elapsed_time = time.time() - start_time
        if self.verbose: print('Read done... (elapsed=' + str(elapsed_time) + ')', flush=True)
        self.close()


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
        return iter(self.sample_values)

    def close(self):
        """Close the underlying file.  Automatically closed in with() block or when GC'd."""
        if self.full_buffer is not None:
            # Close if a mmap()
            if hasattr(self.full_buffer, 'close'):
                self.full_buffer.close()
            # Delete buffer (if large allocation not using mmap)
            del self.full_buffer
            self.full_buffer = None
        if self.fh is not None:
            self.fh.close()
            self.fh = None

    def get_sample_values(self):
        """
        Get the sample values as a single ndarray.

        :returns: An ndarray of the read data, e.g. (time, accel_x, accel_y, accel_z),
                  where 'time' is normalized to seconds since the epoch if from timestamps.
        """
        self._ensure_all_data_read()
        return self.sample_values

    def get_samples(self, use_datetime64=True):
        """
        Return an DataFrame, e.g. (time, accel_x, accel_y, accel_z)

        :param use_datetime64: (Default) time is in datetime64[ns]; otherwise in seconds since the epoch.
        """
        self._ensure_all_data_read()
        if self.timestamps_absolute is not None and use_datetime64:
            if self.verbose: print('Converting time...', flush=True)
            # Samples exclude the current time (float seconds) column
            samples = pd.DataFrame(self.sample_values[:,1:], columns=self.labels[1:])
            # Convert the float epoch time in seconds to a datetime64 integer in nanoseconds (Pandas default)
            time = (self.sample_values[:,0] * 1_000_000_000).astype('datetime64[ns]')
            # Add time as first column
            samples.insert(0, self.labels[0], time, True)
            if self.verbose: print('...done', flush=True)
        else:
            # Keep time (if used) in seconds
            samples = pd.DataFrame(self.sample_values, columns=self.labels)

        # Add sample metadata (start time in seconds since epoch, and configured sample frequency)
        samples.attrs['time'] = self.get_start_time()
        samples.attrs['fs'] = self.get_sample_rate()
        return samples

    # Time of first sample (seconds since epoch)
    def get_start_time(self):
        self._ensure_all_data_read()
        # For non-timestamped data, start at the given origin
        if self.timestamps_absolute is None:
            return self.start_time
        # Otherwise, the time of the first sample
        return self.sample_values[0,0]

    def get_sample_rate(self):
        self._ensure_all_data_read()
        return self.frequency

    def get_num_samples(self):
        self._ensure_all_data_read()
        return self.sample_values.shape[0]



def main():
    filename = '../../../_local/data/sample.csv'
    #filename = '../../../_local/data/mixed_wear.csv'

    with CsvData(filename, verbose=True) as csv_data:
        sample_values = csv_data.get_sample_values()
        samples = csv_data.get_samples()
        pass

    print(sample_values)
    print(samples)

    print('Done')


if __name__ == "__main__":
    main()
