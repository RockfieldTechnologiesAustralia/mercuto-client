import logging
import shutil
import subprocess
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path, PosixPath
from typing import Any, Callable, Optional
from urllib.parse import ParseResult, parse_qs, unquote

import requests

logger = logging.getLogger(__name__)


class IBackupHandler(ABC):
    """
    Abstract base class for backup handlers.
    """

    def __init__(self, url: ParseResult):
        self.url = url
        self.validate_url()
        logger.debug(f'{self} backup location set to: {url.geturl()}')

    def __call__(self, filename: str) -> bool:
        """
        Provide a callable interface to process a file.
        :param filename: The file to process.
        """
        try:
            result = self.process_file(filename)
            if not result:
                logger.error(f"{self} Failed to process {filename}")
            else:
                logger.debug(f"{self} processed {filename}")
            return result
        except Exception:
            return False

    def decode_query(self) -> dict[str, Any]:
        """
        Decodes the query parameters from the URL.
        :return: A dictionary of query parameters (e.g. http://example.com?param1=value1 ==> {'param1': 'value1'})
        """
        return parse_qs(unquote(self.url.query))

    def validate_url(self):
        """
        Validates the URL components.
         Raises an exception if the URL is invalid.

        Should be implemented by subclasses
        """
        pass

    @abstractmethod
    def process_file(self, filename: str) -> bool:
        """
        Processes the given file.
        Should be implemented by subclasses.
        """
        raise NotImplementedError()


class CSCPBackup(IBackupHandler):
    """
    Compressed SCP Backup handler (cscp://).
    Uses SCP to copy files to a remote server, with optional post-transfer script execution.
    Use query parameters to specify additional options:
    - private_key: Path to the private key file for authentication.
    - script: A script to run on the remote server after file transfer. The script can use
      the placeholder '{destination}' to refer to the path of the transferred file.
    """
    @dataclass
    class SCPBackupParams:
        private_key: Optional[Path] = None
        script: Optional[str] = None

        @staticmethod
        def load(config: dict[str, Any]) -> 'CSCPBackup.SCPBackupParams':
            """
            Loads SCPBackupParams from a configuration dictionary.
            :param config: Configuration dictionary.
            :return: An instance of CSCPBackup.SCPBackupParams.
            """
            return CSCPBackup.SCPBackupParams(**config)

        @staticmethod
        def load_qs(query: dict[str, Any]) -> 'CSCPBackup.SCPBackupParams':
            """
            Load SCPBackupParams from a query string dictionary.
            :param query: Query string dictionary.
            """
            result: dict[str, Any] = {}
            keys = list(query.keys())
            known_keys = ['private_key', 'script']
            for _key in known_keys:
                if _key in query:
                    if len(query[_key]) > 1:
                        raise RuntimeError(f"Multiple {_key} entries found")
                    result[_key] = query[_key][0]
                    keys.remove(_key)
            if len(keys) > 0:
                raise RuntimeError(f"Unknown key {keys}")

            return CSCPBackup.SCPBackupParams.load(result)

    def __init__(self, url: ParseResult):
        self.params: Optional[CSCPBackup.SCPBackupParams] = None
        super().__init__(url)

    def validate_url(self):
        if self.url.hostname is None:
            raise RuntimeError("No hostname specified for backup")
        query = self.decode_query()
        self.params = CSCPBackup.SCPBackupParams.load_qs(query)

    def process_file(self, filename: str) -> bool:
        if self.send_file(filename):
            return self.run_script(filename)

        return False

    def send_file(self, filename: str) -> bool:
        command = ['scp', '-oBatchMode=yes']
        dest = ""
        if self.url.username is not None:
            dest = f"{self.url.username}@"

        dest = f'{dest}{self.url.hostname}'

        port = 22
        if self.url.port is not None:
            port = self.url.port

        command.append('-P')
        command.append(str(port))

        if self.params is not None:
            if self.params.private_key is not None:
                command.append('-i')
                command.append(str(self.params.private_key))

        dest = f'{dest}:{self.url.path}'

        command.append(filename)
        command.append(dest)

        try:
            logger.debug(f'Copy Command: {" ".join(command)}')
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.debug(f"STDOUT: {result.stdout.decode("utf-8", errors='ignore')}")
            logger.debug(f"STDERR: {result.stderr.decode("utf-8", errors='ignore')}")
            return result.returncode == 0

        except subprocess.CalledProcessError as e:
            print(e.stdout.decode("utf-8"), file=sys.stderr)
            print(e.stderr.decode("utf-8"), file=sys.stderr)
            return False

    def run_script(self, filename: str) -> bool:
        if self.params is None:
            return True
        elif self.params.script is None:
            return True
        else:
            command = ['ssh', '-oBatchMode=yes']
            if self.url.username is not None:
                command.append('-l')
                command.append(self.url.username)

            port = 22
            if self.url.port is not None:
                port = self.url.port

            command.append('-p')
            command.append(str(port))

            if self.params.private_key is not None:
                command.append('-i')
                command.append(str(self.params.private_key))

            if self.url.hostname is None:
                raise RuntimeError("No hostname specified for backup")
            command.append(self.url.hostname)

            dest_folder = PosixPath(self.url.path)
            fn = Path(filename)

            command.append(self.params.script.format(destination=dest_folder / fn.name))
            logger.debug(f'Script Command: {" ".join(command)}')
        try:
            logger.debug(f'Script Command: {" ".join(command)}')
            result = subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            logger.debug(f"STDOUT: {result.stdout.decode("utf-8", errors='ignore')}")
            logger.debug(f"STDERR: {result.stderr.decode("utf-8", errors='ignore')}")
            return result.returncode == 0

        except subprocess.CalledProcessError as e:
            print(e.stdout.decode("utf-8"), file=sys.stderr)
            print(e.stderr.decode("utf-8"), file=sys.stderr)
            return False


