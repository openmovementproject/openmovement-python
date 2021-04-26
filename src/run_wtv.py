import os
import sys
import filename_info
from openmovement import timeseries_csv, calc_wtv

def run_wtv(source_file, test_load_everything=False):
    output_file = os.path.splitext(source_file)[0] + '.cwtv.csv'

    # (Experimental) Only use this option for scaled triaxial values with full timestamps
    if test_load_everything:
        import numpy as np
        data = timeseries_csv.csv_load_pandas(source_file)
        tscsv = iter(data)
    else:
        # Use the CSV iterator with automatic offset/scaling
        tscsv = timeseries_csv.TimeseriesCsv(source_file, {
            "time_zero": filename_info.csv_time_from_filename(source_file), 
            "global_scale": filename_info.csv_scale_from_filename(source_file)
        })

    wtv_calc = calc_wtv.CalcWtv(tscsv, {})
    
    with open(output_file, 'w') as writer:
        writer.write("Time,Wear time (30 mins)\n")
        feedback_time = None
        feedback_start = None
        for time, is_worn in wtv_calc:
            #time_dt = timeseries_csv.csv_datetime(time)
            time_string = timeseries_csv.csv_datetime_string(time, False)
            writer.write(time_string + "," + str(is_worn) + "\n")

            # Periodic feedback per hour
            if feedback_start is None or (time - feedback_time) >= 60 * 60:
                feedback_time = time
                if feedback_start is None:
                    feedback_start = feedback_time
                print('@' + str(int((time - feedback_start) / (60 * 60))) + 'h')


if __name__ == "__main__":
    source_files = None
    #source_files = ['../_local/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv']
    source_files = ['../_local/sample.csv']
    #source_files = ['../_local/mixed_wear.csv']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No .CSV files specified.')
    else:
        for file in source_files:
            run_wtv(file)
