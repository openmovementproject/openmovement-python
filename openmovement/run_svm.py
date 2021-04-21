import os
import timeseries_csv
from calc_svm import CalcSvm

def run_svm(source_file, test_load_everything=False):
    output_file = os.path.splitext(source_file)[0] + '.csvm.csv'

    # (Experimental) Only use this option for scaled triaxial values with full timestamps
    if test_load_everything:
        import numpy as np
        data = timeseries_csv.csv_load_pandas(source_file)
        tscsv = iter(data)
    else:
        # Use the CSV iterator with automatic time-offset/scaling
        tscsv = timeseries_csv.TimeseriesCsv(source_file, {
            "time_zero": timeseries_csv.csv_time_from_filename(source_file), 
            "global_scale": timeseries_csv.csv_scale_from_filename(source_file)
        })
    #print(tscsv.header)
    svm_calc = CalcSvm(tscsv, {})
    
    with open(output_file, 'w') as writer:
        writer.write("Time,Mean SVM (g)\n")
        feedback_time = None
        feedback_start = None
        for time, svm in svm_calc:
            #time_dt = timeseries_csv.csv_datetime(time)
            time_string = timeseries_csv.csv_datetime_string(time, False)
            writer.write(time_string + "," + str(svm) + "\n")

            # Periodic feedback per hour
            if feedback_start is None or (time - feedback_time) >= 60 * 60:
                feedback_time = time
                if feedback_start is None:
                    feedback_start = feedback_time
                print('@' + str(int((time - feedback_start) / (60 * 60))) + 'h')


# Test version
if __name__ == "__main__":
    #source_file = '../_local/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv'
    source_file = '../_local/sample.csv'
    #source_file = '../_local/mixed_wear.csv'
    run_svm(source_file)
