import re
import os
import datetime

# For files with relative numeric timestamps that store the base time in the filename
def csv_time_from_filename(csv_filename):
    time_zero = 0
    parts = re.match('(\d\d\d\d)-?(\d\d)-?(\d\d)[-T ]?(\d\d):?(\d\d):?(\d\d)(\.?\d\d\d)?', os.path.basename(csv_filename))
    if parts:
        msec = parts.group(7)
        if msec == None:
            msec = 0
        else:
            msec = int(msec)
        time_zero = datetime.datetime(int(parts.group(1)), int(parts.group(2)), int(parts.group(3)), int(parts.group(4)), int(parts.group(5)), int(parts.group(6)), msec * 1000, tzinfo=datetime.timezone.utc).timestamp()
    return time_zero


# For files where the scaling metadata is stored int the last part of the filename
def csv_scale_from_filename(csv_filename):
    global_scale = 1
    basename = os.path.splitext(os.path.basename(csv_filename))[0]
    if basename.endswith('_ACC'):
        global_scale = 0.0002   # possibly 1/4096?
    if basename.endswith('_GYR'):
        global_scale = 0.0305   # probably 1/32768
    if basename.endswith('_EEG') or basename.endswith('_EOG'):
        global_scale = 0.4808
    if basename.endswith('_ECG'):
        global_scale = 1.4424
    if basename.endswith('_EMG'):
        global_scale = 0.4808
    return global_scale
