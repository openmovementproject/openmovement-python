# python -m pip install -e "git+https://github.com/digitalinteraction/openmovement-python.git#egg=openmovement"

import sys
#sys.path.append(".")

import os
from openmovement import omconvert

def run_omconvert(source_file):
    options = {}

    # Base path and file name without extension
    base_name = os.path.splitext(source_file)[0]
    suffix = ''

    #options['executable'] = '/path/to/omconvert'

    options['interpolate_mode'] = 1     # nearest-point sampling

    # Export accelerometer CSV file (can take a long time)
    #options['csv_file'] = base_name + suffix + '.csv'

    # SVM (no filter)
    options['svm_filter'] = 0
    options['svm_file'] = base_name + suffix + '.svm.csv'

    # Wear-time validation
    options['wtv_file'] = base_name + suffix + '.wtv.csv'

    # "PAEE" Cut-points (no filter)
    #options['paee_filter'] = 0
    #options['paee_file'] = base_name + suffix + '.paee.csv'

    om = omconvert.OmConvert()
    result = om.execute(source_file, options)

    # for key, value in result.items():
    #     print('RESULT: ' + key + ' == ' + str(value))


if __name__ == "__main__":
    source_files = None
    #source_files = ['../_local/sample.cwa']
    #source_files = ['../_local/mixed_wear.cwa']

    if len(sys.argv) > 1:
        source_files = sys.argv[1:]

    if source_files is None or len(source_files) == 0:
        print('No .CWA files specified.')
    else:
        for file in source_files:
            run_omconvert(file)
