import logging

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path, PosixPath
from typing import Callable, Optional
from urllib.parse import ParseResult, parse_qs, unquote

import requests

logger = logging.getLogger(__name__)


class Backup:
    def __init__(self, url: ParseResult):
        self.url = url
        self.validate_url()
        logger.debug(f'{self} backup location set to: {url.geturl()}')

    def __call__(self, filename: str) -> bool:
        try:
            result = self.process_file(filename)
            if not result:
                logger.error(f"{self} Failed to process {filename}")
            else:
                logger.debug(f"{self} processed {filename}")
            return result
        except Exception:
            return False

    def decode_query(self):
        return parse_qs(unquote(self.url.query))

    def validate_url(self):
        pass

    def process_file(self, filename: str) -> bool:
        raise NotImplementedError()


@dataclass
class SCPBackupParams:
    private_key: Optional[Path] = None
    script: Optional[str] = None

    @staticmethod
    def load(config: dict) -> 'SCPBackupParams':
        return SCPBackupParams(**config)

    @staticmethod
    def load_qs(query: dict) -> 'SCPBackupParams':
        result = {}
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

        return SCPBackupParams.load(result)


class CSCPBackup(Backup):
    def __init__(self, url: ParseResult):
        self.params: Optional[SCPBackupParams] = None
        super().__init__(url)

    def validate_url(self):
        query = self.decode_query()
        self.params = SCPBackupParams.load_qs(query)

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

    def run_script(self, filename):
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

            if self.params is not None:
                if self.params.private_key is not None:
                    command.append('-i')
                    command.append(str(self.params.private_key))

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


class FileBackup(Backup):
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
                raise ValueError(f"{self} backup path does not exist")
        if not self.backup_path.is_dir():
            raise ValueError(f"{self} backup path must be a directory")

    def process_file(self, filename: str) -> bool:
        if self.backup_path is None:
            raise RuntimeError("No backup path specified")

        dest = self.backup_path / Path(filename).name
        shutil.copyfile(filename, dest)
        return True


class HTTPBackup(Backup):

    def process_file(self, filename: str) -> bool:
        with open(filename, "rb") as f:
            files = {"file": (Path(filename).name, f, "text/plain")}
            response = requests.post(self.url.geturl(), files=files)
            result = response.json().get('result', False)
            return result


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
        case "cscp":
            return CSCPBackup(url)

        case _:
            raise RuntimeError(f"Unsupported scheme: {url.scheme}")
