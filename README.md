# Open Movement Python Code

This repository contains the Python code for the [Open Movement](https://openmovement.dev) project.

Install the current version on [PyPI](https://pypi.org/project/openmovement/):

```bash
python -m pip install openmovement
```

...or the current build on [the repository](https://github.com/digitalinteraction/openmovement-python/):

```bash
python -m pip install "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"
```


## `cwa_load` - .CWA file loader

Load `.CWA` files directly into Python (requires `numpy` and `pandas`).

```python
from openmovement.load import CwaData

filename = 'cwa-data.cwa'
with CwaData(filename, include_gyro=False, include_temperature=True) as cwa_data:
    # As an ndarray of [time,accel_x,accel_y,accel_z,temperature]
    sample_values = cwa_data.get_sample_values()
    # As a pandas DataFrame
    samples = cwa_data.get_samples()
```

You can also use `MultiData` instead of `CwaData`, which supports .CWA files, .WAV accelerometer files and timeseries .CSV files (all of which could be inside a .ZIP file).


## `omconvert` - wrapper for `omconvert` binary executable

([omconvert.py](src/openmovement/process/omconvert.py)) is a Python wrapper for the [omconvert](https://github.com/digitalinteraction/omconvert) executable, which processes `.cwa` and `.omx` binary files and produce calculated outputs, such as SVM (signal vector magnitude) and WTV (wear-time validation).  It can also be used to output raw accelerometer `.csv` files (these can be very large).

The example code, [run_omconvert.py](src/examples/run_omconvert.py), exports the SVM and WTV files.  A basic usage example is:

```python
import os
from openmovement.process import OmConvert

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
om = OmConvert()
result = om.execute(source_file, options)
```

*Note:* You will need the `omconvert` binary either in your `PATH`, in the current working directory, or in the same directory as the `omconvert.py` file (or, on Windows, if you have *OmGui* installed in the default location).  On Windows you can use the `bin/build-omconvert.bat` script to fetch the source and build the binary, or on macOS/Linux you can use the `bin/build-omconvert.sh` script. 


## `zip_helper` - "potentially zipped" file helper

Handles a "potentially zipped" file: one that may be inside a .ZIP archive but, if so, you need the extracted file on a drive and it can't be a stream from a compressed file.  For example, when you need to memory-map the file (e.g. with `cwa_load`), or use it with an external process (e.g. with `omconvert`).

Offers a convenient `with` syntax:

* If the file extension is not '.zip', the original filename is passed through via the `with` syntax.

* Otherwise, the file is opened as a .ZIP archive, and it is searched for exactly one matching filename (by default, a single-file archive).  The matching file is extracted to a temporary location, and that location is passed through the `with` syntax as the filename to use.  At the end of the `with` block, the temporary file is automatically removed.

```python
from openmovement.load import PotentiallyZippedFile

filename = 'example.zip'
with PotentiallyZippedFile(filename, ['*.cwa', '*.omx']) as file:
    print('Using: ' + file)
    pass
```


## Algorithms

### SVM - Signal Vector Magnitude

Calculates the mean *abs(SVM-1)* value (otherwise known as the Euclidean Norm Minus One) for timestamped accelerometer data (default 60 seconds).

```python
from openmovement.load import MultiData
from openmovement.process import calc_svm

filename = 'cwa-data.cwa'
with MultiData(filename) as data:
    samples = data.get_sample_values()

svm_calc = calc_svm.calculate_svm(samples)
```


### WTV - Wear-Time Validation

Calculates the wear-time validation value in 30 minute epochs for timestamped accelerometer data.

This is an implementation of the algorithm described in: van Hees et al. (2011). *Estimation of daily energy expenditure in pregnant and non-pregnant women using a wrist-worn tri-axial accelerometer*. PloS one, 6(7), e22922.

```python
from openmovement.load import MultiData
from openmovement.process import calc_wtv

filename = 'cwa-data.cwa'
with MultiData(filename) as data:
    samples = data.get_sample_values()

wtv_calc = calc_wtv.calculate_wtv(samples)
```


<!--
## Updating PyPI

```bash
# pip install build
python -m build --sdist
twine upload dist/*
```
-->
