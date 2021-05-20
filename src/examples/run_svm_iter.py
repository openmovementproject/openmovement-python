# --- HACK: Allow the example to run standalone as specified by a file in the repo (rather than only through the module)
if __name__ == '__main__' and __package__ is None:
    import sys; import os; sys.path.append(os.path.normpath(os.path.join(os.path.dirname(os.path.realpath(os.path.join(os.getcwd(), os.path.expanduser(__file__)))), '..')))
# ---

import os
import sys
import util_info_from_filename
from openmovement import cwa_load
from openmovement.iterator import timeseries_csv_iter, calc_svm_iter

def run_svm(source_file, test_load_everything=False):
    ext = '.csvm.csv'

    if os.path.splitext(source_file)[1].lower() == '.cwa':
        ext = '.cwa' + ext
        data = cwa_load.CwaData(source_file, verbose=True, include_gyro=False, include_temperature=False)
        row_iterator = iter(data)
    elif test_load_everything: # (Experimental) Only use this option for scaled triaxial values with full timestamps
        data = timeseries_csv_iter.csv_load_pandas(source_file)
        row_iterator = iter(data)
    else:
        # Use the CSV iterator with automatic time-offset/scaling
        row_iterator = timeseries_csv_iter.TimeseriesCsv(source_file, {
            "time_zero": util_info_from_filename.csv_time_from_filename(source_file), 
            "global_scale": util_info_from_filename.csv_scale_from_filename(source_file)
        })
    
    svm_calc = calc_svm_iter.CalcSvmIter(row_iterator, {})
    
    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        writer.write("Time,Mean SVM (g)\n")
        feedback_time = None
        feedback_start = None
        for time, svm in svm_calc:
            #time_dt = timeseries_csv_iter.csv_datetime(time)
            time_string = timeseries_csv_iter.csv_datetime_string(time)
            writer.write(time_string + "," + str(svm) + "\n")

            # Periodic feedback per hour
            if feedback_start is None or (time - feedback_time) >= 60 * 60:
                feedback_time = time
                if feedback_start is None:
                    feedback_start = feedback_time
                print('@' + str(int((time - feedback_start) / (60 * 60))) + 'h')


if __name__ == "__main__":
    source_files = None
    #source_files = ['../../_local/data/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv']
    #source_files = ['../../_local/data/sample.csv']
    source_files = ['../../_local/data/sample.cwa']
    #source_files = ['../../_local/data/mixed_wear.csv']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No .CSV files specified.')
    else:
        for file in source_files:
            run_svm(file)
