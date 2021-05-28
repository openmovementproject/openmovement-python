# Open Movement WAV File Loader
# Dan Jackson

import datetime
from struct import *
import re

import numpy as np
import pandas as pd

from openmovement.load.base_data import BaseData

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_IEEE_FLOAT = 0x0003
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

def _parse_wav_info(buffer):
    """
    Parse a WAV file chunks to determine the data offset, type and metadata.
    """
    wav_info = {}

    # Empty metadata
    wav_info['name'] = None
    wav_info['artist'] = None
    wav_info['comment'] = None
    wav_info['creation'] = None

    if len(buffer) < 28:
        raise Exception('Too small to be a valid WAV file')

    (riff, riff_size, wave) = unpack('<4sI4s', buffer[0:12])
    if riff != b'RIFF':
        raise Exception('RIFF header not found')

    if riff_size + 8 != len(buffer):
        print('WARNING: RIFF size is not as expected from file length')

    if wave != b'WAVE':
        raise Exception('WAVE header not found')

    # Read each chunk
    ofs = 12
    while ofs < riff_size and ofs + 8 < riff_size:
        (chunk, chunk_size) = unpack('<4sI', buffer[ofs+0:ofs+8])

        if chunk[0] < 32 | chunk[0] >= 127 | chunk[1] < 32 | chunk[1] >= 127 | chunk[2] < 32 | chunk[2] >= 127 | chunk[3] < 32 | chunk[3] >= 127:
            raise Exception('Seemingly invalid chunk type')

        if ofs + chunk_size > riff_size:
            raise Exception('Chunk size is invalid: ' + str(chunk_size))

        if chunk == b'fmt ':
            if chunk_size < 16:
                raise Exception('fmt chunk too small for WAVEFORMATEX')

            (format_tag, num_channels, samples_per_sec, avg_bytes_per_sec, block_align, bits_per_sample) = unpack('<HHIIHH', buffer[ofs+8:ofs+8+16])

            cb_size = 0
            if chunk_size >= 18:
                (cb_size,) = unpack('<H', buffer[ofs+8+16:ofs+8+16+2])
                if 18 + cb_size != chunk_size:
                    print('WARNING: fmt chunk size is not consistent with cbSize.')
            
            if format_tag != WAVE_FORMAT_EXTENSIBLE and chunk_size != 16 and chunk_size != 18:
                print('WARNING: fmt chunk size is not an expected length for PCM data (16 or 18 bytes).')

            if format_tag == WAVE_FORMAT_EXTENSIBLE and chunk_size != 40:
                print('WARNING: fmt chunk size is not an expected length for WAVE_FORMAT_EXTENSIBLE PCM data (40 bytes).')

            format_tag_original = format_tag
            if format_tag == WAVE_FORMAT_EXTENSIBLE and cb_size >= 22 and chunk_size >= 40:
                (valid_bits_per_sample, channel_mask, guid) = unpack('<HI16s', buffer[ofs+8+18:ofs+8+18+22])
                if guid[2:16] != b'\x00\x00\x00\x00\x10\x00\x80\x00\x00\xAA\x00\x38\x9B\x71':
                    raise Exception('GUID is not WAVE_FORMAT_EXTENSIBLE')
                (format_tag,) = unpack('<H', guid[0:2])

            # Check format
            wav_info['format'] = format_tag

            if bits_per_sample & 0x7 != 0:
                print('WARNING: Bits-per-sample is not a whole number of bytes -- rounding up to nearest byte.')

            if block_align != (num_channels * ((bits_per_sample + 7) >> 3)):
                print('WARNING: Block alignment is not the expected number for the given number of channels and bytes per sample.')

            if avg_bytes_per_sec != samples_per_sec * block_align:
                print('WARNING: Average bytes per second is not the expected number for the frequency, channels and bytes-per-sample.')

            # Set output values
            wav_info['bytes_per_channel'] = (bits_per_sample + 7) >> 3
            wav_info['num_channels'] = num_channels
            wav_info['frequency'] = samples_per_sec

        elif chunk == b'data':
            wav_info['data_offset'] = ofs + 8
            wav_info['data_size'] = chunk_size

        elif chunk == b'LIST':
            (list_type,) = unpack('<4s', buffer[ofs+8:ofs+12])

            if list_type == b'INFO':
                list_ofs = ofs + 12

                while list_ofs < ofs + chunk_size + 8:
                    (sub_chunk, sub_chunk_size) = unpack('<4sI', buffer[list_ofs+0:list_ofs+8])

                    if list_ofs + sub_chunk_size + 8 > ofs + 8 + chunk_size:
                        raise Exception('List Sub-chunk size is invalid: ' + str(sub_chunk_size))

                    info_type = None
                    if sub_chunk == b'INAM': info_type = 'name'         # Track Title
                    if sub_chunk == b'IART': info_type = 'artist'       # Artist Name
                    if sub_chunk == b'ICMT': info_type = 'comment'      # Comments
                    if sub_chunk == b'ICRD': info_type = 'creation'     # Creation Date
                    
                    if info_type is not None:
                        # Remove any trailing null bytes
                        text = buffer[list_ofs + 8 : list_ofs + 8 + sub_chunk_size].rstrip(b'\x00')
                        wav_info[info_type] = text
                        #print('LIST-INFO: ' + info_type + ' == ' + wav_info[info_type])

                    else:
                        print('WARNING: Unknown list-info type: ' + str(sub_chunk))

                    list_ofs += sub_chunk_size + 8

            else:
                print('WARNING: Unknown list type: ' + str(list_type))
                pass

        elif chunk == b'JUNK' or chunk == b'fact' or chunk == b'PEAK':
            pass

        else:
            print('WARNING: Unknown chunk type: ' + str(chunk))
            pass

        
        ofs += chunk_size + 8
    
    if 'frequency' not in wav_info or 'num_channels' not in wav_info or 'bytes_per_channel' not in wav_info:
        raise Exception('Valid format not found')
    
    if 'data_offset' not in wav_info or 'data_size' not in wav_info:
        raise Exception('Data not found')

    return wav_info