class FileBackup(IBackupHandler):
    """
    File Backup handler (file://)
    Copies files to a specified local directory.
    """

    def __init__(self, url: ParseResult):
        self.backup_path: Optional[Path] = None
        super().__init__(url)

    def validate_url(self):
        if self.url.scheme.lower() != 'file':
            raise ValueError(f"{self} url scheme must be 'file'")
        self.backup_path = Path(unquote(self.url.path))
        if not self.backup_path.exists():
            query = self.decode_query()
            create = False
            if 'create' in query:
                create = query['create']
                if len(create) != 1:
                    raise ValueError(f"{self} create query element has wrong length: {len(create)}, expected 1")
                create = create[0].lower()
                if create in ['true', 'yes', 'y']:
                    create = True
            if create:
                self.backup_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created backup path: {self.backup_path}")
            else:
                raise ValueError(f"{self.backup_path} backup path does not exist")
        if not self.backup_path.is_dir():
            raise ValueError(f"{self.backup_path} backup path must be a directory")

    def process_file(self, filename: str) -> bool:
        if self.backup_path is None:
            raise RuntimeError("No backup path specified")

        dest = self.backup_path / Path(filename).name
        shutil.copyfile(filename, dest)
        return True


class HTTPBackup(IBackupHandler):
    """
    HTTP Backup handler (http:// or https://).
    Uses HTTP POST to send files to a specified URL.
    """

    def validate_url(self):
        if self.url.scheme.lower() not in ['http', 'https']:
            raise ValueError(f"{self} url scheme must be 'http' or 'https'")

    def _process_file(self, filename: str) -> tuple[bool, int]:
        with open(filename, "rb") as f:
            files = {"file": (Path(filename).name, f, "text/plain")}
            response = requests.post(self.url.geturl(), files=files)
            response_data = response.json()
            result = response_data.get('result', False)

            logger.debug(f"HTTP Response: {response.status_code} - {response_data}")
            return result, response.status_code

    def process_file(self, filename: str) -> bool:
        result, status_code = self._process_file(filename)
        return result and status_code == 200


def get_backup_handler(url: ParseResult) -> Callable[[str], bool]:
    match url.scheme.lower():
        case "file":
            return FileBackup(url)
        case "http":
            return HTTPBackup(url)
        case "https":
            return HTTPBackup(url)

        # case "scp":
        #     return SCPBackup(url)
        # case "cscp":
        #     return CSCPBackup(url)

        case _:
            raise RuntimeError(f"Unsupported scheme: {url.scheme}")
