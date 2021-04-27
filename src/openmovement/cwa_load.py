"""CWA File Reader
Dan Jackson, Open Movement, 2017-2021

Derived from cwa_metadata.py CWA Metadata Reader by Dan Jackson, Open Movement.
"""

# TODO:
# * Seek/read to quickly determine 'segments' where the sequence ID increases by one, the session_id/rate/range/format stays the same, all but the last are full of data, the timestamp/sample index monotonically increases
# * Read a sample-indexed span from a segment
# * Interpret adjacent segments as "sessions": a segment plus additional identical-config segments with a delay less than a maximum interval (e.g. 7 days).
# * Read a sample span within a session.

import sys
import time
from datetime import datetime
from struct import *

import numpy as np
import pandas as pd

SECTOR_SIZE = 512
EPOCH = datetime(1970, 1, 1)


def _fast_timestamp(value):
    """Faster date/time parsing.  This does not include 'always' limits; invalid dates do not cause an error; the first call will be slower as a lookup table is created."""
    # On first run, build lookup table for initial 10-bits of the packed date-time parsing, minus one day as days are 1-indexed
    if not hasattr(_fast_timestamp, "SECONDS_BEFORE_YEAR_MONTH"):
        _fast_timestamp.SECONDS_BEFORE_YEAR_MONTH = [0] * 1024        # YYYYYYMM MM (Y=years since 2000, M=month-of-year 1-indexed)
        SECONDS_PER_DAY = 24 * 60 * 60
        DAYS_IN_MONTH = [ 0, 31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31, 0, 0, 0 ]    # invalid month 0, months 1-12 (non-leap-year), invalid months 13-15
        seconds_before = 946684800        # Seconds from UNIX epoch (1970) until device epoch (2000)
        for year in range(0, 64):        # 2000-2063
            for month in range(0, 16):    # invalid month 0, months 1-12, invalid months 13-15
                index = (year << 4) + month
                _fast_timestamp.SECONDS_BEFORE_YEAR_MONTH[index] = seconds_before - SECONDS_PER_DAY    # minus one day as day-of-month is 1-based
                days = DAYS_IN_MONTH[month]
                if year % 4 == 0 and month == 2:    # This is correct for this year range
                    days += 1
                seconds_before += days * SECONDS_PER_DAY

    year_month = (value >> 22) & 0x3ff
    day   = (value >> 17) & 0x1f
    hours = (value >> 12) & 0x1f
    mins  = (value >>  6) & 0x3f
    secs  = value & 0x3f
    return _fast_timestamp.SECONDS_BEFORE_YEAR_MONTH[year_month] + ((day * 24 + hours) * 60 + mins) * 60 + secs


def _parse_timestamp(value):
    """Single value date/time parsing (slower, handles 'always' times, handles invalid times)"""
    if value == 0x00000000:    # Infinitely in past = 'always before now'
        return 0
    if value == 0xffffffff:    # Infinitely in future = 'always after now'
        return -1
    # bit pattern:  YYYYYYMM MMDDDDDh hhhhmmmm mmssssss
    year  = ((value >> 26) & 0x3f) + 2000
    month = (value >> 22) & 0x0f
    day   = (value >> 17) & 0x1f
    hours = (value >> 12) & 0x1f
    mins  = (value >>  6) & 0x3f
    secs  = (value >>  0) & 0x3f
    try:
        dt = datetime(year, month, day, hours, mins, secs)
        timestamp = int((dt - EPOCH).total_seconds())
        return timestamp
        # return str(datetime.fromtimestamp(timestamp))
        # return time.strptime(t, '%Y-%m-%d %H:%M:%S')
    except ValueError:
        print("WARNING: Invalid date:", year, month, day, hours, mins, secs)
        return -1


def _checksum(data):
    """16-bit checksum for data blocks (should sum to zero)"""
    sum = 0
    for i in range(0, len(data), 2):
        #value = data[i] | (data[i + 1] << 8)
        value = unpack('<H', data[i:i+2])[0]
        sum = (sum + value) & 0xffff
    return sum


def _short_sign_extend(value):
    """Sign-extend a 16-bit value."""
    return ((value + 0x8000) & 0xffff) - 0x8000


