# --- HACK: Allow the example to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

## This is experimental code to verify the timestamp values.

import os
import sys
import datetime

from openmovement.load import CwaData

def run_timestamps(source_file):
    ext = '.timestamps.csv'

    with CwaData(source_file, verbose=False, include_gyro=False, include_light=True, include_temperature=True, diagnostic=True) as data:
        samples = data.get_sample_values()
    
    #print(samples)

    limit_index = 0
    delta_threshold = 0.1
    index = 0
    previous_time = 0
    previous_over_threshold_index = -1;
    jump_delta_sum = 0
    jump_delta_count = 0

    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        writer.write("Index,Time,Delta\n")
        for time, _, _, _, _, _ in samples:
            if limit_index and index >= limit_index:
                break
            if previous_time == 0:
                delta = 0
            else:
                delta = time - previous_time
            #time_string = datetime.datetime.fromtimestamp(time, tz=datetime.timezone.utc).isoformat(sep=' ')[0:23]
            line = str(index) + "," + str(time) + "," + str(delta)
            writer.write(line + "\n")
            if delta > delta_threshold:
                if previous_over_threshold_index >= 0:
                    jump_delta = index - previous_over_threshold_index
                    jump_delta_sum += jump_delta
                    jump_delta_count += 1
                    print(line + ' -- ' + str(jump_delta) + '')
                else:
                    print(line)
                previous_over_threshold_index = index
            previous_time = time
            index += 1

    if jump_delta_count > 0:
        print('Average jump delta: ' + str(jump_delta_sum / jump_delta_count))


if __name__ == "__main__":
    source_files = None
    source_files = ['../_local/data/sample.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run_timestamps(file)
