# CWA Reader
# Dan Jackson, Open Movement, 2017-2021
#
# Derived from cwa_metadata.py CWA Metadata Reader by Dan Jackson, Open Movement.
#
# TODO:
# * Create a 'segment' and merge adjacent packets where the sequence ID increases by one, the session_id/rate/range/format stays the same, all but the last are full of data, the timestamp/sample index monotonically increases
# * Interpret segments as "sessions": a segment plus additional identical-config segments with a delay less than a maximum interval (e.g. 7 days).
# * Read a sample span within a session.


import sys
from struct import *
import time
from datetime import datetime

import numpy as np
import pandas as pd

SECTOR_SIZE = 512
EPOCH = datetime(1970, 1, 1)

dtCWA = np.dtype([
    ('packet_header', '<H'),        # @ 0  +2   ASCII "AX", little-endian (0x5841)
    ('packet_length', '<H'),        # @ 2  +2   Packet length (508 bytes, with header (4) = 512 bytes total)
    ('device_fractional', '<H'),    # @ 4  +2   Top bit set: 15-bit fraction of a second for the time stamp, the timestampOffset was already adjusted to minimize this assuming ideal sample rate; Top bit clear: 15-bit device identifier, 0 = unknown;
    ('session_id', '<I'),           # @ 6  +4   Unique session identifier, 0 = unknown
    ('sequence_id', '<I'),          # @10  +4   Sequence counter (0-indexed), each packet has a new number (reset if restarted)
    ('timestamp_packed', '<I'),     # @14  +4   Last reported RTC value, 0 = unknown
    ('light', '<H'),                # @18  +2   Last recorded light sensor value in raw units, 0 = none #  log10LuxTimes10Power3 = ((value + 512.0) * 6000 / 1024); lux = pow(10.0, log10LuxTimes10Power3 / 1000.0);
    ('temperature', '<H'),          # @20  +2   Last recorded temperature sensor value in raw units, 0 = none
    ('events', 'B'),                # @22  +1   Event flags since last packet, b0 = resume logging, b1 = reserved for single-tap event, b2 = reserved for double-tap event, b3 = reserved, b4 = reserved for diagnostic hardware buffer, b5 = reserved for diagnostic software buffer, b6 = reserved for diagnostic internal flag, b7 = reserved)
    ('battery', 'B'),               # @23  +1   Last recorded battery level in raw units, 0 = unknown
    ('rate_code', 'B'),             # @24  +1   Sample rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
    ('num_axes_bps', 'B'),          # @25  +1   0x32 (top nibble: number of axes = 3; bottom nibble: packing format - 2 = 3x 16-bit signed, 0 = 3x 10-bit signed + 2-bit exponent)
    ('timestamp_offset', '<h'),     # @26  +2   Relative sample index from the start of the buffer where the whole-second timestamp is valid
    ('sample_count', '<H'),         # @28  +2   Number of accelerometer samples (depending on packing, 40/80/120 if this sector is full)
    ('raw_data', 'S480'),           # @30  +480 Raw sample data.  Each sample is either 3x 16-bit signed values (x, y, z) or one 32-bit packed value (The bits in bytes [3][2][1][0]: eezzzzzz zzzzyyyy yyyyyyxx xxxxxxxx, e = binary exponent, lsb on right)
    ('checksum', '<H'),             # @510 +2   Checksum of packet (16-bit word-wise sum of the whole packet should be zero)
])


# 16-bit checksum (should sum to zero)
def checksum(data):
	sum = 0
	for i in range(0, len(data), 2):
		#value = data[i] | (data[i + 1] << 8)
		value = unpack('<H', data[i:i+2])[0]
		sum = (sum + value) & 0xffff
	return sum

def short_sign_extend(value):
    return ((value + 0x8000) & 0xffff) - 0x8000

def timestamp_string(timestamp):
	if timestamp == 0:
		return "0"
	if timestamp < 0:
		return "-1"
	# return str(datetime.fromtimestamp(timestamp))
	return datetime.utcfromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S.%f")[:23]


# Local "URL-decode as UTF-8 string" function
def urldecode(input):
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


