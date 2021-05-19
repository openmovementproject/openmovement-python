import os
import sys
from openmovement import timeseries_csv, cwa_load, calc_wtv

def run_wtv(source_file):
    ext = '.cwtv.csv'

    if os.path.splitext(source_file)[1].lower() == '.cwa':
        ext = '.cwa' + ext
        cwa_data = cwa_load.CwaData(source_file, verbose=True, include_gyro=False, include_temperature=False)
        data = cwa_data.get_sample_values()
    else: # Only use this option for scaled triaxial values with full timestamps
        data = timeseries_csv.csv_load_pandas(source_file)
    
    wtv_calc = calc_wtv.calculate_wtv(data)
    
    output_file = os.path.splitext(source_file)[0] + ext
    with open(output_file, 'w') as writer:
        writer.write("Time,Wear time (30 mins)\n")
        for time, wtv in wtv_calc:
            #time_dt = timeseries_csv.csv_datetime(time)
            time_string = timeseries_csv.csv_datetime_string(time)
            line = time_string + "," + str(int(wtv))
            writer.write(line + "\n")

            print(line)


if __name__ == "__main__":
    source_files = None
    #source_files = ['../_local/2021-04-01-123456123_XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX_ACC.csv']
    source_files = ['../_local/sample.csv']
    #source_files = ['../_local/sample.cwa']
    #source_files = ['../_local/mixed_wear.csv']
    #source_files = ['../_local/mixed_wear.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No input file specified.')
    else:
        for file in source_files:
            run_wtv(file)
