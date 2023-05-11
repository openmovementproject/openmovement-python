# Install Python: python.org/downloads
# python -m pip install numpy scipy matplotlib "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"

import os
import sys
import datetime

from openmovement.load import MultiData
from openmovement.process import calc_svm

def run(source_file):
    ext = '.accel.csv'

    with MultiData(source_file, verbose=True, include_gyro=False, include_temperature=False) as data:
        samples = data.get_sample_values()
    
    svm_calc = calc_svm.calculate_svm(samples)
    
    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        writer.write("Time,Mean SVM (g)\n")
        for time, svm in svm_calc:
            time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ')[0:19]
            line = time_string + "," + str(svm)
            writer.write(line + "\n")

            print(line)


if __name__ == "__main__":
    source_files = None

    # Temporary default test file
    source_files = ['../_local/data/sample.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run(file)