def cwa_parse_metadata(data):
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
		name = urldecode(parts[0])
		if len(name) > 0:
			value = None
			
			if len(parts) > 1:
				# Value is URL-encoded UTF-8
				value = urldecode(parts[1])
			
			# Expand shorthand names
			name = shorthand.get(name, name)
			
			# Store metadata name-value pair
			metadata[name] = value
	
	# Metadata dictionary
	return metadata


def parse_timestamp(value):
	if value == 0x00000000:	# Infinitely in past = 'always before now'
		return 0
	if value == 0xffffffff:	# Infinitely in future = 'always after now'
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
		timestamp = (dt - EPOCH).total_seconds()
		return timestamp
		# return str(datetime.fromtimestamp(timestamp))
		# return time.strptime(t, '%Y-%m-%d %H:%M:%S')
	except ValueError:
		print("WARNING: Invalid date:", year, month, day, hours, mins, secs)
		return -1


def cwa_header(block):
	header = {}
	if len(block) >= 512:
		packetHeader = unpack('BB', block[0:2])							# @ 0  +2   ASCII "MD", little-endian (0x444D)
		packetLength = unpack('<H', block[2:4])[0]						# @ 2  +2   Packet length (1020 bytes, with header (4) = 1024 bytes total)
		if packetHeader[0] == ord('M') and packetHeader[1] == ord('D') and packetLength >= 508:
			header['packetLength'] = packetLength
			# unpack() <=little-endian, bB=s/u 8-bit, hH=s/u 16-bit, iI=s/u 32-bit		
			hardwareType = unpack('B', block[4:5])[0]					# @ 4  +1   Hardware type (0x00/0xff/0x17 = AX3, 0x64 = AX6)
			header['hardwareType'] = hardwareType
			if hardwareType == 0x00 or hardwareType == 0xff:
				hardwareType = 0x17
			if hardwareType == 0x17:
				header['deviceType'] = 'AX3'
			elif hardwareType == 0x64:
				header['deviceType'] = 'AX6'
			else:
				header['deviceType'] = hex(hardwareType)[2:] # BCD
			header['deviceId'] = unpack('<H', block[5:7])[0]			# @ 5  +2   Device identifier
			header['sessionId'] = unpack('<I', block[7:11])[0]			# @ 7  +4   Unique session identifier
			deviceIdUpper = unpack('<H', block[11:13])[0]				# @11  +2   Upper word of device id (if 0xffff is read, treat as 0x0000)
			if deviceIdUpper != 0xffff:
				header['deviceId'] |= deviceIdUpper << 16
			header['loggingStart'] = parse_timestamp(unpack('<I', block[13:17])[0])		# @13  +4   Start time for delayed logging
			header['loggingEnd'] = parse_timestamp(unpack('<I', block[17:21])[0])			# @17  +4   Stop time for delayed logging		
			header['loggingCapacity'] = unpack('<I', block[21:25])[0]	# @21  +4   (Deprecated: preset maximum number of samples to collect, 0 = unlimited)
			# header['reserved3'] = block[25:26]						# @25  +1   (1 byte reserved)
			header['flashLed'] = unpack('B', block[35:36])[0]			# @26  +1   Flash LED during recording
			if header['flashLed'] == 0xff:
				header['flashLed'] = 0
			# header['reserved4'] = block[27:35]						# @25  +8   (8 bytes reserved)
			sensorConfig = unpack('B', block[35:36])[0]					# @35  +1   Fixed rate sensor configuration, 0x00 or 0xff means accel only, otherwise bottom nibble is gyro range (8000/2^n dps): 2=2000, 3=1000, 4=500, 5=250, 6=125, top nibble non-zero is magnetometer enabled.
			if sensorConfig != 0x00 and sensorConfig != 0xff:
				header['gyroRange'] = 8000 / 2 ** (sensorConfig & 0x0f)
			else:
				header['gyroRange'] = 0
			rateCode = unpack('B', block[36:37])[0]						# @36  +1   Sampling rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
			header['lastChange'] = parse_timestamp(unpack('<I', block[37:41])[0])   # @37  +4   Last change metadata time
			header['firmwareRevision'] = unpack('B', block[41:42])[0]	# @41  +1   Firmware revision number
			# header['timeZone'] = unpack('<H', block[42:44])[0]		# @42  +2   (Unused: originally reserved for a "Time Zone offset from UTC in minutes", 0xffff = -1 = unknown)
			# header['reserved5'] = block[44:64]						# @44  +20  (20 bytes reserved)
			header['metadata'] = cwa_parse_metadata(block[64:512])		# @64  +448 "Annotation" meta-data (448 ASCII characters, ignore trailing 0x20/0x00/0xff bytes, url-encoded UTF-8 name-value pairs)
			# header['reserved'] = block[512:1024]						# @512 +512 Reserved for device-specific meta-data (512 bytes, ASCII characters, ignore trailing 0x20/0x00/0xff bytes, url-encoded UTF-8 name-value pairs, leading '&' if present?)
			
			# Timestamps
			header['loggingStartTime'] = timestamp_string(header['loggingStart'])
			header['loggingEndTime'] = timestamp_string(header['loggingEnd'])
			header['lastChangeTime'] = timestamp_string(header['lastChange'])
			
			# Parse rateCode
			header['sampleRate'] = (3200/(1<<(15-(rateCode & 0x0f))))
			header['accelRange'] = (16 >> (rateCode >> 6))
		
	return header


