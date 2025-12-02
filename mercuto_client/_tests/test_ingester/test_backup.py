import tempfile
from pathlib import Path
from urllib.parse import urlparse

import pytest

from ...ingester.backup import FileBackup


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
