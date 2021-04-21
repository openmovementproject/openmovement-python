# Open Movement Python Code

<!--
```
python -m pip install -e "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"
```
-->



## omconvert wrapper

This is a Python wrapper for the `omconvert` binary, and Python implementations of some of the `omconvert` algorithms.  The `omconvert` program will process `.cwa` and `.omx` binary files and produce calculated outputs, such as SVM and WTV (wear-time validation).  It can also be used to output raw accelerometer `.csv` files (these will be very large), and they can be run through the Python versions of the analysis algorithms (slowly).

* [omconvert.py](openmovement/omconvert.py) - the Python wrapper containing the `OmConvert` class.

* [run_omconvert.py](openmovement/run_omconvert.py) - example code using the `OmConvert` class.

The example code exports the SVM and WTV files.

*IMPORTANT:* You will need the `omconvert` binary either in your `PATH`, in the current working directory, or in the same directory as the `omconvert.py` file (or, on Windows, if you have *OmGui* installed in the default location).  On Windows you can use the `bin/build-omconvert.bat` script, or on macOS/Linux you can use the `bin/build-omconvert.sh` script, or see [omconvert](https://github.com/digitalinteraction/omconvert#open-movement-file-converter) for further instructions.


## Iterable time series CSV loader

Note: This is quite slow for large amounts of data, and a `numpy`/`np.loadtxt()`, or `pandas`/`pd.readcsv()` would be faster if it was OK to load all of the data to memory.

* [timeseries_csv.py](openmovement/timeseries_csv.py) - An iterable CSV file reader.  The first row can contain column headers.  The first column must contain a timestamp.  If the timestamp is numeric, the 'time_zero' option may be added.  If the timestamp is an ISO-ish date/time, it is parsed as a time in seconds since the 1970 epoch date.  In either case, no timezone information is known, so treat as a UTC time to correctly recover date/time of day.  All other values must be numeric (a global scaling factor may be applied to these).

For files using a zero-based numeric timestamp, a helper `csv_time_from_filename()` has been provided to set the `"time_zero"` option in cases where the filename starts with the timestamp for the `0` time.

For files using raw data units, a helper `csv_scale_from_filename()` has been provided to set the `"global_scale"` option in cases where the base of the filename ends with a suffix that indicates the data type, from which the scaling may be derived.


## Python implementations of some omconvert algorithms

Note: These iteration-based versions are quite slow for large amounts of data, and would probably benefit from a `numpy` version that operates from already-loaded data.

### SVM

* [calc_svm.py](openmovement/calc_svm.py) - Calculates (as an iterator) the mean *abs(SVM-1)* value for an epoch (default 60 seconds) given an iterator yielding `[time_seconds, x, y, z]`.

* [run_svm.py](openmovement/run_svm.py) - Example showing how to run the SVM calculation from a source `.csv` file to an output `.csvm.csv` file.

### WTV

* [calc_wtv.py](openmovement/calc_svm.py) - Calculates (as an iterator) the WTV (wear-time validation) value (30 minute epochs) given an iterator yielding `[time_seconds, x, y, z]`.

* [run_wtv.py](openmovement/run_wtv.py) - Example showing how to run the WTV calculation from a source `.csv` file to an output `.cwtv.csv` file.