def _decode_comment(comment):
    result = {}
    entries = []
    if comment is not None:
        entries = comment.decode('ascii').split('\n')
    for entry in entries:
        parts = entry.split(':', 1)
        name = parts[0].strip(' ')
        if len(name) > 0:
            value = None
            if len(parts) > 1:
                value = parts[1].strip(' ')
            result[name] = value
    return result


def _parse_accel_info(wav_info):
    info = {}

    # General format checks
    if wav_info['num_channels'] <= 0:
        raise Exception('No channels found')
    if wav_info['frequency'] <= 0 or wav_info['frequency'] > 65535:
        raise Exception('Invalid frequency')
    if wav_info['bytes_per_channel'] <= 0:
        raise Exception('No data per sample')

    format = None
    global_range = 1
    global_offset = 0
    if wav_info['format'] == WAVE_FORMAT_PCM and wav_info['bytes_per_channel'] == 1:
        format = 'B'    # Unsigned 8-bit integer
        global_offset = -128
        global_range = 1 << 7
    elif wav_info['format'] == WAVE_FORMAT_PCM and wav_info['bytes_per_channel'] == 2:
        format = 'h'    # Signed 16-bit integer
        global_range = 1 << 15
    elif wav_info['format'] == WAVE_FORMAT_PCM and wav_info['bytes_per_channel'] == 4:
        format = 'i'    # Signed 32-bit integer
        global_range = 1 << 31
    elif wav_info['format'] == WAVE_FORMAT_PCM and wav_info['bytes_per_channel'] == 8:
        format = 'q'    # Signed 64-bit integer
        global_range = 1 << 63
    elif wav_info['format'] == WAVE_FORMAT_IEEE_FLOAT and wav_info['bytes_per_channel'] == 2:
        format = 'e'    # 16-bit float
    elif wav_info['format'] == WAVE_FORMAT_IEEE_FLOAT and wav_info['bytes_per_channel'] == 4:
        format = 'f'    # 32-bit float
    elif wav_info['format'] == WAVE_FORMAT_IEEE_FLOAT and wav_info['bytes_per_channel'] == 8:
        format = 'd'    # 64-bit double-precision float

    if format is None:        
        raise Exception('Unrecognized data storage format')
    info['format'] = format
    info['global_range'] = global_range
    info['global_offset'] = global_offset
    
    # Data offset / size (bytes) directly from WAV file
    info['data_offset'] = wav_info['data_offset']
    info['data_size'] = wav_info['data_size']

    # Frequency / channels directly from WAV file
    info['frequency'] = wav_info['frequency']
    info['num_channels'] = wav_info['num_channels']

    # Number of samples
    info['channel_span'] = wav_info['bytes_per_channel']
    info['sample_span'] = info['num_channels'] * info['channel_span']
    info['num_samples'] = info['data_size'] // info['sample_span']

    ## Find time-offset from creation date (timestamp of first sample)
    info['time_offset'] = 0
    info['time_offset_datetime'] = None
    if wav_info['creation'] is not None:
        try:
            info['time_offset_datetime'] = datetime.datetime.fromisoformat(wav_info['creation'].decode('ascii') + '+00:00')
            info['time_offset'] = info['time_offset_datetime'].timestamp()
        except Exception as e:
            print('WARNING: Problem parsing timestamp: ' + str(wav_info['creation']) + ' -- ' + str(e))

    # (INAM) name: Track title (data about the recording itself)
    info['recording'] = _decode_comment(wav_info['name'])
    
    # (IART) artist: Artist name (data about the device that made the recording)
    info['device'] = _decode_comment(wav_info['artist'])

    # (ICMT) comment: Comments (data about this file representation)
    info['representation'] = _decode_comment(wav_info['comment'])

    # Empty axis allocation and scaling
    info['scale'] = [1] * info['num_channels']
    info['sensor'] = [None] * info['num_channels']
    info['axis'] = [None] * info['num_channels']

    # Decode channel sensor/axis assignment
    for channel in range(0, info['num_channels']):
        tag_channel = 'Channel-' + str(channel + 1)
        if tag_channel in info['representation']:
            channel_name = info['representation'][tag_channel]
            parts = channel_name.split('-', 1)
            info['sensor'][channel] = parts[0]
            if len(parts) > 1:
                axis = parts[1]
                if len(axis) == 1 and ord(axis[0]) >= ord('X') and ord(axis[0]) <= ord('Z'):
                    axis = ord(axis[0]) - ord('X')
                info['axis'][channel] = axis
            
    # Decode channel scaling
    for channel in range(0, info['num_channels']):
        tag_scale = 'Scale-' + str(channel + 1)
        if tag_scale in info['representation']:
            scale_value = float(info['representation'][tag_scale])
            info['scale'][channel] = scale_value

    # Find sensor axis index
    info['accel_axis'] = None
    info['accel_scale'] = None
    info['gyro_axis'] = None
    info['gyro_scale'] = None
    info['mag_axis'] = None
    info['mag_scale'] = None
    info['aux_axis'] = None
    for channel in range(0, info['num_channels']):
        if info['sensor'][channel] == 'Aux':
            info['aux_axis'] = channel
        if info['axis'][channel] == 0:
            tag = info['sensor'][channel].lower() + '_axis'
            info[tag] = channel

    # Check triaxial and contiguous
    if info['accel_axis'] is not None:
        channel = info['accel_axis']
        info['accel_scale'] = info['scale'][channel]
        if channel + 3 > info['num_channels'] or info['sensor'][channel + 1] != info['sensor'][channel] or info['sensor'][channel + 2] != info['sensor'][channel] or info['axis'][channel + 1] != 1 or info['axis'][channel + 2] != 2 or info['scale'][channel + 1] != info['scale'][channel] or info['scale'][channel + 2] != info['scale'][channel]:
            raise Exception('Accel channels are not triaxial/contiguous/same-scaled')
    if info['gyro_axis'] is not None:
        channel = info['gyro_axis']
        info['gyro_scale'] = info['scale'][channel]
        if channel + 3 > info['num_channels'] or info['sensor'][channel + 1] != info['sensor'][channel] or info['sensor'][channel + 2] != info['sensor'][channel] or info['axis'][channel + 1] != 1 or info['axis'][channel + 2] != 2 or info['scale'][channel + 1] != info['scale'][channel] or info['scale'][channel + 2] != info['scale'][channel]:
            raise Exception('Gyro channels are not triaxial/contiguous/same-scaled')
    if info['mag_axis'] is not None:
        channel = info['mag_axis']
        info['mag_scale'] = info['scale'][channel]
        if channel + 3 > info['num_channels'] or info['sensor'][channel + 1] != info['sensor'][channel] or info['sensor'][channel + 2] != info['sensor'][channel] or info['axis'][channel + 1] != 1 or info['axis'][channel + 2] != 2 or info['scale'][channel + 1] != info['scale'][channel] or info['scale'][channel + 2] != info['scale'][channel]:
            raise Exception('Mag channels are not triaxial/contiguous/same-scaled')

    # Assign aux channel if not already allocated
    if info['aux_axis'] is None:
        last_channel = info['num_channels'] - 1
        if info['sensor'][last_channel] is None:
            info['aux_axis'] = last_channel

    return info