def _timestamp_string(timestamp):
    """Formatted version of timestamp"""
    if timestamp == 0:
        return "0"
    if timestamp < 0:
        return "-1"
    # return str(datetime.fromtimestamp(timestamp))
    return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:23]


def _urldecode(input):
    """URL-decode metadata"""
    output = bytearray()
    nibbles = 0
    value = 0
    # Each input character
    for char in input:
        if char == '%':
            # Begin a percent-encoded hex pair
            nibbles = 2
            value = 0
        elif nibbles > 0:
            # Parse the percent-encoded hex digits
            value *= 16
            if char >= 'a' and char <= 'f':
                value += ord(char) + 10 - ord('a')
            elif char >= 'A' and char <= 'F':
                value += ord(char) + 10 - ord('A')
            elif char >= '0' and char <= '9':
                value += ord(char) - ord('0')
            nibbles -= 1
            if nibbles == 0:
                output.append(value)
        elif char == '+':
            # Treat plus as space (application/x-www-form-urlencoded)
            output.append(ord(' '))
        else:
            # Preserve character
            output.append(ord(char))
    return output.decode('utf-8')


def _cwa_parse_metadata(data):
    """Parse the metadata string."""

    # Metadata represented as a dictionary
    metadata = {}
    
    # Shorthand name expansions
    shorthand = {
        "_c":  "Study Centre", 
        "_s":  "Study Code", 
        "_i":  "Investigator", 
        "_x":  "Exercise Code", 
        "_v":  "Volunteer Num", 
        "_p":  "Body Location", 
        "_so": "Setup Operator", 
        "_n":  "Notes", 
        "_b":  "Start time", 
        "_e":  "End time", 
        "_ro": "Recovery Operator", 
        "_r":  "Retrieval Time", 
        "_co": "Comments", 
        "_sc": "Subject Code", 
        "_se": "Sex", 
        "_h":  "Height", 
        "_w":  "Weight", 
        "_ha": "Handedness", 
    }
    
    # CWA File has 448 bytes of metadata at offset 64
    if sys.version_info[0] < 3:
        encString = str(data)
    else:
        encString = str(data, 'ascii')
    
    # Remove any trailing spaces, null, or 0xFF bytes
    encString = encString.rstrip('\x20\xff\x00')
    
    # Name-value pairs separated with ampersand
    nameValues = encString.split('&')
    
    # Each name-value pair separated with an equals
    for nameValue in nameValues:
        parts = nameValue.split('=')
        # Name is URL-encoded UTF-8
        name = _urldecode(parts[0])
        if len(name) > 0:
            value = None
            
            if len(parts) > 1:
                # Value is URL-encoded UTF-8
                value = _urldecode(parts[1])
            
            # Expand any shorthand names
            name = shorthand.get(name, name)
            
            # Store metadata name-value pair
            metadata[name] = value
    
    # Metadata dictionary
    return metadata


