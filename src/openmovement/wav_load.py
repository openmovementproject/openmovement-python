# Open Movement WAV File Loader
# Dan Jackson

# NOTE: Not quite complete - do not use!


from struct import *

WAVE_FORMAT_PCM = 0x0001
WAVE_FORMAT_EXTENSIBLE = 0xFFFE

def _parse_wav_header(buffer):
    """
    Parse a WAV file chunks to determine the data offset, type and metadata.
    """
    header = {}

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
            if format_tag != WAVE_FORMAT_PCM:
                raise Exception('Not PCM format')
            if num_channels & 0xff <= 0:
                raise Exception('No channels found')
            if samples_per_sec <= 0 or samples_per_sec > 65535:
                raise Exception('Invalid frequency')
            if bits_per_sample <= 0:
                raise Exception('No bits per sample')

            if bits_per_sample & 0x7 != 0:
                print('WARNING: Bits-per-sample is not a whole number of bytes -- rounding up to nearest byte.')

            if block_align != (num_channels * ((bits_per_sample + 7) >> 3)):
                print('WARNING: Block alignment is not the expected number for the given number of channels and bytes per sample.')

            if avg_bytes_per_sec != samples_per_sec * block_align:
                print('WARNING: Average bytes per second is not the expected number for the frequency, channels and bytes-per-sample.')

            # Set output values
            header['bytes_per_channel'] = (bits_per_sample + 7) >> 3
            header['num_channels'] = num_channels
            header['frequency'] = samples_per_sec

        elif chunk == b'data':
            header['data_offset'] = ofs + 8
            header['data_size'] = chunk_size

        elif chunk == b'LIST':
            (list_type,) = unpack('<4s', buffer[ofs+8:ofs+12])

            if list_type == b'INFO':
                list_ofs = ofs + 12

                while list_ofs < ofs + chunk_size + 8:
                    (sub_chunk, sub_chunk_size) = unpack('<4sI', buffer[list_ofs+0:list_ofs+8])

                    if list_ofs + sub_chunk_size + 8 > ofs + 8 + chunk_size:
                        raise Exception('List Sub-chunk size is invalid: ' + str(sub_chunk_size))

                    info_type = None
                    if sub_chunk == b'INAM': info_type = 'name'         # Track Title (Data about the recording itself)
                    if sub_chunk == b'IART': info_type = 'artist'       # Artist Name (Data about the device that made the recording)
                    if sub_chunk == b'ICMT': info_type = 'comments'     # Comments (Data about this file representation)
                    if sub_chunk == b'ICRD': info_type = 'creation'     # Creation Date (Timestamp of first sample)
                    
                    if info_type is not None:
                        text = buffer[list_ofs + 8 : list_ofs + 8 + sub_chunk_size].decode('utf-8')
                        header[info_type] = text
                        #print('LIST-INFO: ' + info_type + ' == ' + header[info_type])

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
    
    if 'frequency' not in header or 'num_channels' not in header or 'bytes_per_channel' not in header:
        raise Exception('Valid format not found')
    
    if 'data_offset' not in header or 'data_size' not in header:
        raise Exception('Data not found')

    return header





class WavData():
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
        if self.verbose: print('Parsing header...', flush=True)
        self.header = _parse_wav_header(self.full_buffer)

        self.data_offset = self.header['data_offset']
        self.data_size = self.header['data_size']

        bytes_per_row = self.header['num_channels'] * self.header['bytes_per_channel']
        self.num_samples = self.data_size // bytes_per_row

        ## TODO: Find axis allocation and scaling from metadata

        ## TODO: Find time-offset from metadata

        ## TODO: Check bytes/sample is 2


    def __init__(self, filename, verbose=False, include_time=True, include_accel=True, include_gyro=True, include_mag=True):
        self.verbose = verbose
        self.include_time = include_time
        self.include_accel = include_accel
        self.include_gyro = include_gyro
        self.include_mag = include_mag

        self.filename = filename
        self.fh = None
        self.full_buffer = None

        self._read_data()
        self._parse_header()


    # Nothing to do at start of 'with'
    def __enter__(self):
        return self
        
    # Close handle at end of 'with'
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    # Close handle when destructed
    def __del__(self):
        self.close()

    # Iterate
    def __iter__(self):
        return iter(self.sample_values)

    def close(self):
        """Close the underlying file.  Automatically closed in with() block or when GC'd."""
        if self.full_buffer is not None:
            # Close if a mmap()
            if hasattr(self.full_buffer, 'close'):
                self.full_buffer.close()
            # Delete buffer (if large allocation not using mmap)
            del self.full_buffer
            self.full_buffer = None
        if self.fh is not None:
            self.fh.close()
            self.fh = None


    # def get_sample_values(self):
    #     """Return an ndarray of (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)"""
    #     return self.sample_values

    # def get_samples(self):
    #     """Return an DataFrame for (time, accel_x, accel_y, accel_z) or (time, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)"""
    #     if self.samples is None:
    #         self.samples = pd.DataFrame(self.sample_values, columns=self.labels)

    #     return self.samples

    def get_sample_rate(self):
        return self.header['frequency']




def main():
    filename = '../../_local/sample.wav'

    with WavData(filename, verbose=True, include_gyro=False) as wav_data:
        print('Freq: ' + str(wav_data.get_sample_rate()))
        # sample_values = wav_data.get_sample_values()
        # print(sample_values)
        # samples = wav_data.get_samples()
        # print(samples)
        #_export(wav_data, os.path.splitext(filename)[0] + '.wav.csv')
        print('Done')
        
    print('End')

if __name__ == "__main__":
    main()


