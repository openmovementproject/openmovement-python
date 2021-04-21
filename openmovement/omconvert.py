"""
Python wrapper for executing the omconvert binary (part of the Open Movement Project).

This processes .CWA and .OMX files, and can perform some operations on triaxial .WAV files; including:

* Export at a fixed sample rate to .CSV or .WAV

* Signal Vector Magnitude/Euclidean Norm Minus One

* "PAEE" cut-points categorizing epochs into a physical activity level.  A free choice of cut-points can be made, for example, levels from: 
  * Esliger, D. W., Rowlands, A. V., Hurst, T. L., Catt, M., Murray, P., & Eston, R. G. (2011). Validation of the GENEA Accelerometer.
  * Dillon, C. B., Fitzgerald, A. P., Kearney, P. M., Perry, I. J., Rennie, K. L., Kozarski, R., & Phillips, C. M. (2016). Number of days required to estimate habitual activity using wrist-worn GENEActiv accelerometer: a cross-sectional study. PloS one, 11(5), e0109913.
  * Powell, C., Carson, B. P., Dowd, K. P., & Donnelly, A. E. (2017). Simultaneous validation of five activity monitors for use in adult populations. Scandinavian journal of medicine & science in sports, 27(12), 1881-1892.

* Wear-time validation, an implementation of the algorithm described in:
  * van Hees, V. T., Renström, F., Wright, A., Gradmark, A., Catt, M., Chen, K. Y., ... & Franks, P. W. (2011). Estimation of daily energy expenditure in pregnant and non-pregnant women using a wrist-worn tri-axial accelerometer. PloS one, 6(7), e22922.

* (Not recommended) Step counts, an implementation of the algorithm described in:
  * Cho, Y., Cho, H., & Kyung, C. M. (2016). Design and implementation of practical step detection algorithm for wrist-worn devices. IEEE Sensors Journal, 16(21), 7720-7730.

* (Not recommended) Sleep, an implementation of the algorithm described in:
  * Borazio, M., Berlin, E., Kücükyildiz, N., Scholl, P., & Van Laerhoven, K. (2014, September). Towards benchmarked sleep detection with wrist-worn sensing units. In 2014 IEEE International Conference on Healthcare Informatics (pp. 125-134). IEEE.

* AG-Counts, an implementation of the algorithm described in:
  *  Brønd, J. C., Andersen, L. B., & Arvidsson, D. (2017). Generating ActiGraph counts from raw acceleration recorded by an alternative monitor.
"""

import os
import subprocess
import tempfile
import uuid
import datetime

