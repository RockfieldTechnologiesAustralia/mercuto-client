import argparse
import logging
import logging.handlers
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any, Callable, Optional, TypeVar
from urllib.parse import ParseResult, urlparse

import schedule

from ..util import get_free_space_excluding_files
from .backup import get_backup_handler
from .ftp import simple_ftp_server
from .mercuto import MercutoIngester
from .pid_file import PidFile
from .processor import FileProcessor

logger = logging.getLogger(__name__)


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


class Status:
    """
    Status class to handle running state of the ingester.
    """

    def __init__(self):
        self.running = True

    def stop(self, code: Any, frame: Any):
        self.running = False
        print("Stopping")

    def is_running(self):
        return self.running


def launch_mercuto_ingester(
    project: str,
    api_key: str,
    hostname: str = 'https://api.rockfieldcloud.com.au',
    verify_ssl: bool = True,
    pid_file: Optional[Path] = None,
    workdir: Optional[str] = '~/.mercuto-ingester',
    verbose: bool = False,
    logfile: Optional[str] = None,
    directory: Optional[str] = None,
    target_free_space_mb: Optional[float] = None,
    max_files: Optional[int] = None,
    mapping: Optional[str] = None,
    clean: bool = False,
    ftp_server_username: str = 'logger',
    ftp_server_password: str = 'password',
    ftp_server_port: int = 2121,
    ftp_server_rename: bool = True,
    max_attempts: int = 1000,
    backup_location: Optional[list[ParseResult]] = None,
    timezone: Optional[str] = None,
    camera: Optional[str] = None
):

    if backup_location is None:
        backup_location = []

    with PidFile(pid_file):
        if workdir is None:
            workdir = os.path.join(os.path.expanduser('~'), ".mercuto-ingester")
        elif workdir.startswith("~"):
            workdir = os.path.expanduser(workdir)
        else:
            workdir = workdir
            if not os.path.exists(workdir):
                raise ValueError(f"Work directory {workdir} does not exist")

        os.makedirs(workdir, exist_ok=True)

        if verbose:
            level = logging.DEBUG
        else:
            level = logging.INFO

        handlers: list[logging.Handler] = []
        handlers.append(logging.StreamHandler(sys.stderr))

        if logfile is not None:
            logfile = logfile
        else:
            logfile = os.path.join(workdir, 'log.txt')
        handlers.append(logging.handlers.RotatingFileHandler(
            logfile, maxBytes=1000000, backupCount=3))

        logging.basicConfig(format='[PID %(process)d] %(asctime)s,%(msecs)d %(name)s %(levelname)s %(message)s',
                            datefmt='%d/%m/%Y %H:%M:%S',
                            level=level,
                            handlers=handlers)

        if directory is None:
            buffer_directory = os.path.join(workdir, "buffered-files")
        else:
            buffer_directory = directory
        os.makedirs(buffer_directory, exist_ok=True)

        ftp_dir = os.path.join(workdir, 'temp-ftp-data')
        os.makedirs(ftp_dir, exist_ok=True)

        if target_free_space_mb is None and max_files is None:
            target_free_space_mb = get_free_space_excluding_files(buffer_directory) * 0.25 // (1024 * 1024)  # Convert to MB
            logging.info(f"Target remaining free space set to {target_free_space_mb} MB based on available disk space.")

            if target_free_space_mb <= 1:
                raise ValueError("Not enough free space on the buffer partition to set a reasonable target free space. "
                                 "Please specify either a larger buffer directory or set the target free space or max files manually.")

        logger.info(f"Using work directory: {workdir}")

        database_path = os.path.join(workdir, "buffer.db")
        if clean and os.path.exists(database_path):
            logging.info(f"Dropping existing database at {database_path}")
            os.remove(database_path)

        ingester = MercutoIngester(
            project_code=project,
            api_key=api_key,
            hostname=hostname,
            verify_ssl=verify_ssl,
            timezone=timezone,
            camera_code=camera
        )

        if mapping is not None:
            import json
            with open(mapping, 'r') as f:
                mapping = json.load(f)
            if not isinstance(mapping, dict):
                raise ValueError(f"Mapping file {mapping} must contain a JSON object")
            ingester.update_mapping(mapping)

        pre_processing_handlers: list[Callable[[str], bool]] = [get_backup_handler(loc) for loc in backup_location]
        processor_callbacks: list[Callable[[str], bool]] = [ingester.process_file]
        post_processing_handlers: list[Callable[[str], bool]] = []

        all_handlers = pre_processing_handlers + processor_callbacks + post_processing_handlers

        processor = FileProcessor(
            buffer_dir=buffer_directory,
            db_path=database_path,
            process_callback=lambda filename: all(handler(filename) for handler in all_handlers),
            max_attempts=max_attempts,
            target_free_space_mb=target_free_space_mb,
            max_files=max_files)

        processor.scan_existing_files()

        with simple_ftp_server(directory=buffer_directory,
                               username=ftp_server_username, password=ftp_server_password, port=ftp_server_port,
                               callback=processor.add_file_to_db, rename=ftp_server_rename,
                               workdir=ftp_dir):
            call_and_log_error(ingester.ping)
            schedule.every(60).seconds.do(call_and_log_error, ingester.ping)  # type: ignore[attr-defined]
            schedule.every(5).seconds.do(call_and_log_error, processor.process_next_file)  # type: ignore[attr-defined]
            schedule.every(2).minutes.do(call_and_log_error, processor.cleanup_old_files)  # type: ignore[attr-defined]

            status = Status()
            signal.signal(signal.SIGTERM, status.stop)

            while status.is_running():
                schedule.run_pending()
                sleep_period = schedule.idle_seconds()
                if sleep_period is None or sleep_period < 0:
                    sleep_period = 0
                # We need to wake up to handle ctrl-c etc
                if sleep_period > 1:
                    sleep_period = 1
                time.sleep(sleep_period)

            logger.warning("Shutting Down...")


