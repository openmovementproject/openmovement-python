# Open Movement Python Code

This repository contains the Python code for the [Open Movement](https://openmovement.dev) project.

```bash
python -m pip install "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"
```


## Wrapper for 'omconvert'

This ([omconvert.py](src/openmovement/omconvert.py)) is a Python wrapper for the [omconvert](https://github.com/digitalinteraction/omconvert) executable, which processes `.cwa` and `.omx` binary files and produce calculated outputs, such as SVM (signal vector magnitude) and WTV (wear-time validation).  It can also be used to output raw accelerometer `.csv` files (these can be very large).

The example code, [run_omconvert.py](src/run_omconvert.py), exports the SVM and WTV files.  A basic usage example is:

```python
import os
from openmovement import omconvert

source_file = 'CWA-DATA.CWA'

base_name = os.path.splitext(source_file)[0]
options = {}

# Nearest-point sampling
options['interpolate_mode'] = 1

# Optionally export accelerometer CSV file (can take a long time)
#options['csv_file'] = base_name + '.csv'

# SVM (no filter)
options['svm_filter'] = 0
options['svm_file'] = base_name + '.svm.csv'

# Wear-time validation
options['wtv_file'] = base_name + '.wtv.csv'

# Run the processing
om = omconvert.OmConvert()
result = om.execute(source_file, options)
```

*NOTE:* You will need the `omconvert` binary either in your `PATH`, in the current working directory, or in the same directory as the `omconvert.py` file (or, on Windows, if you have *OmGui* installed in the default location).  On Windows you can use the `bin/build-omconvert.bat` script to fetch the source and build the binary, or on macOS/Linux you can use the `bin/build-omconvert.sh` script. 


## CWA Loader

```python
from openmovement import cwa_load

filename = 'CWA-DATA.CWA'
with CwaData(filename, verbose=True, include_gyro=False, include_temperature=True) as cwa_data:
    # (time,accel_x,accel_y,accel_z,temperature)
    sample_values = cwa_data.get_sample_values()
    # As a pandas DataFrame
    samples = cwa_data.get_samples()


<!--

## Iterable time series CSV loader

Note: This is quite slow for large amounts of data, and a `numpy`/`np.loadtxt()`, or `pandas`/`pd.readcsv()` would be faster if it was OK to load all of the data to memory.

* [timeseries_csv.py](src/openmovement/timeseries_csv.py) - An iterable CSV file reader.  The first row can contain column headers.  The first column must contain a timestamp.  If the timestamp is numeric, the 'time_zero' option may be added.  If the timestamp is an ISO-ish date/time, it is parsed as a time in seconds since the 1970 epoch date.  In either case, no timezone information is known, so treat as a UTC time to correctly recover date/time of day.  All other values must be numeric (a global scaling factor may be applied to these).


## Python implementations of algorithms

Note: These iteration-based versions are quite slow for large amounts of data, and would probably benefit from a `numpy` version that operates from already-loaded data.

### SVM

* [calc_svm.py](src/openmovement/calc_svm.py) - Calculates (as an iterator) the mean *abs(SVM-1)* value for an epoch (default 60 seconds) given an iterator yielding `[time_seconds, x, y, z]`.

* [run_svm.py](src/openmovement/run_svm.py) - Example showing how to run the SVM calculation from a source `.csv` file to an output `.csvm.csv` file.

### WTV

* [calc_wtv.py](src/openmovement/calc_svm.py) - Calculates (as an iterator) the WTV (wear-time validation) value (30 minute epochs) given an iterator yielding `[time_seconds, x, y, z]`.

* [run_wtv.py](src/openmovement/run_wtv.py) - Example showing how to run the WTV calculation from a source `.csv` file to an output `.cwtv.csv` file.

-->