class OmConvert:
    """An implementation of the analysis functions using the external binary executable 'omconvert'."""

    @staticmethod
    def locate_executable(executable_name = None):
        # Default
        if executable_name == None:
            executable_name = 'omconvert'

        # Search OS 'PATH'
        search_path = os.environ["PATH"].split(os.pathsep)

        # Prefer file in current working directory
        search_path.insert(0, os.getcwd())

        # Prefer binary co-located with source file
        search_path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # Prefer binary in 'bin' folder in parent folder of source file
        search_path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../bin'))

        # Prefer a full path if specified
        parts = os.path.split(executable_name)
        executable_name = parts[1]
        if parts[0]  != '':
            search_path.insert(0, parts[0])

        # If on Windows, append .exe and search in a default installation location (as a last resort)
        if (os.name == 'nt'):
            if os.path.splitext(executable_name)[1] == '':
                executable_name = executable_name + '.exe'
            search_path.append(os.path.expandvars('%PROGRAMFILES(x86)%\Open Movement\OM GUI\Plugins\OmConvertPlugin'))

        # Search in locations
        for path in search_path:
            filename = os.path.join(path, executable_name)
            if os.path.isfile(filename):
                if not os.access(filename, os.X_OK):
                    raise FileNotFoundError('Binary file exists but is not executable, consider:  chmod +x ' + filename)
                return filename

        return None


    def __init__(self):
        pass

    def execute(self, source_file, options):
        """
        Options:
            "resample": 0,                  # resample frequency (not specified uses the configured rate)
            "interpolate_mode": 3,          # 1=nearest, 2=linear, 3=cubic
            "header_csv": 1,                # 0=none, 1=header in first row
            "time": 0,                      # 0=date/time, 1=UNIX epoch
            "calibrate": 1,                 # 0=off, 1=auto

            "csv_file": "file.csv",         # output resampled data to CSV

            "svm_file": "file.svm.csv",     # SVM analysis output
            "svm_epoch": 60,                # SVM analysis epoch period (seconds)
            "svm_filter": 1,                # SVM analysis filter (0=off, 1=BP 0.5-20 Hz)
            "svm_mode": 0,                  # SVM analysis mode (0=abs(SVM-1), 1=max(SVM-1, 0), 2=SVM-1)

            "wtv_file": "file.svm.csv",     # WTV analysis output
            "wtv_epoch": 1,                 # WTV analysis epochs of 30-minute windows

            "paee_file": "file.paee.csv",   # PAEE analysis
            "paee_model": "wrist",          # PAEE analysis cut-point values (see 'Cut-point thresholds strings')
            "paee_epoch": 1,                # PAEE analysis count of 1-minute epochs
            "paee_filter": 1,               # PAEE analysis filter (0=off, 1=BP 0.5-20 Hz)

            "counts_file": "file.svm.csv",  # WTV analysis output
            "counts_epoch": 1,              # WTV analysis epochs of 30-minute windows
        """

        executable = self.locate_executable(options.get('executable'))
        if executable is None:
            raise FileNotFoundError('omconvert executable not found: specify "executable" option or place binary in path or working directory. For build instructions, see: https://github.com/digitalinteraction/omconvert/') 
        
        result = {}
        print('OMCONVERT: Using executable: ' + executable)

        parameters = [
            executable,
            source_file,
        ]

        # Key/value options
        for key, value in options.items():
            if key == 'executable':
                continue
            parameters.append('-' + key.replace('_', '-'))
            if value is not None:
                parameters.append(str(value))

        # Use an info file to get detailed output of the process
        info_file = os.path.join(tempfile.gettempdir(), str(uuid.uuid4()) + '.yml')
        parameters.append('-info')
        parameters.append(info_file)

        try:
            # Execute the external binary
            completed_process = subprocess.run(parameters)
            result['returncode'] = completed_process.returncode

            # Non-zero return code on failure
            if result['returncode'] != 0:
                raise RuntimeError('Conversion failed: ' + str(result['returncode']))

            # Zero return codes should have an info file
            if not os.path.isfile(info_file):
                raise RuntimeError('Expected info file not found')

            # Read and parse the info file
            with open(info_file, 'r') as info_file_handle:
                info_file_content = info_file_handle.read().splitlines()
            
            for line in info_file_content:
                line = line.strip()
                if line == '' or line.startswith('#'):
                    continue
                parts = line.split(':', 1)
                key = parts[0].strip()
                value = None
                if len(parts) > 1:
                    value = parts[1].strip()
                if value.isdigit() or (len(value) > 2 and value[0] == '-' and value[1:].isdigit()):
                    value = int(value, 10)
                if key == 'Processed':
                    # This is in local timezone
                    value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f')
                if key == 'Start' or key == 'Stop' or key == 'Time' or key == 'ClearTime' or key == 'ChangeTime':
                    # Is in no defined timezone
                    value = datetime.datetime.strptime(value, '%Y-%m-%d %H:%M:%S.%f').replace(tzinfo=None)  # datetime.timezone.utc

                # Ignore keys that change on each run
                if key == 'Processed' or key == 'Results-output':
                    continue

                result[key] = value

        finally:
            try:
                os.remove(info_file)
            except OSError:
                # It's OK if it can't be removed (e.g. if it doesn't exist)
                pass

        print('...done')
        return result


# Cut-point thresholds strings:
#
#   "'wrist':                386/80/60 542/80/60 1811/80/60"
#   "Esliger(40-63)-wristR:  386/80/60 440/80/60 2099/80/60"
#   "Esliger(40-63)-wristL:  217/80/60 645/80/60 1811/80/60"
#   "Esliger(40-63)-waist:   77/80/60 220/80/60 2057/80/60"
#   "Schaefer(6-11)-wristND: 0.190 0.314 0.998"
#   "Phillips(8-14)-wristR:  6/80 22/80 56/80"
#   "Phillips(8-14)-wristL:  7/80 20/80 60/80"
#   "Phillips(8-14)-hip:     3/80 17/80 51/80"
#   "Roscoe(4-5)-wristND:    5.3/87.5 8.6/87.5"
#   "Roscoe(4-5)-wristD:     8.1/87.5 9.3/87.5"
#   "Dillon-wristD:          191.8/100/15 281.6/100/15 595/100/15"
#   "Dillon-wristND:         158.5/100/15 261.9/100/15 495/100/15"
#   "Dillon-wristD (2016) same as Dillon-wristD (2015): 230/30/60 338/30/60 714/30/60"
#   "Dillon-wristND (2016) same as Dillon-wristND (2015): 190/30/60 314/30/60 594/30/60"
#   "Powell-wristD:          51/30/15 68/30/15 142/30/15"
#   "Powell-wristND:         47/30/15 64/30/15 157/30/15"
