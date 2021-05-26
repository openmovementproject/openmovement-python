# "Potentially Zipped" Helper Tool
# Dan Jackson, 2021

import os
import sys
import zipfile
import fnmatch
import tempfile
import uuid

class PotentiallyZippedFile:
    """
    Handles a "potentially zipped" file where a file is needed on (local) disk, and can't just be a stream from a compressed file 
    -- e.g. memory-mapped files or external processes.
    If the file extension is not '.zip', the original file is passed through via 'with' syntax.
    Otherwise, the file is expected to be a .ZIP archive, and the 'filter' is used to find a matching inner filename.  
    It is an error if there is not exactly one matching inner filename.
    The matching file is extracted to a temporary location, and that location is passed through the 'with' syntax.
    At the end of the 'with' block, the temporary file is deleted.
    """

    def __init__(self, source_file, filters=['*.*'], verbose=False):
        """
        Construct a zip helper object -- if the file is an archive, its inner file is temporarily extracted for use in a 'with' clause.

        :param source_file: The potentially zipped filename -- if matching '*.zip' the archive is opened to find a matching inner file.
        :param filter: A list (or a string is treated as a single element list) of case-insensitive 'glob' string expressions to match 
                       the expected inner filename (default: '*.*' = a single-file archive).
        :param verbose: Output more detailed information.
        """
        self.source_file = source_file
        self.verbose = verbose
        self.archive_file = None
        self.temp_file = None

        # Allow a single filter to be passed as a string
        self.filters = filters
        if type(self.filters) is not list:
            self.filters = [self.filters]

        # Files not ending in .ZIP will be passed through
        source_extension = os.path.splitext(self.source_file)[1]
        if source_extension.lower() != '.zip':
            return

        # If it ends in .ZIP, check that it is a valid archive
        # (just to improve the error message -- it may not be a valid archive by the time it is opened below!)
        if not zipfile.is_zipfile(self.source_file):
            raise Exception('File is named .ZIP but does not seem to be a valid archive')

        # Open .ZIP archive
        with zipfile.ZipFile(self.source_file, 'r') as zip:

            # Examine all zip entries to find matches against the filters
            matching = []
            zip_info_list = zip.infolist()
            for zi in zip_info_list:
                # Check whether this zip entry matches any of the filters
                is_match = False
                for filter in filters:
                    if fnmatch.fnmatch(zi.filename.lower(), filter.lower()):
                        is_match = True
                
                # Ignore if not a match
                if is_match:
                    matching += [zi]

            if len(matching) == 0:
                raise Exception('No filenames in the archive match the filter(s)')

            if len(matching) != 1:
                raise Exception('Multiple filenames in the archive match the filter(s): ' + str(matching))
                
            # Only a single match allowed
            matching_zip_info = matching[0]
            self.archive_file = '' + matching_zip_info.filename     # original filename

            # Create temporary filename
            baseArchive = os.path.splitext(os.path.basename(self.source_file))[0]
            baseFilename = os.path.splitext(os.path.basename(self.archive_file))[0]
            randomString = str(uuid.uuid4()).replace('-', '')
            ext = os.path.splitext(self.archive_file)[1]
            temp_path = tempfile.gettempdir()

            temp_filename = '__TEMP-' + randomString + '__' + baseArchive + '__' + baseFilename + ext
            
            # Have to modify zip_info filename to extract to a file with another name (?!)
            matching_zip_info.filename = temp_filename
            self.temp_file = os.path.join(temp_path, temp_filename)
            # Attempt to extract
            if self.verbose: print('EXTRACTING: ' + self.archive_file + ' (' + str(matching_zip_info.compress_size) + ') --> ' + self.temp_file + ' (' + str(matching_zip_info.file_size) + ')')
            zip.extract(matching_zip_info, path=temp_path)


    # Start of 'with'
    def __enter__(self):
        if self.temp_file is not None:
            # Temporary file
            return self.temp_file
        else:
            # Original file
            return self.source_file
        
    # Close handle at end of 'with'
    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
    
    # Close handle when destructed
    def __del__(self):
        self.close()

    def close(self):
        """
        Finish using the file.
        Automatically called if using the 'with' syntax.
        If an inner file was temporarily extracted, it is removed.
        """
        remove_file = self.temp_file
        self.temp_file = None       # Don't try to remove again

        # Nothing to do if not using a temporary file
        if remove_file is None:
            return

        # Safety precaution: filename must have this tag in to be deleted
        if '__TEMP-' not in remove_file:
            raise Exception('Expected safety marker not within temporary filename: ' + remove_file)
        
        # Try to remove the temporary file (any issue here will just give a warning)
        try:
            if self.verbose: print('REMOVING: ' + remove_file)
            if '__TEMP-' in remove_file:    # Safety precaution
                os.remove(remove_file)
        except Exception as e:
            print('WARNING: Problem removing temporary file (' + str(e) + '): ' + remove_file, file=sys.stderr)
        

# Test function
def main():
    print('Start')
    #filename = '../../_local/sample.zip'
    filename = '../../_local/sample-nested.zip'
    #filename = '../../_local/sample.cwa'
    with PotentiallyZippedFile(filename, ['*.cwa', '*.omx'], verbose=True) as file:
        print('USING: ' + file)
    print('End')

if __name__ == "__main__":
    main()
