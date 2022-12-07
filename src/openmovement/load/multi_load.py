"""
Timeseries data loader, for .CWA,.WAV,.CSV (directly or stored in a .ZIP file).
"""

import os

from openmovement.load.base_data import BaseData

from openmovement.load.csv_load import CsvData
from openmovement.load.cwa_load import CwaData
from openmovement.load.omx_load import OmxData
from openmovement.load.wav_load import WavData

from openmovement.load.zip_helper import PotentiallyZippedFile


class MultiData(BaseData):

    def __init__(self, filename, verbose=False, include_time=True, include_accel=True, include_gyro=True, include_mag=True, include_light=False, include_temperature=False, force_time=True, start_time=0, assumed_frequency=None, filters=['*.cwa', '*.omx', '*.wav', '*.csv']):
        """
        Construct a data object from a .CWA/.OMX/.WAV/.CSV file, or a .ZIP file containing one file from those formats.

        :param filename: The path to the file to open, it is extracted as required and memory-mapped.
        :param verbose: Output more detailed information.

        :param include_time: (.cwa/.omx/.wav) Interpolate timestamps for each row.
        :param include_accel: (.cwa/.omx/.wav) Include the three axes of accelerometer data.
        :param include_gyro: (.cwa/.omx/.wav) Include the three axes of gyroscope data, if they are present.
        :param include_mag: (.cwa/.omx/.wav - Not currently used) Include the three axes of magnetometer data, if they are present.

        :param include_light: (.cwa/.omx) Include the light indicator ADC readings, nearest-neighbor interpolated for each row.
        :param include_temperature: (.cwa/.omx) Include the internal temperature readings, nearest-neighbor interpolated for each row.

        :param force_time: (.csv) First column to be treated as time even if it doesn't look like an absolute timestamp and doesn't have a column header similar to 'time'.
        :param start_time: (.csv) Seconds since the epoch to use as an initial time to use for relative numeric (rather than absolute) timestamps, or where the time is missing.
        :param assumed_frequency: (.csv) Sampling frequency to assume if no timestamps are given.

        :param filter: (.zip file) Case-insensitive 'glob' string expressions to match the expected inner filename (default: ['*.cwa', '*.omx', '*.wav', '*.csv']).
        """
        super().__init__(filename, verbose)
        self.potentially_zipped_file = PotentiallyZippedFile(self.filename, filters=filters, verbose=self.verbose)
        try:
            self.inner_filename = self.potentially_zipped_file.__enter__()
        
            ext = os.path.splitext(self.inner_filename)[1].lower()
            if ext == '.cwa':
                self.inner_data = CwaData(self.inner_filename, verbose=self.verbose, include_time=include_time, include_accel=include_accel, include_gyro=include_gyro, include_mag=include_mag, include_light=include_light, include_temperature=include_temperature)
            elif ext == '.omx':
                self.inner_data = OmxData(self.inner_filename, verbose=self.verbose, include_time=include_time, include_accel=include_accel, include_gyro=include_gyro, include_mag=include_mag, include_light=include_light, include_temperature=include_temperature)
            elif ext == '.wav':
                self.inner_data = WavData(self.inner_filename, verbose=self.verbose, include_time=include_time, include_accel=include_accel, include_gyro=include_gyro, include_mag=include_mag)
            elif ext == '.csv':
                self.inner_data = CsvData(self.inner_filename, verbose=self.verbose, force_time=force_time, start_time=start_time, assumed_frequency=assumed_frequency)
            else:
                raise Exception('Unhandled file type: [' + ext + ']')

        except Exception as e:
            self.potentially_zipped_file.__exit__(None, None, None)
            raise e
        
    def close(self):
        try:
            if hasattr(self, 'inner_data') and self.inner_data is not None:
                self.inner_data.close()
                self.inner_data = None
        finally:
            if hasattr(self, 'potentially_zipped_file') and self.potentially_zipped_file is not None:
                self.potentially_zipped_file.__exit__(None, None, None)
                self.potentially_zipped_file = None

    def get_sample_values(self):
        return self.inner_data.get_sample_values()

    def get_samples(self, use_datetime64=True):
        return self.inner_data.get_samples(use_datetime64)

    def get_start_time(self):
        return self.inner_data.get_start_time()

    def get_sample_rate(self):
        return self.inner_data.get_sample_rate()

    def get_num_samples(self):
        return self.inner_data.get_num_samples()
    

def main():
    filename = '../_local/data/mixed_wear.cwa'

    with MultiData(filename, verbose=True) as data:
        sample_values = data.get_sample_values()
        samples = data.get_samples()
        
    print(sample_values)
    print(samples)
    print('Done')

if __name__ == "__main__":
    main()

