# python -m pip install "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"

# --- HACK: Allow the example to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

import os
import sys
import datetime

from openmovement.load import CwaData


def run_export_aux(source_file):
    print("READ: " + source_file)

    samples_per_sector = None
    with CwaData(source_file, include_gyro=False, include_light=True, include_temperature=True) as data:
        samples = data.get_sample_values()
        samples_per_sector = data.data_format['sampleCount']
   
    output_file = os.path.splitext(source_file)[0] + '.aux.csv'
    output_lines = 0
    with open(output_file, 'w') as writer:
        writer.write("Time,Light,Temp\n")
        # Skip to use one value from each data sector (rather than for each accelerometer sample)
        for index in range(0, samples.shape[0], samples_per_sector):
            value = samples[index] # time, accel_x, accel_y, accel_z, light, temp
            time_string = datetime.datetime.fromtimestamp(value[0], tz=datetime.timezone.utc).isoformat(sep=' ', timespec='milliseconds')[0:23]
            line = time_string + "," + str(value[4]) + "," + str(value[5])
            writer.write(line + "\n")
            output_lines += 1
    
    print("WROTE: " + str(output_lines) + " lines to " + output_file)


if __name__ == "__main__":
    source_files = None

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]
    
    if source_files is None or len(source_files) == 0:
        print('ERROR: No input file specified at command line.')
    else:
        for file in source_files:
            run_export_aux(file)
