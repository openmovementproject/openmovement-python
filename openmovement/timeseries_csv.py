import csv
import re
import os
import datetime
import array


# For files with relative numeric timestamps that store the base time in the filename
def csv_time_from_filename(csv_filename):
    time_zero = 0
    parts = re.match('(\d\d\d\d)-?(\d\d)-?(\d\d)[-T ]?(\d\d):?(\d\d):?(\d\d)(\.?\d\d\d)?', os.path.basename(csv_filename))
    if parts:
        msec = parts.group(7)
        if msec == None:
            msec = 0
        else:
            msec = int(msec)
        time_zero = datetime.datetime(int(parts.group(1)), int(parts.group(2)), int(parts.group(3)), int(parts.group(4)), int(parts.group(5)), int(parts.group(6)), msec * 1000, tzinfo=datetime.timezone.utc).timestamp()
    return time_zero


# For files where the scaling metadata is stored int the last part of the filename
def csv_scale_from_filename(csv_filename):
    global_scale = 1
    basename = os.path.splitext(os.path.basename(csv_filename))[0]
    if basename.endswith('_ACC'):
        global_scale = 0.0002   # really 1/5000? Or possibly 1/4096?
    if basename.endswith('_GYR'):
        global_scale = 0.0305   # probably 1/32768
    if basename.endswith('_EEG') or basename.endswith('_EOG'):
        global_scale = 0.4808
    if basename.endswith('_ECG'):
        global_scale = 1.4424
    if basename.endswith('_EMG'):
        global_scale = 0.4808
    return global_scale


# Convert a timestamp-with-no-timezone into a datetime (using UTC even though unknown zone, alternative is naive datetime which is assumed to be in the current local computer's time)
def csv_datetime(timestamp):
    return datetime.datetime.fromtimestamp(timestamp, tz=datetime.timezone.utc)


# Convert a timestamp-with-no-timezone into a ISO-ish string representation (using UTC even though unknown zone, alternative is naive datetime which is assumed to be in the current local computer's time)
def csv_datetime_string(time, with_milliseconds):
    if not isinstance(time, datetime.datetime):
        time = csv_datetime(time)
    if with_milliseconds:
        return time.isoformat(sep=' ',timespec='milliseconds')[0:23]
    else:
        return time.isoformat(sep=' ')[0:19]



def csv_load_numpy(filename):
    """Use numpy to load ISO-timestamped x/y/z data"""
    import numpy as np
    return np.loadtxt(
        filename, 
        delimiter=',', 
        skiprows=1,
        usecols=(0,1,2,3),
        # dtype={
        #     'names': ('timestamp', 'x', 'y', 'z'),
        #     'formats': ['f8', 'f8', 'f8', 'f8'],    # 'datetime64[us]'
        # }, 
        converters={
            0: lambda value: np.datetime64(value, 'ms').astype('int64') / 1000  # Seconds since epoch
            # 0: lambda value: np.datetime64(value, 'ms')
            # 0: lambda value: datetime.datetime.fromisoformat(value.decode("utf-8") + '+00:00').timestamp()
            # 0: lambda value: np.datetime64(datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')))
        },
    )


def csv_load_pandas(filename):
    """Use pandas to load ISO-timestamped x/y/z data"""
    import pandas as pd
    pd_data = pd.read_csv(
        filename, 
        parse_dates=[0], 
        infer_datetime_format=True, 
        #date_parser = lambda value: datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S.%f").timestamp(),
        #date_parser = lambda value: np.datetime64(value, 'ms').astype('int64') / 1000,  # Seconds since epoch
        sep=',', 
        usecols=[0,1,2,3],
    )
    # Use time since epoch in seconds
    pd_data.iloc[:,0] = pd.to_numeric(pd_data.iloc[:,0]) / 1e9
    return pd_data.values
    #return np.array(pd_data)




