"""
Python wrapper for executing the omsynth binary (part of the Open Movement Project).

This is intended for producing data files for testing, and is not recommended for any other purpose.

Input CSV has optional header line:

  Time,Accel-X (g), Accel-Y (g), Accel-Z (g)

...and data lines of:

  T,Ax,Ay,Az

...where T is a timestamp in the format YYYY-MM-DD hh:mm:ss.fff, Ax/Ay/Az are the accelerometer axes in units of g.
"""

import os
import subprocess
import tempfile
import uuid
import datetime

class OmSynth:
    """An implementation of the analysis functions using the external binary executable 'omsynth'."""

    @staticmethod
    def locate_executable(executable_name = None):
        # Default
        if executable_name == None:
            executable_name = 'omsynth'

        # Search OS 'PATH'
        search_path = os.environ["PATH"].split(os.pathsep)

        # Prefer file in current working directory
        search_path.insert(0, os.getcwd())

        # Prefer binary in 'bin' folder in parent folder of source file
        search_path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../bin'))
        
        # Prefer binary co-located with source file
        search_path.insert(0, os.path.dirname(os.path.abspath(__file__)))

        # Prefer a full path if specified
        parts = os.path.split(executable_name)
        executable_name = parts[1]
        if parts[0]  != '':
            search_path.insert(0, parts[0])

        # If on Windows, append .exe
        if (os.name == 'nt'):
            if os.path.splitext(executable_name)[1] == '':
                executable_name = executable_name + '.exe'

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

    def execute(self, source_file, out_file, options):
        """
        Options:
            "unpacked", None                # use unpacked format (the default)
            "packed", None                  # use packed format (default is unpacked)
            "scale": 1,                     # global scaling to apply to data
            "rate": 100,                    # Configured sampling rate in Hz (default=100; sector-rate from data)
            "range": 8,                     # +/- 2/4/8/16 g sensor range
            "silent", None                  # less verbose output
            "gyro": -1,                     # none/-1=AX3 (default); off/0=AX6 accel-only mode; 125/250/500/1000/2000 degrees/second
        """

        executable = self.locate_executable(options.get('executable'))
        if executable is None:
            raise FileNotFoundError('omsynth executable not found: specify "executable" option or place binary in path or working directory. For build instructions, see: https://github.com/digitalinteraction/omsynth/') 
        
        result = {}
        print('OMSYNTH: Using executable: ' + executable)

        parameters = [
            executable,
            source_file,
            '-out',
            out_file,
        ]

        # Key/value options
        for key, value in options.items():
            if key == 'executable':
                continue
            parameters.append('-' + key.replace('_', '-'))
            if value is not None:
                parameters.append(str(value))

        # Execute the external binary
        completed_process = subprocess.run(parameters)
        result['returncode'] = completed_process.returncode

        # Non-zero return code on failure
        if result['returncode'] != 0:
            raise RuntimeError('Synthesis failed: ' + str(result['returncode']))

        print('...done')
        return result