def main():
    parser = argparse.ArgumentParser(description='Mercuto Ingester CLI')
    parser.add_argument('-p', '--project', type=str,
                        required=True, help='Mercuto project code')
    parser.add_argument('-k', '--api-key', type=str,
                        required=True, help='API key for Mercuto')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Enable verbose output')
    parser.add_argument('-d', '--directory', type=str,
                        help='Directory to store ingested files. Default is a directory called `buffered-files` in the workdir.')
    parser.add_argument('-s', '--target-free-space-mb', type=int,
                        help='Size in MB for total amount of remaining free space to keep available. \
                            Default is 25% of the available disk space on the buffer partition excluding the directory itself', default=None)
    parser.add_argument('--max-files', type=int,
                        help='Maximum number of files to keep in the buffer. Default is to use the size param.', default=None)
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
    parser.add_argument('-i', '--insecure', action="store_true",
                        help='Disable SSL verification',
                        default=False)
    parser.add_argument('-b', '--backup-location', action="append",
                        help='Backup location to store ingested files. Must be a valid URL, e.g. scp://user@host/path. '
                        'Can be specified multiple times.',
                        type=urlparse)
    parser.add_argument('-e', '--pid-file', help='Ths location to create the PID file', type=Path, default=None)
    parser.add_argument('--timezone', type=str,
                        help='Timezone to use for data uploads (e.g. "Australia/Melbourne"). \
                        If not provided, no timezone will be sent on uploads. \
                        Only needed if data files do not contain timezone information (E.g. Campbell Scientific loggers).',
                        default=None)
    parser.add_argument('--camera', type=str,
                        help='Camera code to associate with image uploads. If not provided, image files will error on upload.',
                        default=None)

    args = parser.parse_args()

    launch_mercuto_ingester(
        project=args.project,
        api_key=args.api_key,
        verify_ssl=not args.insecure,
        pid_file=args.pid_file,
        workdir=args.workdir,
        verbose=args.verbose,
        logfile=args.logfile,
        directory=args.directory,
        target_free_space_mb=args.target_free_space_mb,
        max_files=args.max_files,
        mapping=args.mapping,
        clean=args.clean,
        ftp_server_username=args.username,
        ftp_server_password=args.password,
        ftp_server_port=args.port,
        ftp_server_rename=not args.no_rename,
        max_attempts=args.max_attempts,
        backup_location=args.backup_location,
        hostname=args.hostname,
        timezone=args.timezone,
        camera=args.camera
    )


if __name__ == '__main__':
    main()