def _parse_cwa_header(block):
    """Parse a header block"""
    header = {}
    if len(block) >= 512:
        packetHeader = unpack('BB', block[0:2])                         # @ 0  +2   ASCII "MD", little-endian (0x444D)
        packetLength = unpack('<H', block[2:4])[0]                      # @ 2  +2   Packet length (1020 bytes, with header (4) = 1024 bytes total)
        if packetHeader[0] == ord('M') and packetHeader[1] == ord('D') and packetLength >= 508:
            header['packetLength'] = packetLength
            # unpack() <=little-endian, bB=s/u 8-bit, hH=s/u 16-bit, iI=s/u 32-bit        
            hardwareType = unpack('B', block[4:5])[0]                   # @ 4  +1   Hardware type (0x00/0xff/0x17 = AX3, 0x64 = AX6)
            header['hardwareType'] = hardwareType
            if hardwareType == 0x00 or hardwareType == 0xff:
                hardwareType = 0x17
            if hardwareType == 0x17:
                header['deviceType'] = 'AX3'
            elif hardwareType == 0x64:
                header['deviceType'] = 'AX6'
            else:
                header['deviceType'] = hex(hardwareType)[2:] # BCD
            header['deviceId'] = unpack('<H', block[5:7])[0]            # @ 5  +2   Device identifier
            header['sessionId'] = unpack('<I', block[7:11])[0]          # @ 7  +4   Unique session identifier
            deviceIdUpper = unpack('<H', block[11:13])[0]               # @11  +2   Upper word of device id (if 0xffff is read, treat as 0x0000)
            if deviceIdUpper != 0xffff:
                header['deviceId'] |= deviceIdUpper << 16
            header['loggingStart'] = _parse_timestamp(unpack('<I', block[13:17])[0])    # @13  +4   Start time for delayed logging
            header['loggingEnd'] = _parse_timestamp(unpack('<I', block[17:21])[0])      # @17  +4   Stop time for delayed logging        
            header['loggingCapacity'] = unpack('<I', block[21:25])[0]   # @21  +4   (Deprecated: preset maximum number of samples to collect, 0 = unlimited)
            # header['reserved3'] = block[25:26]                        # @25  +1   (1 byte reserved)
            header['flashLed'] = unpack('B', block[35:36])[0]           # @26  +1   Flash LED during recording
            if header['flashLed'] == 0xff:
                header['flashLed'] = 0
            # header['reserved4'] = block[27:35]                        # @25  +8   (8 bytes reserved)
            sensorConfig = unpack('B', block[35:36])[0]                 # @35  +1   Fixed rate sensor configuration, 0x00 or 0xff means accel only, otherwise bottom nibble is gyro range (8000/2^n dps): 2=2000, 3=1000, 4=500, 5=250, 6=125, top nibble non-zero is magnetometer enabled.
            if sensorConfig != 0x00 and sensorConfig != 0xff:
                header['gyroRange'] = 8000 / 2 ** (sensorConfig & 0x0f)
            else:
                header['gyroRange'] = 0
            rateCode = unpack('B', block[36:37])[0]                     # @36  +1   Sampling rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
            header['lastChange'] = _parse_timestamp(unpack('<I', block[37:41])[0])      # @37  +4   Last change metadata time
            header['firmwareRevision'] = unpack('B', block[41:42])[0]   # @41  +1   Firmware revision number
            # header['timeZone'] = unpack('<H', block[42:44])[0]        # @42  +2   (Unused: originally reserved for a "Time Zone offset from UTC in minutes", 0xffff = -1 = unknown)
            # header['reserved5'] = block[44:64]                        # @44  +20  (20 bytes reserved)
            header['metadata'] = _cwa_parse_metadata(block[64:512])     # @64  +448 "Annotation" meta-data (448 ASCII characters, ignore trailing 0x20/0x00/0xff bytes, url-encoded UTF-8 name-value pairs)
            # header['reserved'] = block[512:1024]                      # @512 +512 Reserved for device-specific meta-data (512 bytes, ASCII characters, ignore trailing 0x20/0x00/0xff bytes, url-encoded UTF-8 name-value pairs, leading '&' if present?)
            
            # Timestamps
            header['loggingStartTime'] = _timestamp_string(header['loggingStart'])
            header['loggingEndTime'] = _timestamp_string(header['loggingEnd'])
            header['lastChangeTime'] = _timestamp_string(header['lastChange'])
            
            # Parse rateCode
            header['sampleRate'] = (3200/(1<<(15-(rateCode & 0x0f))))
            header['accelRange'] = (16 >> (rateCode >> 6))
        
    return header


