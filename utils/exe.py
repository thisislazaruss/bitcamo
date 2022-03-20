import os
from pathlib import Path
from models.malconv import TARGET_BENIGN, TARGET_MALICIOUS
from utils.os import code_section_hash, hash_bytes, is_pe_file, read_file_bytes, write_file_bytes

class Sample:
    def __init__(
        self,
        path,
        output_dir='',
        max_iterations=8,
        payload_size=0,
        initialization_method='weighted',
        epsilon=1.00,
        benign=False,
        force=False,
    ):
        # Configuration
        self.filename = os.path.basename(path)
        self.input_path = path
        self.output_path = self._generate_output_path(output_dir)
        self.input_benign = benign
        self.allow_overwrite = force
        self.payload_size = payload_size
        self.max_iterations = max_iterations
        self.initialization_method = initialization_method
        self.epsilon = epsilon
        self.y_target = TARGET_BENIGN
        if self.input_benign:
            self.y_target = TARGET_MALICIOUS

        # Database
        self.db_orig_file_id = None
        self.db_adv_file_id = None
        self.attack_config_id = None

        # Input File
        self.x = None
        self.x_len = 0
        self.x_hash = None
        self.x_code_hash = None
        self.x_code_section_name = None
        self.x_embermalconv_score = 0

        # Output File
        self.x_new = None
        self.x_new_len = 0
        self.x_new_hash = None
        self.x_new_code_hash = None
        self.x_new_embermalconv_score = 0

        # Results
        self.z_new_embermalconv_score = 0
        self.processable = True
        self.success = False
        self.evades_predetection = False
        self.payload_byte_distribution = None
        self.iterations = 0
        self.duration = 0
        self.reconstruction_duration = 0

        # Validate File Paths
        self.valid = self.validate()

    def _generate_output_path(self, output_dir):
        '''
        Output file will be the same as the input filename, but 
        include '.adv' to signify that it's adversarial.

        E.g., sample.bin -> sample.adv.bin
        E.g., sample.exe -> sample.adv.exe
        E.g., sample -> sample.adv
        '''
        p = Path(self.input_path)
        name = p.stem + '.adv' + ''.join(p.suffixes)
        return os.path.join(output_dir, name)

    def validate(self):
        if self._validate_input_file() == False:
            return False
        if self._validate_output_file() == False:
            return False
        return True

    def _validate_input_file(self):
        if os.path.exists(self.input_path) == False:
            print(f'File path does not exist: {self.input_path}')
            return False
        if os.path.isfile(self.input_path) == False:
            print(f'Path is a directory, not a file: {self.input_path}')
            return False
        if os.access(self.input_path, os.R_OK) == False:
            print(f'Insufficient permission to access file: {self.input_path}')
            return False
        if is_pe_file(self.input_path) == False:
            print(f'File is not in Windows PE format: {self.input_path}')
            return False
        return True

    def _validate_output_file(self):
        if os.path.exists(self.output_path):
            if os.path.isfile(self.output_path):
                if os.access(self.output_path, os.W_OK) == False:
                    print(f'Insufficient permission to overwrite existing file: \'{self.output_path}\'.')
                    return False
                elif self.allow_overwrite == False:
                    print(f'The output file already exists, and the --preserve flag was specified. Path: \'{self.output_path}\'.')
                    return False
                else:
                    return True
            else:
                print(f'Specified output file exists as a directory: \'{self.output_path}\'.')
                return False
        directory = os.path.dirname(os.path.abspath(self.output_path))
        if os.access(directory, os.W_OK | os.X_OK) == False:
            print(f'Insufficient permission to create output file in directory: \'{directory}\'.')
            return False
        return True

    def read(self):
        self.x = read_file_bytes(self.input_path)
        self.x_len = len(self.x)
        self.x_hash = hash_bytes(self.x)
        self.x_code_hash, self.x_code_section_name = code_section_hash(self.x)

    def write(self):
        write_file_bytes(self.output_path, self.x_new)

    def free(self):
        '''
        After processing is completed and the new file is saved, free up the file's
        raw bytes to save memory before iterating to the next sample. Keep the results though.
        '''
        self.x = None
        self.x_new = None