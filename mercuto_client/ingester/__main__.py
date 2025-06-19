import argparse
import fnmatch
import itertools
import logging
import logging.handlers
import os
import sys
import time
from typing import Callable, TypeVar

import schedule

from .. import MercutoClient, MercutoHTTPException
from ..types import DataSample
from .ftp import simple_ftp_server
from .parsers import detect_parser
from .processor import FileProcessor
from .util import batched, get_free_space_excluding_files, get_my_public_ip

logger = logging.getLogger(__name__)

NON_RETRYABLE_ERRORS = {400, 404, 409}  # HTTP status codes that indicate non-retryable errors


class MercutoIngester:
    def __init__(self, project_code: str, api_key: str, hostname: str = 'https://api.rockfieldcloud.com.au') -> None:
        self._client = MercutoClient(url=hostname)
        self._api_key = api_key
        with self._client.as_credentials(api_key=api_key) as client:
            self._project = client.projects().get_project(project_code)
            assert self._project['code'] == project_code

            self._secondary_channels = client.channels().get_channels(project_code, classification='SECONDARY')
            self._datatables = list(itertools.chain.from_iterable([dt['datatables'] for dt in client.devices().list_dataloggers(project_code)]))

        self._channel_map = {c['label']: c['code'] for c in self._secondary_channels}

    def update_mapping(self, mapping: dict[str, str]) -> None:
        """
        Update the channel label to channel code mapping.
        """
        self._channel_map.update(mapping)
        logger.info(f"Updated channel mapping: {self._channel_map}")

    @property
    def project_code(self) -> str:
        return self._project['code']

    def ping(self) -> None:
        """
        Ping the Mercuto serverto update the last seen IP address.
        """
        ip = get_my_public_ip()
        with self._client.as_credentials(api_key=self._api_key) as client:
            client.projects().ping_project(self.project_code, ip_address=ip)
            logging.info(f"Pinged Mercuto server from IP: {ip} for project: {self.project_code}")

    def matching_datatable(self, filename: str) -> str | None:
        """
        Check if any datatables on the project match this file name.
        Returns the datatable code if a match is found, otherwise None.
        """
        basename = os.path.basename(filename)

        def matches(test: str) -> bool:
            """
            test should be a pattern or a filename.
            E.g. "my_data.csv" or "my_data*.csv", or "/path/to/my_data*.csv"
            Do wildcard matching as well as prefix matching.
            """
            test_base = os.path.basename(test)
            if fnmatch.fnmatch(basename, test_base):
                return True
            lhs, _ = os.path.splitext(test_base)
            if basename.startswith(lhs):
                return True
            return False

        for dt in self._datatables:
            # Match using datatable pattern
            if matches(dt['name']):
                return dt['code']
            if dt['src'] and matches(dt['src']):
                return dt['code']
        return None

    def _upload_samples(self, samples: list[DataSample]) -> bool:
        """
        Upload samples to the Mercuto project.
        """
        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                for batch in batched(samples, 500):
                    client.data().upload_samples(batch)
            return True
        except MercutoHTTPException as e:
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False

    def _upload_file(self, file_path: str, datatable_code: str) -> bool:
        """
        Upload a file to the Mercuto project.
        """
        logging.info(f"Uploadeding file {file_path} to datatable {datatable_code} in project {self.project_code}")
        try:
            with self._client.as_credentials(api_key=self._api_key) as client:
                client.data().upload_file(
                    project=self.project_code,
                    datatable=datatable_code,
                    file=file_path,
                )
            return True
        except MercutoHTTPException as e:
            if e.status_code in NON_RETRYABLE_ERRORS:
                logger.exception(
                    "Error indicates bad file that should not be retried. Skipping.")
                return True
            else:
                return False

    def process_file(self, file_path: str) -> bool:
        """
        Process the received file.
        """
        logging.info(f"Processing file: {file_path}")
        datatable_code = self.matching_datatable(file_path)
        if datatable_code:
            logger.info(f"Matched datatable code: {datatable_code} for file: {file_path}")
            return self._upload_file(file_path, datatable_code)
        else:
            parser = detect_parser(file_path)
            samples = parser(file_path, self._channel_map)
            if not samples:
                logging.warning(f"No samples found in file: {file_path}")
                return True
            return self._upload_samples(samples)


T = TypeVar('T')


