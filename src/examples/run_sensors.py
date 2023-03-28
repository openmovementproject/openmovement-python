# --- HACK: Allow the example to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

import os
import sys
import datetime

from openmovement.load import MultiData

def run_sensors(source_file):
    ext = '.sensors.csv'

    include_gyro = True
    with MultiData(source_file, verbose=True, include_gyro=include_gyro, include_light=True, include_temperature=True) as data:
        samples = data.get_sample_values()
   
    #print(samples)

    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        if include_gyro:
            writer.write("Time,AccelX,AccelY,AccelZ,GyroX,GyroY,GyroZ,Light,Temp\n")
            for time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, light, temp in samples:
                time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ', timespec='milliseconds')[0:23]
                line = time_string + "," + str(accel_x) + "," + str(accel_y) + "," + str(accel_z) + "," + str(gyro_x) + "," + str(gyro_y) + "," + str(gyro_z) + "," + str(light) + "," + str(temp)
                writer.write(line + "\n")
                print(line)
        else:
            writer.write("Time,AccelX,AccelY,AccelZ,Light,Temp\n")
            for time, accel_x, accel_y, accel_z, light, temp in samples:
                time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ', timespec='milliseconds')[0:23]
                line = time_string + "," + str(accel_x) + "," + str(accel_y) + "," + str(accel_z) + "," + str(light) + "," + str(temp)
                writer.write(line + "\n")
                print(line)


if __name__ == "__main__":
    source_files = None
    source_files = [
        './_local/data/AX6-Sample.cwa',
        #'./_local/data/sample.cwa',
    ]

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run_sensors(file)