def _parse_cwa_data(block, extractData=False):
    """(Slow) parser for a single block."""
    data = {}
    if len(block) >= 512:
        packetHeader = unpack('BB', block[0:2])                       # @ 0  +2   ASCII "AX", little-endian (0x5841)
        packetLength = unpack('<H', block[2:4])[0]                    # @ 2  +2   Packet length (508 bytes, with header (4) = 512 bytes total)
        if packetHeader[0] == ord('A') and packetHeader[1] == ord('X') and packetLength == 508 and _checksum(block[0:512]) == 0:
            #checksum = unpack('<H', block[510:512])[0]               # @510 +2   Checksum of packet (16-bit word-wise sum of the whole packet should be zero)

            deviceFractional = unpack('<H', block[4:6])[0]            # @ 4  +2   Top bit set: 15-bit fraction of a second for the time stamp, the timestampOffset was already adjusted to minimize this assuming ideal sample rate; Top bit clear: 15-bit device identifier, 0 = unknown;
            data['sessionId'] = unpack('<I', block[6:10])[0]          # @ 6  +4   Unique session identifier, 0 = unknown
            data['sequenceId'] = unpack('<I', block[10:14])[0]        # @10  +4   Sequence counter (0-indexed), each packet has a new number (reset if restarted)
            timestamp = _parse_timestamp(unpack('<I', block[14:18])[0]) # @14  +4   Last reported RTC value, 0 = unknown
            light = unpack('<H', block[18:20])[0]                     # @18  +2   Last recorded light sensor value in raw units, 0 = none #  log10LuxTimes10Power3 = ((value + 512.0) * 6000 / 1024); lux = pow(10.0, log10LuxTimes10Power3 / 1000.0);
            data['light'] = light & 0x3ff  # least-significant 10 bits
            temperature = unpack('<H', block[20:22])[0]               # @20  +2   Last recorded temperature sensor value in raw units, 0 = none
            data['temperature'] = temperature * 75.0 / 256 - 50
            data['events'] = unpack('B', block[22:23])[0]             # @22  +1   Event flags since last packet, b0 = resume logging, b1 = reserved for single-tap event, b2 = reserved for double-tap event, b3 = reserved, b4 = reserved for diagnostic hardware buffer, b5 = reserved for diagnostic software buffer, b6 = reserved for diagnostic internal flag, b7 = reserved)
            battery = unpack('B', block[23:24])[0]                    # @23  +1   Last recorded battery level in raw units, 0 = unknown
            data['battery'] = (battery + 512.0) * 6000 / 1024 / 1000.0
            rateCode = unpack('B', block[24:25])[0]                   # @24  +1   Sample rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
            data['rateCode'] = rateCode
            numAxesBPS = unpack('B', block[25:26])[0]                 # @25  +1   0x32 (top nibble: number of axes = 3; bottom nibble: packing format - 2 = 3x 16-bit signed, 0 = 3x 10-bit signed + 2-bit exponent)
            data['numAxesBPS'] = numAxesBPS
            timestampOffset = unpack('<h', block[26:28])[0]           # @26  +2   Relative sample index from the start of the buffer where the whole-second timestamp is valid
            data['sampleCount'] = unpack('<H', block[28:30])[0]       # @28  +2   Number of accelerometer samples (40/80/120, depending on format, if this sector is full)
            # rawSampleData[480] = block[30:510]                      # @30  +480 Raw sample data.  Each sample is either 3x 16-bit signed values (x, y, z) or one 32-bit packed value (The bits in bytes [3][2][1][0]: eezzzzzz zzzzyyyy yyyyyyxx xxxxxxxx, e = binary exponent, lsb on right)
            
            # range = 16 >> (rateCode >> 6)
            frequency = 3200 / (1 << (15 - (rateCode & 0x0f)))
            data['frequency'] = frequency
            
            timeFractional = 0;
            # if top-bit set, we have a fractional date
            if deviceFractional & 0x8000:
                # Need to undo backwards-compatible shim by calculating how many whole samples the fractional part of timestamp accounts for.
                timeFractional = (deviceFractional & 0x7fff) << 1     # use original deviceId field bottom 15-bits as 16-bit fractional time
                timestampOffset += (timeFractional * int(frequency)) >> 16 # undo the backwards-compatible shift (as we have a true fractional)
            
            # Add fractional time to timestamp
            timestamp += timeFractional / 65536

            data['timestamp'] = timestamp
            data['timestampOffset'] = timestampOffset
            
            data['timestampTime'] = _timestamp_string(data['timestamp'])
            
            # Maximum samples per sector
            channels = (numAxesBPS >> 4) & 0x0f
            bytesPerAxis = numAxesBPS & 0x0f
            bytesPerSample = 4
            if bytesPerAxis == 0 and channels == 3:
                bytesPerSample = 4
            elif bytesPerAxis > 0 and channels > 0:
                bytesPerSample = bytesPerAxis * channels
            samplesPerSector = 480 // bytesPerSample
            data['channels'] = channels
            data['bytesPerAxis'] = bytesPerAxis            # 0 for DWORD packing
            data['bytesPerSample'] = bytesPerSample
            data['samplesPerSector'] = samplesPerSector

            # Axes
            accelAxis = -1
            gyroAxis = -1
            magAxis = -1
            if channels >= 6:
                gyroAxis = 0
                accelAxis = 3
                if channels >= 9:
                    magAxis = 6
            elif channels >= 3:
                accelAxis = 0
            
            # Default units/scaling/range
            accelUnit = 256        # 1g = 256
            gyroRange = 2000    # 32768 = 2000dps
            magUnit = 16        # 1uT = 16
            # light is least significant 10 bits, accel scale 3-MSB, gyro scale next 3 bits: AAAGGGLLLLLLLLLL
            accelScale = 1 << (8 + ((light >> 13) & 0x07))
            if ((light >> 10) & 0x07) != 0:
                gyroRange = 8000 // (1 << ((light >> 10) & 0x07))
            
            # Scale
            #accelScale = 1.0 / accelUnit
            #gyroScale = float(gyroRange) / 32768
            #magScale = 1.0 / magUnit

            # Range
            accelRange = 16
            if rateCode != 0:
                accelRange = 16 >> (rateCode >> 6)
            #magRange = 32768 / magUnit
            
            # Unit
            gyroUnit = 32768.0 / gyroRange

            if accelAxis >= 0:
                data['accelAxis'] = accelAxis
                data['accelRange'] = accelRange
                data['accelUnit'] = accelUnit
            if gyroAxis >= 0:
                data['gyroAxis'] = gyroAxis
                data['gyroRange'] = gyroRange
                data['gyroUnit'] = gyroUnit
            if magAxis >= 0:
                data['magAxis'] = magAxis
                data['magRange'] = magRange
                data['magUnit'] = magUnit
            
            # Read sample values
            if extractData:
                if accelAxis >= 0:
                    accelSamples = [[0, 0, 0]] * data['sampleCount']
                    if bytesPerAxis == 0 and channels == 3:
                        for i in range(data['sampleCount']):
                            ofs = 30 + i * 4
                            #val =  block[i] | (block[i + 1] << 8) | (block[i + 2] << 8) | (block[i + 3] << 24)
                            val = unpack('<I', block[ofs:ofs + 4])[0]
                            ex = (6 - ((val >> 30) & 3))
                            accelSamples[i][0] = (_short_sign_extend((0xffc0 & (val <<  6))) >> ex) / accelUnit
                            accelSamples[i][1] = (_short_sign_extend((0xffc0 & (val >>  4))) >> ex) / accelUnit
                            accelSamples[i][2] = (_short_sign_extend((0xffc0 & (val >> 14))) >> ex) / accelUnit
                    elif bytesPerSample == 2:
                        for i in range(data['sampleCount']):
                            ofs = 30 + (i * 2 * channels) + 2 * accelAxis
                            accelSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / accelUnit
                            accelSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / accelUnit
                            accelSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / accelUnit
                    data['samplesAccel'] = accelSamples
                
                if gyroAxis >= 0 and bytesPerSample == 2:
                    gyroSamples = [[0, 0, 0]] * data['sampleCount']
                    for i in range(data['sampleCount']):
                        ofs = 30 + (i * 2 * channels) + 2 * gyroAxis
                        gyroSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / gyroUnit
                        gyroSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / gyroUnit
                        gyroSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / gyroUnit
                    data['samplesGyro'] = gyroSamples
                
                if magAxis >= 0 and bytesPerSample == 2:
                    magSamples = [[0, 0, 0]] * data['sampleCount']
                    for i in range(data['sampleCount']):
                        ofs = 30 + (i * 2 * channels) + 2 * magAxis
                        magSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / magUnit
                        magSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / magUnit
                        magSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / magUnit
                    data['samplesMag'] = magSamples


    return data