def call_and_log_error(func: Callable[[], T]) -> T | None:
    """
    Call a function and log any exceptions that occur.
    """
    try:
        return func()
    except Exception:
        logging.exception(f"Error in {func.__name__}")
        return None


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Mercuto Ingester CLI')
    parser.add_argument('-p', '--project', type=str,
                        required=True, help='Mercuto project code')
    parser.add_argument('-k', '--api-key', type=str,
                        required=True, help='API key for Mercuto')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-d', '--directory', type=str,
                        help='Directory to store ingested files. Default is a directory called `buffered-files` in the workdir.')
    parser.add_argument('-s', '--size', type=int,
                        help='Size in MB for total amount of files to store in the buffer. \
                            Default is 75% of the available disk space on the buffer partition excluding the directory itself', default=None)
    parser.add_argument('--max-attempts', type=int,
                        help='Maximum number of attempts to process a file before giving up. Default is 1000.',
                        default=1000)
    parser.add_argument('--workdir', type=str,
                        help='Working directory for the ingester. Default is ~/.mercuto-ingester',)
    parser.add_argument('--logfile', type=str,
                        help='Log file path. No logs written if not provided. Maximum of 4 log files of 1MB each will be kept.\
                            Default is log.txt in the workdir.')
    parser.add_argument('--mapping', type=str,
                        help='Path to a JSON file with channel label to channel code mapping.\
                            If not provided, the ingester will try to detect the channels from the project.',
                        default=None)
    parser.add_argument('--hostname', type=str,
                        help='Hostname to use for the Mercuto server. Default is "https://api.rockfieldcloud.com.au".',
                        default='https://api.rockfieldcloud.com.au')
    parser.add_argument('--clean',
                        help='Drop the database before starting. This will not remove any buffer files and will rescan them on startup.',
                        action='store_true')
    parser.add_argument('--username', type=str,
                        help='Username for the FTP server. Default is "logger".',
                        default='logger')
    parser.add_argument('--password', type=str,
                        help='Password for the FTP server. Default is "password".',
                        default='password')
    parser.add_argument('--port', type=int,
                        help='Port for the FTP server. Default is 2121.',
                        default=2121)
    parser.add_argument('--no-rename', action='store_true',
                        help='Add the current timestamp to the end of the files received via FTP. \
                        This is useful to avoid overwriting files with the same name.')

    args = parser.parse_args()

    if args.workdir is None:
        workdir = os.path.join(os.path.expanduser('~'), ".mercuto-ingester")
    else:
        workdir = args.workdir
        if not os.path.exists(args.workdir):
            raise ValueError(f"Work directory {args.workdir} does not exist")
    os.makedirs(workdir, exist_ok=True)

    if args.verbose:
        level = logging.DEBUG
    else:
        level = logging.INFO

    handlers: list[logging.Handler] = []
    handlers.append(logging.StreamHandler(sys.stderr))

    if args.logfile is not None:
        logfile = args.logfile
    else:
        logfile = os.path.join(workdir, 'log.txt')
    handlers.append(logging.handlers.RotatingFileHandler(
        logfile, maxBytes=1000000, backupCount=3))

    logging.basicConfig(format='[PID %(process)d] %(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                        datefmt='%d/%m/%Y %H:%M:%S',
                        level=level,
                        handlers=handlers)

    if args.directory is None:
        buffer_directory = os.path.join(workdir, "buffered-files")
    else:
        buffer_directory = args.directory
    os.makedirs(buffer_directory, exist_ok=True)

    ftp_dir = os.path.join(workdir, 'temp-ftp-data')
    os.makedirs(ftp_dir, exist_ok=True)

    size = args.size
    if size is None:
        size = get_free_space_excluding_files(buffer_directory) * 0.75 // (1024 * 1024)  # Convert to MB
        logging.info(f"Buffer size set to {size} MB based on available disk space.")

    if args.mapping is not None:
        import json
        with open(args.mapping, 'r') as f:
            mapping = json.load(f)
        if not isinstance(mapping, dict):
            raise ValueError(f"Mapping file {args.mapping} must contain a JSON object")
    else:
        mapping = {}

    logger.info(f"Using work directory: {workdir}")

    database_path = os.path.join(workdir, "buffer.db")
    if args.clean and os.path.exists(database_path):
        logging.info(f"Dropping existing database at {database_path}")
        os.remove(database_path)

    ingester = MercutoIngester(
        project_code=args.project,
        api_key=args.api_key,
        hostname=args.hostname)

    ingester.update_mapping(mapping)

    processor = FileProcessor(
        buffer_dir=buffer_directory,
        db_path=database_path,
        process_callback=ingester.process_file,
        max_attempts=args.max_attempts,
        free_space_mb=size)

    processor.scan_existing_files()

    with simple_ftp_server(directory=buffer_directory,
                           username=args.username, password=args.password, port=args.port,
                           callback=processor.add_file_to_db, rename=not args.no_rename,
                           workdir=workdir):
        schedule.every(60).seconds.do(call_and_log_error, ingester.ping)
        schedule.every(5).seconds.do(call_and_log_error, processor.process_next_file)
        schedule.every(2).minutes.do(call_and_log_error, processor.cleanup_old_files)

        while True:
            schedule.run_pending()
            time.sleep(0.5)