class TimeseriesCsv:
    """
    Open a .CSV file as iterable over each row.
    The first row can contain column headers.
    The first column must contain a timestamp.  If the timestamp is numeric, the 'time_zero' option may be added.  
    If the timestamp is an ISO-ish date/time, it is parsed as a time in seconds since the 1970 epoch date.
    In either case, no timezone information is known, so treat as a UTC time to correctly recover date/time of day.
    All other values must be numeric (a global scaling factor may be applied to these).
    """
    def __init__(self, csv_filename, options = {}):
        self.options = options

        # For relative numeric timestamps, the epoch time for zero
        self.time_zero = self.options.get('time_zero') or 0

        # An overall timstamp offset (e.g. to convert to a time zone)
        self.time_offset = self.options.get('time_offset') or 0

        # Apply scaling for columns other than the first column
        self.global_scale = self.options.get('global_scale') or 1

        self.csv_file = open(csv_filename, newline='')

        initial_chunk = self.csv_file.read(1024)
        sniffer = csv.Sniffer()
        dialect = sniffer.sniff(initial_chunk)

        self.csv_file.seek(0)
        self.csv_reader = csv.reader(self.csv_file, dialect) # quoting=csv.QUOTE_NONNUMERIC

        if sniffer.has_header(initial_chunk):
            self.header = next(self.csv_reader)
        else:
            self.header = None

        try:
            first_row = next(self.csv_reader)
        except StopIteration:
            first_row = []

        self.num_columns = len(first_row)
        self.empty_row = [0] * self.num_columns

        # Check whether the first column in a formatted date/time
        date_time_re = re.compile('^\d\d\d\d-\d\d-\d\d[T ]\d\d:\d\d:\d\d\.?(?:\d\d\d)?$')
        if self.num_columns > 0:
            self.initial_date_time = date_time_re.match(first_row[0])
        else:
            self.initial_date_time = None

        # Reset to first row
        self.csv_file.seek(0)
        if self.header != None:
            next(self.csv_reader)
        
        # Line number 1 after reading first row
        self.line_num = 0

    # Nothing to do at start of 'with'
    def __enter__(self):
        pass
        
    # Close handle at end of 'with'
    def __exit__(self):
        self.close()
    
    # Close handle when destructed
    def __del__(self):
        self.close()

    # Iterating can use self
    def __iter__(self):
        return self

    # Process next CSV line
    def __next__(self):
        try:
            row = next(self.csv_reader)
            self.line_num += 1
        except StopIteration:
            self.close()
            raise   # Cascade StopIteration to caller
            
        row_values = array.array('d', self.empty_row)
        
        # First column is time
        if self.initial_date_time:
            # Seconds since epoch but no timezone
            timestamp = datetime.datetime.fromisoformat(row[0] + '+00:00').timestamp()
            row_values[0] = timestamp + self.time_offset
        else:
            row_values[0] = float(row[0]) + self.time_zero + self.time_offset

        # Remaining columns are data, potentially scaled
        for i in range(1, len(row)):
            if i < self.num_columns:
                row_values[i] = float(row[i]) * self.global_scale
        
        return row_values


    def close(self):
        """
        Close the underlying file.
        Automatically closed in a 'with' block, or after reading past the last row, or when GCd.
        """
        if self.csv_reader is not None:
            self.csv_reader = None
        if self.csv_file is not None:
            self.csv_file.close()
            self.csv_file = None
        

    def read_row(self):
        """
        Read the next row, returning a numeric array of num_columns, or None if no more rows.
        Alternatively, the rows can be read and iterated with a for-in loop.
        """
        try:
            return next(self)
        except StopIteration:
            return None


    def read_all(self):
        """
        Read the remaining rows as a list.
        The file will be closed.
        """
        values = []

        for row_values in self:
            values.append(row_values)

        return (self.header, values)


def main():
    test_file = '../_local/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv'
    #test_file = '../_local/sample.csv'

    tscsv = TimeseriesCsv(test_file, {"time_zero": csv_time_from_filename(test_file), "global_scale": csv_scale_from_filename(test_file)})
    print(tscsv.header)
    for values in tscsv:
        if tscsv.line_num >= 10:
            break
        time_string = csv_datetime_string(values[0], True)
        print('#' + str(tscsv.line_num) + ' @' + time_string + ' = ' + str(values))

if __name__ == "__main__":
    main()
