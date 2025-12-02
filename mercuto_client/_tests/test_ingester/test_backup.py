import os
import tempfile
from pathlib import Path
from threading import Thread
from typing import Iterator, TypedDict
from urllib.parse import urlparse

import pyftpdlib.authorizers  # type: ignore[import-untyped]
import pyftpdlib.handlers  # type: ignore[import-untyped]
import pyftpdlib.servers  # type: ignore[import-untyped]
import pytest

from ...ingester.backup import FileBackup, FTPBackup


def test_file_backup():
    with tempfile.TemporaryDirectory() as temp_dir:
        uri = Path(temp_dir).as_uri()
        bak = FileBackup(urlparse(uri))
        assert bak.process_file(__file__)


def test_file_backup_does_not_exist_create_it():
    with tempfile.TemporaryDirectory() as temp_dir:
        test_dir = Path(temp_dir) / "test_dir"
        uri = test_dir.as_uri() + "?create=true"
        assert not test_dir.exists()
        bak = FileBackup(urlparse(uri))
        assert bak.process_file(__file__)
        dest = test_dir / Path(__file__).name
        assert test_dir.exists()
        assert dest.exists()


def test_file_backup_does_not_exist():
    uri = (Path(__file__).parent / "I_DO_NOT_EXIST").as_uri()
    with pytest.raises(ValueError, match="backup path does not exist"):
        FileBackup(urlparse(uri))


class TestFTPServerConfig(TypedDict):
    host: str
    port: int
    user: str
    passwd: str
    ftp_root: str


@pytest.fixture(scope="function")
def mock_ftp_server() -> Iterator[TestFTPServerConfig]:
    # Create a temporary directory to act as the FTP root
    temp_dir = tempfile.TemporaryDirectory()
    ftp_root = temp_dir.name

    # Set up user authentication
    authorizer = pyftpdlib.authorizers.DummyAuthorizer()
    authorizer.add_user("user", "12345", ftp_root, perm="elradfmwMT")

    # Set up FTP handler
    handler = pyftpdlib.handlers.FTPHandler
    handler.authorizer = authorizer

    # Start the FTP server in a separate thread
    server = pyftpdlib.servers.FTPServer(("127.0.0.1", 0), handler)
    ip, port = server.socket.getsockname()

    server_thread = Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()

    yield {
        "host": ip,
        "port": port,
        "user": "user",
        "passwd": "12345",
        "ftp_root": ftp_root
    }

    server.close_all()
    temp_dir.cleanup()


def test_ftp_backup(mock_ftp_server: TestFTPServerConfig):
    url = f"ftp://{mock_ftp_server['user']}:{mock_ftp_server['passwd']}@{mock_ftp_server['host']}:{mock_ftp_server['port']}/my_dir?create=true"
    os.makedirs(Path(mock_ftp_server['ftp_root']) / "my_dir", exist_ok=True)
    bak = FTPBackup(urlparse(url))
    bak.process_file(__file__)
    assert bak.process_file(__file__)
    dest = Path(mock_ftp_server['ftp_root']) / "my_dir" / Path(__file__).name
    assert dest.exists()


def test_ftp_backup_fails_if_dir_not_exists(mock_ftp_server: TestFTPServerConfig):
    url = f"ftp://{mock_ftp_server['user']}:{mock_ftp_server['passwd']}@{mock_ftp_server['host']}:{mock_ftp_server['port']}/my_dir"
    bak = FTPBackup(urlparse(url))
    assert not bak.process_file(__file__)
    dest = Path(mock_ftp_server['ftp_root']) / "my_dir" / Path(__file__).name
    assert not dest.exists()
