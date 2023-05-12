# Install Python: python.org/downloads
# python -m pip install numpy scipy matplotlib "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"
# python run_accel_plot.py "CWA-DATA.CWA"

import os
import sys
import datetime

import numpy as np
from scipy.signal import butter
#from scipy.signal import lfilter
from scipy.signal import sosfilt
import matplotlib.pyplot as plt

from openmovement.load import MultiData

def run(source_file):
    # Source data (time and values)
    print('Loading data from: ' + source_file)
    with MultiData(source_file, verbose=True, include_gyro=False, include_temperature=False) as data:
        raw_samples = data.get_sample_values()
        sample_freq = data.get_sample_rate()

    # Separate accelerometer X/Y/Z values
    sample_values = raw_samples[:,1:4]

    # Calculate vector magnitude from X/Y/Z
    print('Calculating magnitude...')
    magnitude = np.sqrt(np.sum(sample_values * sample_values, axis=1))

    # Filter
    print('Frequency filtering...')
    high_freq = 10
    sos = butter(4, high_freq / (sample_freq / 2), btype='lowpass', output='sos')
    filtered_magnitude = sosfilt(sos, magnitude, axis=0)

    # Join time and magnitude
    samples = np.column_stack((raw_samples[:,0], filtered_magnitude))
    
    # Output data
    data_ext = '.accel.csv'
    data_file = os.path.splitext(source_file)[0] + data_ext
    print('Writing data to: ' + data_file)
    with open(data_file, 'w') as writer:
        writer.write("Time,Filtered Acceleration Magnitude (g)\n")
        for time, svm in samples:
            time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ')[0:19]
            line = time_string + "," + str(svm)
            writer.write(line + "\n")
    
    # Plot
    image_ext = '.accel.png'
    image_file = os.path.splitext(source_file)[0] + image_ext
    print('Plotting image to: ' + data_file)
    fig, ax = plt.subplots()
    relative_time = samples[:,0] - samples[0,0]
    ax.plot(relative_time, samples[:,1])
    ax.set(xlabel='time (s)', ylabel='acceleration (g)', title='Filtered acceleration magnitude over time')
    ax.grid()
    fig.savefig(image_file)

    # Show plot
    print('Displaying plot...')
    plt.show()
    print('...done.')


if __name__ == "__main__":
    source_files = None

    # Temporary default test file
    #source_files = ['../../_local/data/AX6-Sample.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run(file)