class WavData(BaseData):
    """
    WAV file loader
    """

    def _read_data(self):
        if self.verbose: print('Opening WAV file...', flush=True)
        self.fh = open(self.filename, 'rb')
        try:
            import mmap
            self.full_buffer = mmap.mmap(self.fh.fileno(), 0, access=mmap.ACCESS_READ)
            if self.verbose: print('...mapped ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)
        except Exception as e:
            print('WARNING: Problem using mmap (' + str(e) +') - falling back to reading whole file...', flush=True)
            self.full_buffer = self.fh.read()
            if self.verbose: print('...read ' + str(len(self.full_buffer) / 1024 / 1024) + 'MB', flush=True)


    def _parse_header(self):
        if self.verbose: print('Parsing WAV info...', flush=True)
        self.wav_info = _parse_wav_info(self.full_buffer)
        self.info = _parse_accel_info(self.wav_info)


    def _interpret_samples(self):
        raw_samples = np.frombuffer(self.full_buffer, dtype='<'+self.info['format'], offset=self.info['data_offset'], count=self.info['num_samples'] * self.info['num_channels'])
        raw_samples = raw_samples.reshape(-1, self.info['num_channels'])
        self.raw_samples = raw_samples
        
        # Raw data needs scaling by  info['accel_scale']/info['global_range']  or info['gyro_scale']/info['global_range']

        # Which sensors?
        has_accel = self.include_accel and self.info['accel_axis'] is not None
        has_gyro = self.include_gyro and self.info['gyro_axis'] is not None
        has_mag = self.include_mag and self.info['mag_axis'] is not None
        
        # Calculate dimensions
        axis_count = 0  # time
        if self.include_time: axis_count += 1
        if has_accel: axis_count += 3
        if has_gyro: axis_count += 3
        if has_mag: axis_count += 3
        self.labels = []

        if self.verbose: print('Create output...', flush=True)
        self.sample_values = np.ndarray(shape=(self.raw_samples.shape[0], axis_count))
        current_axis = 0

        if self.include_time:
            # Create time from timestamp offset and frequency
            if self.verbose: print('Timestamp create...', flush=True)
            time_start = self.info['time_offset']
            time_stop = time_start + (self.info['num_samples'] / self.info['frequency'])
            self.sample_values[:,current_axis] = np.linspace(time_start, time_stop, endpoint=False, num=self.info['num_samples'])
            self.labels = self.labels + ['time']
            current_axis += 1

        if has_accel:
            if self.verbose: print('Sample data: scaling accel... ' + str(self.info['accel_scale']), flush=True)
            self.sample_values[:,current_axis:current_axis+3] = (self.raw_samples[:, self.info['accel_axis']:self.info['accel_axis']+3] + self.info['global_offset']) / self.info['global_range'] * self.info['accel_scale']
            self.labels = self.labels + ['accel_x', 'accel_y', 'accel_z']
            current_axis += 3

        if has_gyro:
            if self.verbose: print('Sample data: scaling gyro... ' + str(self.info['gyro_scale']), flush=True)
            self.sample_values[:,current_axis:current_axis+3] = (self.raw_samples[:, self.info['gyro_axis']:self.info['gyro_axis']+3] + self.info['global_offset']) / self.info['global_range'] * self.info['gyro_scale'] 
            self.labels = self.labels + ['gyro_x', 'gyro_y', 'gyro_z']
            current_axis += 3

        if has_mag:
            if self.verbose: print('Sample data: scaling mag... ' + str(self.info['mag_scale']), flush=True)
            self.sample_values[:,current_axis:current_axis+3] = (self.raw_samples[:, self.info['mag_axis']:self.info['mag_axis']+3] + self.info['global_offset']) / self.info['global_range'] * self.info['mag_scale']
            self.labels = self.labels + ['mag_x', 'mag_y', 'mag_z']
            current_axis += 3

        del self.raw_samples
        self.samples = None
        if self.verbose: print('Interpreted data', flush=True)
        
        if current_axis != axis_count:
            raise Exception('Internal error: not all output axes accounted for')


    def __init__(self, filename, verbose=False, include_time=True, include_accel=True, include_gyro=True, include_mag=True):
        """
        Construct a timeseries movement data object from a multi-channel .WAV file (with metadata for channel scaling).

        :param filename: The path to the multi-channel .WAV file.
        :param verbose: Output more detailed information.
        :param include_time: Generate timestamps for each row.
        :param include_accel: Include the three axes of accelerometer data.
        :param include_gyro: Include the three axes of gyroscope data, if they are present.
        :param include_mag: (Not currently used) Include the three axes of magnetometer data, if they are present.
        """
        super().__init__(filename, verbose)

        self.include_time = include_time
        self.include_accel = include_accel
        self.include_gyro = include_gyro
        self.include_mag = include_mag

        self.fh = None
        self.full_buffer = None

        self.all_data_read = False
        self._read_data()
        self._parse_header()


    # Current model interprets all of the data in one go (and releases the file)
    def _ensure_all_data_read(self):
        if self.all_data_read:
            return
        self.all_data_read = True
        self._interpret_samples()
        self.close()

    def close(self):
        """Close the underlying file.  Automatically closed in with() block or when GC'd."""
        if hasattr(self, 'full_buffer') and self.full_buffer is not None:
            # Close if a mmap()
            if hasattr(self.full_buffer, 'close'):
                self.full_buffer.close()
            # Delete buffer (if large allocation not using mmap)
            del self.full_buffer
            self.full_buffer = None
        if hasattr(self, 'fh') and self.fh is not None:
            self.fh.close()
            self.fh = None

    def get_sample_values(self):
        """
        Get the sample values as a single ndarray.

        :returns: An ndarray of (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)
                  where 'time' is in seconds since the epoch.
        """
        self._ensure_all_data_read()
        return self.sample_values

    def get_samples(self, use_datetime64=True):
        """
        Return an DataFrame for (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)

        :param use_datetime64: (Default) time is in datetime64[ns]; otherwise in seconds since the epoch.
        """
        self._ensure_all_data_read()
        if self.include_time and use_datetime64:
            if self.verbose: print('Converting time...', flush=True)
            # Samples exclude the current time (float seconds) column
            samples = pd.DataFrame(self.sample_values[:,1:], columns=self.labels[1:])
            # Convert the float epoch time in seconds to a datetime64 integer in nanoseconds (Pandas default)
            time = (self.sample_values[:,0] * 1_000_000_000).astype('datetime64[ns]')
            # Add time as first column
            samples.insert(0, self.labels[0], time, True)
            if self.verbose: print('...done', flush=True)
        else:
            # Keep time, if used, in seconds
            samples = pd.DataFrame(self.sample_values, columns=self.labels)

        # Add sample metadata (start time in seconds since epoch, and sample frequency)
        samples.attrs['time'] = self.get_start_time()
        samples.attrs['fs'] = self.get_sample_rate()
        return samples

    # Time of first sample (seconds since epoch)
    def get_start_time(self):
        return self.info['time_offset']

    def get_sample_rate(self):
        return self.info['frequency']
    
    def get_num_samples(self):
        return self.info['num_samples']




def main():
    filename = '../_local/data/sample.wav'
    #filename = '../../../_local/data/sample.wav'

    with WavData(filename, verbose=True, include_gyro=True) as wav_data:
        sample_values = wav_data.get_sample_values()
        samples = wav_data.get_samples()

    print(sample_values)
    print(samples)
    #_export(wav_data, os.path.splitext(filename)[0] + '.wav.csv')
    print('Done')

if __name__ == "__main__":
    main()