def calc_timestamp(row):
    return parse_timestamp(row['timestamp_packed'])


def load(filename):
    print('Opening...', flush=True)
    with open(filename, 'rb') as fp:
        print('Loading header...', flush=True)
        header_raw = fp.read(SECTOR_SIZE)
        if len(header_raw) != SECTOR_SIZE:
            raise Exception('Problem reading file header')

        header = cwa_header(header_raw)
        if 'packetLength' not in header:
            raise Exception('File header parsing error')
        
        # Skip remaining space before first data packet
        data_offset = (((header['packetLength'] + SECTOR_SIZE - 1) // SECTOR_SIZE) * SECTOR_SIZE)
        spare_size = data_offset - SECTOR_SIZE
        print('Skipping ' + str(spare_size) + ' to offset ' + str(data_offset), flush=True)
        fp.read(spare_size)

        print('Loading data...', flush=True)
        np_data = np.fromfile(fp, dtype=dtCWA, count=-1, offset=0)

    print('Creating data frame...', flush=True)
    df = pd.DataFrame(np_data)

    print('Parsing timestamps...', flush=True)
    df['timestamp'] = df.apply(calc_timestamp, axis=1)

    print('Done...', flush=True)
    print(df)

def main():
    #file = '_local/sample.cwa'
    #file = '_local/mixed_wear.cwa'
    file = '_local/AX6-Sample-48-Hours.cwa'
    load(file)
    pass

if __name__ == "__main__":
    main()




# def cwa_data(block, extractData=False):
# 	data = {}
# 	if len(block) >= 512:
# 		packetHeader = unpack('BB', block[0:2])							# @ 0  +2   ASCII "AX", little-endian (0x5841)
# 		packetLength = unpack('<H', block[2:4])[0]						# @ 2  +2   Packet length (508 bytes, with header (4) = 512 bytes total)
# 		if packetHeader[0] == ord('A') and packetHeader[1] == ord('X') and packetLength == 508 and checksum(block[0:512]) == 0:
# 			#checksum = unpack('<H', block[510:512])[0]					# @510 +2   Checksum of packet (16-bit word-wise sum of the whole packet should be zero)

# 			deviceFractional = unpack('<H', block[4:6])[0]				# @ 4  +2   Top bit set: 15-bit fraction of a second for the time stamp, the timestampOffset was already adjusted to minimize this assuming ideal sample rate; Top bit clear: 15-bit device identifier, 0 = unknown;
# 			data['sessionId'] = unpack('<I', block[6:10])[0]			# @ 6  +4   Unique session identifier, 0 = unknown
# 			data['sequenceId'] = unpack('<I', block[10:14])[0]			# @10  +4   Sequence counter (0-indexed), each packet has a new number (reset if restarted)
# 			timestamp = read_timestamp(block[14:18])					# @14  +4   Last reported RTC value, 0 = unknown
# 			light = unpack('<H', block[18:20])[0]						# @18  +2   Last recorded light sensor value in raw units, 0 = none #  log10LuxTimes10Power3 = ((value + 512.0) * 6000 / 1024); lux = pow(10.0, log10LuxTimes10Power3 / 1000.0);
# 			data['light'] = light & 0x3f # least-significant 10 bits
# 			temperature = unpack('<H', block[20:22])[0]					# @20  +2   Last recorded temperature sensor value in raw units, 0 = none
# 			data['temperature'] = temperature * 75.0 / 256 - 50
# 			data['events'] = unpack('B', block[22:23])[0]				# @22  +1   Event flags since last packet, b0 = resume logging, b1 = reserved for single-tap event, b2 = reserved for double-tap event, b3 = reserved, b4 = reserved for diagnostic hardware buffer, b5 = reserved for diagnostic software buffer, b6 = reserved for diagnostic internal flag, b7 = reserved)
# 			battery = unpack('B', block[23:24])[0]						# @23  +1   Last recorded battery level in raw units, 0 = unknown
# 			data['battery'] = (battery + 512.0) * 6000 / 1024 / 1000.0
# 			rateCode = unpack('B', block[24:25])[0]					    # @24  +1   Sample rate code, frequency (3200/(1<<(15-(rate & 0x0f)))) Hz, range (+/-g) (16 >> (rate >> 6)).
# 			numAxesBPS = unpack('B', block[25:26])[0]					# @25  +1   0x32 (top nibble: number of axes = 3; bottom nibble: packing format - 2 = 3x 16-bit signed, 0 = 3x 10-bit signed + 2-bit exponent)
# 			timestampOffset = unpack('<h', block[26:28])[0]				# @26  +2   Relative sample index from the start of the buffer where the whole-second timestamp is valid
# 			data['sampleCount'] = unpack('<H', block[28:30])[0]			# @28  +2   Number of accelerometer samples (80 or 120 if this sector is full)
# 			# rawSampleData[480] = block[30:510]						# @30  +480 Raw sample data.  Each sample is either 3x 16-bit signed values (x, y, z) or one 32-bit packed value (The bits in bytes [3][2][1][0]: eezzzzzz zzzzyyyy yyyyyyxx xxxxxxxx, e = binary exponent, lsb on right)
			
# 			# range = 16 >> (rateCode >> 6)
# 			frequency = 3200 / (1 << (15 - (rateCode & 0x0f)))
# 			data['frequency'] = frequency
			
# 			timeFractional = 0;
# 			# if top-bit set, we have a fractional date
# 			if deviceFractional & 0x8000:
# 				# Need to undo backwards-compatible shim by calculating how many whole samples the fractional part of timestamp accounts for.
# 				timeFractional = (deviceFractional & 0x7fff) << 1     # use original deviceId field bottom 15-bits as 16-bit fractional time
# 				timestampOffset += (timeFractional * int(frequency)) >> 16 # undo the backwards-compatible shift (as we have a true fractional)
			
# 			# Add fractional time to timestamp
# 			timestamp += timeFractional / 65536

# 			data['timestamp'] = timestamp
# 			data['timestampOffset'] = timestampOffset
			
# 			data['timestampTime'] = timestamp_string(data['timestamp'])
			
# 			# Maximum samples per sector
# 			channels = (numAxesBPS >> 4) & 0x0f
# 			bytesPerAxis = numAxesBPS & 0x0f
# 			bytesPerSample = 4
# 			if bytesPerAxis == 0 and channels == 3:
# 				bytesPerSample = 4
# 			elif bytesPerAxis > 0 and channels > 0:
# 				bytesPerSample = bytesPerAxis * channels
# 			samplesPerSector = 480 // bytesPerSample
# 			data['channels'] = channels
# 			data['bytesPerAxis'] = bytesPerAxis			# 0 for DWORD packing
# 			data['bytesPerSample'] = bytesPerSample
# 			data['samplesPerSector'] = samplesPerSector

# 			# Axes
# 			accelAxis = -1
# 			gyroAxis = -1
# 			magAxis = -1
# 			if channels >= 6:
# 				gyroAxis = 0
# 				accelAxis = 3
# 				if channels >= 9:
# 					magAxis = 6
# 			elif channels >= 3:
# 				accelAxis = 0
			
# 			# Default units/scaling/range
# 			accelUnit = 256		# 1g = 256
# 			gyroRange = 2000	# 32768 = 2000dps
# 			magUnit = 16		# 1uT = 16
# 			# light is least significant 10 bits, accel scale 3-MSB, gyro scale next 3 bits: AAAGGGLLLLLLLLLL
# 			accelScale = 1 << (8 + ((light >> 13) & 0x07))
# 			if ((light >> 10) & 0x07) != 0:
# 				gyroRange = 8000 // (1 << ((light >> 10) & 0x07))
			
# 			# Scale
# 			#accelScale = 1.0 / accelUnit
# 			#gyroScale = float(gyroRange) / 32768
# 			#magScale = 1.0 / magUnit

# 			# Range
# 			accelRange = 16
# 			if rateCode != 0:
# 				accelRange = 16 >> (rateCode >> 6)
# 			#magRange = 32768 / magUnit
			
# 			# Unit
# 			gyroUnit = 32768.0 / gyroRange

# 			if accelAxis >= 0:
# 				data['accelAxis'] = accelAxis
# 				data['accelRange'] = accelRange
# 				data['accelUnit'] = accelUnit
# 			if gyroAxis >= 0:
# 				data['gyroAxis'] = gyroAxis
# 				data['gyroRange'] = gyroRange
# 				data['gyroUnit'] = gyroUnit
# 			if magAxis >= 0:
# 				data['magAxis'] = magAxis
# 				data['magRange'] = magRange
# 				data['magUnit'] = magUnit
			
# 			# Read sample values
# 			if extractData:
# 				if accelAxis >= 0:
# 					accelSamples = [[0, 0, 0]] * data['sampleCount']
# 					if bytesPerAxis == 0 and channels == 3:
# 						for i in range(data['sampleCount']):
# 							ofs = 30 + i * 4
# 							#val =  block[i] | (block[i + 1] << 8) | (block[i + 2] << 8) | (block[i + 3] << 24)
# 							val = unpack('<I', block[ofs:ofs + 4])[0]
# 							ex = (6 - ((val >> 30) & 3))
# 							accelSamples[i][0] = (short_sign_extend((0xffc0 & (val <<  6))) >> ex) / accelUnit
# 							accelSamples[i][1] = (short_sign_extend((0xffc0 & (val >>  4))) >> ex) / accelUnit
# 							accelSamples[i][2] = (short_sign_extend((0xffc0 & (val >> 14))) >> ex) / accelUnit
# 					elif bytesPerSample == 2:
# 						for i in range(data['sampleCount']):
# 							ofs = 30 + (i * 2 * channels) + 2 * accelAxis
# 							accelSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / accelUnit
# 							accelSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / accelUnit
# 							accelSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / accelUnit
# 					data['samplesAccel'] = accelSamples
				
# 				if gyroAxis >= 0 and bytesPerSample == 2:
# 					gyroSamples = [[0, 0, 0]] * data['sampleCount']
# 					for i in range(data['sampleCount']):
# 						ofs = 30 + (i * 2 * channels) + 2 * gyroAxis
# 						gyroSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / gyroUnit
# 						gyroSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / gyroUnit
# 						gyroSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / gyroUnit
# 					data['samplesGyro'] = gyroSamples
				
# 				if magAxis >= 0 and bytesPerSample == 2:
# 					magSamples = [[0, 0, 0]] * data['sampleCount']
# 					for i in range(data['sampleCount']):
# 						ofs = 30 + (i * 2 * channels) + 2 * magAxis
# 						magSamples[i][0] = (block[ofs + 0] | (block[ofs + 1] << 8)) / magUnit
# 						magSamples[i][1] = (block[ofs + 2] | (block[ofs + 3] << 8)) / magUnit
# 						magSamples[i][2] = (block[ofs + 4] | (block[ofs + 5] << 8)) / magUnit
# 					data['samplesMag'] = magSamples
			
# 			# Light
# 			light &= 0x3ff		# actual light value is least significant 10 bits

# 	return data