class CwaData():
    """
    CWA file loader
    """

    def _read_data(self):
        if self.verbose: print('Opening CWA file...', flush=True)
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
        self.header = _parse_cwa_header(self.full_buffer)

        self.data_offset = 0
        if 'packetLength' in self.header:
            self.data_offset = (((self.header['packetLength'] + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE)
        else:
            raise Exception('File header parsing error')

        # Parse first sector to get initial data format
        self.data_format = {}
        if (len(self.full_buffer) - self.data_offset >= SECTOR_SIZE):
            self.data_format = _parse_cwa_data(self.full_buffer[self.data_offset:self.data_offset + SECTOR_SIZE])
            if 'channels' not in self.data_format or self.data_format['channels'] < 1 or 'samplesPerSector' not in self.data_format or self.data_format['samplesPerSector'] <= 0:
                raise Exception('Unexpected data format')
        else:
            raise Exception('File has no data')


    def _parse_data(self):
        if self.verbose: print('Interpreting data...', flush=True)
        self.data_buffer = self.full_buffer[self.data_offset:]

        # Data type for numpy loading
        dt_cwa = np.dtype([
            ('packet_header', '<H'),                # @ 0  +2   ASCII "AX", little-endian (0x5841)
            ('packet_length', '<H'),                # @ 2  +2   Packet length (508 bytes, with header (4) = 512 bytes total)
            ('device_fractional', '<H'),            # @ 4  +2   Top bit set: 15-bit fraction of a second for the time stamp, the timestampOffset was already adjusted to minimize this assuming ideal sample rate; Top bit clear: 15-bit device identifier, 0 = unknown;
            ('session_id', '<I'),                   # @ 6  +4   Unique session identifier, 0 = unknown
            ('sequence_id', '<I'),                  # @10  +4   Sequence counter (0-indexed), each packet has a new number (reset if restarted)
            ('timestamp_packed', '<I'),             # @14  +4   Last reported RTC value, 0 = unknown
            ('light', '<H'),                        # @18  +2   Last recorded light sensor value in raw units, 0 = none #  log10LuxTimes10Power3 = ((value + 512.0) * 6000 / 1024); lux = pow(10.0, log10LuxTimes10Power3 / 1000.0);
            ('temperature', '<H'),                  # @20  +2   Last recorded temperature sensor value in raw units, 0 = none
            ('events', 'B'),                        # @22  +1   Event flags since last packet, b0 = resume logging, b1 = reserved for single-tap event, b2 = reserved for double-tap event, b3 = reserved, b4 = reserved for diagnostic hardware buffer, b5 = reserved for diagnostic software buffer, b6 = reserved for diagnostic internal flag, b7 = reserved)
            ('battery', 'B'),                       # @23  +1   Last recorded battery level in raw units, 0 = unknown
            ('rate_code', 'B'),                     # @24  +1   Sample rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
            ('num_axes_bps', 'B'),                  # @25  +1   0x32 (top nibble: number of axes = 3; bottom nibble: packing format - 2 = 3x 16-bit signed, 0 = 3x 10-bit signed + 2-bit exponent)
            ('timestamp_offset', '<h'),             # @26  +2   Relative sample index from the start of the buffer where the whole-second timestamp is valid
            ('sample_count', '<H'),                 # @28  +2   Number of accelerometer samples (depending on packing, 40/80/120 if this sector is full)
            ('raw_data_buffer', np.dtype('V480')),  # @30  +480 Raw sample data.  Each sample is either 3x 16-bit signed values (x, y, z) or one 32-bit packed value (The bits in bytes [3][2][1][0]: eezzzzzz zzzzyyyy yyyyyyxx xxxxxxxx, e = binary exponent, lsb on right)
            ('checksum', '<H'),                     # @510 +2   Checksum of packet (16-bit word-wise sum of the whole packet should be zero)
        ])

        if self.verbose: print('From buffer...', flush=True)
        self.np_data = np.frombuffer(self.data_buffer, dtype=dt_cwa, count=-1)

        if self.verbose: print('Creating data frame...', flush=True)
        self.df = pd.DataFrame(self.np_data)

        if self.verbose: print('Parsing timestamps...', flush=True)
        #self.df['timestamp'] = self.df['timestamp_packed'].apply(lambda timestamp_packed: _fast_timestamp(timestamp_packed))
        _fast_timestamp_vectorized = np.vectorize(_fast_timestamp, otypes=[np.uint32])
        self.df['timestamp'] = timestamps = _fast_timestamp_vectorized(self.df['timestamp_packed'])

        if self.verbose: print('Adding row index...', flush=True)
        self.df.index.name = 'row_index'
        #self.df['row_index'] = np.arange(0, self.df.shape[0])

        # Calculate sectors checksums: view data as 16-bit LE integers, reshaped per 512-byte sector, summed (wrapped to zero)
        if self.verbose: print('Calculating checksums...', flush=True)
        np_words = np.frombuffer(self.data_buffer, dtype=np.dtype('<H'), count=-1)
        np_sector_words = np.reshape(np_words, (-1, SECTOR_SIZE // 2))
        self.df['checksum_sum'] = np.sum(np_sector_words, dtype=np.int16, axis=1)

        # Valid sectors: zero checksum, correct header and packet-length, matching data format (numAxesBPS and rateCode)
        if self.verbose: print('Determining valid sectors...', flush=True)
        self.df['valid_sector'] = ((self.df.checksum_sum == 0) & (self.df.packet_header == 22593) & (self.df.packet_length == 508) & (self.df.num_axes_bps == self.data_format['numAxesBPS']) & (self.df.rate_code == self.data_format['rateCode']))
        #print(self.df.valid_sector)

        # TODO: Create 2D strided view of all raw sample data (as DWORD/WORD) before unpacking / reshaping / scaling

        if self.verbose: print('Interpreted data', flush=True)


    def _find_segments(self):

        if self.verbose: print('Finding segments...', flush=True)
        self.all_segments = []

        # Last sector in a segment where the session_id/config changes, or the sequence does not follow on, or the next sector is invalid.
        ends = np.where((self.df.valid_sector.diff(periods=-1) != 0) | (self.df.session_id.diff(periods=-1) != 0) | (self.df.num_axes_bps.diff(periods=-1)  != 0) | ((-self.df.sequence_id).diff(periods=-1) != 1))[0]
        
        segment_start = 0
        for end in ends:
            segment = slice(segment_start, end + 1)
            self.all_segments.append(segment)
            segment_start = end + 1

        # TODO: Return segments as raw sample ranges?: scale by self.data_format.data['samplesPerSector']

        if self.verbose: print('...segments located', flush=True)
        if self.verbose: print(str(self.all_segments), flush=True)
        #print(str(self.df.iloc[self.all_segments[0]]))


    def _parse_samples(self):
        # TODO: Operate on one segment
        if self.verbose: print('Parsing samples (16-bit values)...', flush=True)
        dt_int16 = np.dtype(np.int16).newbyteorder('<')
        self.df['raw_data'] = self.df['raw_data_buffer'].apply(lambda raw_data_buffer: np.frombuffer(raw_data_buffer, dtype=dt_int16))

        if self.verbose: print('Concat samples...', flush=True)
        self.samples = np.concatenate(self.df['raw_data'])

        if self.verbose: print('Reshape samples (6-axis)...', flush=True)
        self.samples = np.reshape(self.samples, (-1, 6))




    def __init__(self, filename, verbose=False):
        start_time = time.time()

        self.verbose = verbose

        self.filename = filename
        self.fh = None
        self.full_buffer = None

        self._read_data()
        self._parse_header()
        self._parse_data()
        self._find_segments()

        self._parse_samples()

        if self.verbose: print(self.samples)
        if self.verbose: print(self.df)

        elapsed_time = time.time() - start_time
        if self.verbose: print('Done... (elapsed=' + str(elapsed_time) + ')', flush=True)


    # Nothing to do at start of 'with'
    def __enter__(self):
        pass
        
    # Close handle at end of 'with'
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    # Close handle when destructed
    def __del__(self):
        self.close()

    # # Iterating can use self
    # def __iter__(self):
    #     return self

    # # Process next data line
    # def __next__(self):
    #     try:
    #         row = next(self.reader)
    #     except StopIteration:
    #         self.close()
    #         raise   # Cascade StopIteration to caller
    #     return row

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


def main():
    #filename = '../../_local/sample.cwa'
    #filename = '../../_local/mixed_wear.cwa'
    #filename = '../../_local/AX6-Sample-48-Hours.cwa'
    filename = '../../_local/AX6-Static-8-Day.cwa'
    #filename = '../../_local/longitudinal_data.cwa'
    with CwaData(filename, verbose=True) as cwaData:
        print('Done')
    print('End')

if __name__ == "__main__":
    main()


