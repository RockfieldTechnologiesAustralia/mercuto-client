import tempfile
from pathlib import Path
from urllib.parse import urlparse

# import mockssh  # type: ignore[import-untyped]
# import paramiko
import pytest
# from paramiko import PasswordRequiredException

from mercuto_client.ingester.backup import FileBackup, CSCPBackup


def test_file_backup():
    with tempfile.TemporaryDirectory() as temp_dir:
        uri = Path(temp_dir).as_uri()
        bak = FileBackup(urlparse(uri))
        assert bak.process_file(__file__)


def test_file_backup_does_not_exist_create_it():
    test_dir = Path('/tmp/test_dir')
    already_exists = test_dir.exists()
    try:
        test_url = urlparse(test_dir.as_uri())
        test_url = test_url._replace(query="create=true")
        uri = test_url.geturl()
        if already_exists:
            raise AssertionError(f"test_dir {str(test_dir)} already exists")
        bak = FileBackup(urlparse(uri))
        bak.process_file(__file__)
        dest = test_dir / Path(__file__).name
        assert test_dir.exists()
        assert dest.exists()
        dest.unlink()
    finally:
        if not already_exists:
            test_dir.rmdir()


def test_file_backup_does_not_exist():
    with pytest.raises(ValueError, match="backup path does not exist"):
        uri = Path('/I/DO/NOT/EXIST').as_uri()
        FileBackup(urlparse(uri))


# @dataclass
# class SSHUser:
#     username: str
#     private_key: Path
#     public_key: Path
#
#
# @pytest.fixture
# def ssh_user(username="test_user"):
#     with tempfile.TemporaryDirectory() as tmpdir:
#         temp_dir_path = Path(tmpdir)
#         private_key_path = temp_dir_path / "id_rsa"
#         public_key_path = temp_dir_path / "id_rsa.pub"
#         private_key = paramiko.RSAKey.generate(bits=4096)
#         with open(private_key_path, "w") as f:
#             private_key.write_private_key(f)
#         with open(public_key_path, "w") as f:
#             print(f'ssh-rsa {private_key.get_base64()}', file=f)
#         yield SSHUser(username, private_key_path, public_key_path)
#
#
# @pytest.fixture
# def ssh_server(ssh_user):
#     users = {
#         ssh_user.username: ssh_user.private_key,
#     }
#     with mockssh.Server(users) as s:
#         yield s
#
#
# def test_scp_backup_no_user(ssh_server, ssh_user):
#     with pytest.raises(PasswordRequiredException, match="Private key file is encrypted"):
#         SCPBackup(urlparse(f"scp://localhost:{ssh_server.port}{ssh_user.private_key.parent}?private_key={ssh_user.private_key}"))
#
#
# def test_scp_backup(ssh_server, ssh_user):
#     backup = SCPBackup(urlparse(
#         f"scp://{ssh_user.username}@localhost:{ssh_server.port}{ssh_user.private_key.parent}?private_key={ssh_user.private_key}"))
#     assert backup.process_file(__file__)
#
#
# def test_scp_backup_with_command(ssh_server, ssh_user):
#     backup = SCPBackup(urlparse(
#         f"scp://{ssh_user.username}@localhost:{ssh_server.port}{ssh_user.private_key.parent}"
#         f"?private_key={ssh_user.private_key}&script=cat {{destination}}"))
#     assert backup.process_file(__file__)

def test_cscp_backup_with_command(ssh_server, ssh_user):
    backup = CSCPBackup(urlparse(
        f"cscp://localhost:{ssh_user.private_key.parent}"
        f"?script=cat {{destination}}"))
    assert backup.process_file(__file__)
