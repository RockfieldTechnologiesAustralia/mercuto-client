import email
import hashlib
import tempfile
from email.message import Message

from io import BytesIO, StringIO
from pathlib import Path
from typing import BinaryIO
from urllib.parse import urlparse

import pytest
import requests
import requests_mock
from fastapi import APIRouter, UploadFile, FastAPI
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _Context

from mercuto_client.ingester.backup import FileBackup, CSCPBackup, HTTPBackup


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


class EnqueueResult(BaseModel):
    result: bool = Field(title="The result of the enqueuing attempt")
    sha512_hash: str = Field(title="The SHA512 sum of the received data")
    processed: bool = Field(title="The result of processing")


def sha512_hash_stream(stream: BinaryIO):
    sha512_hash = hashlib.sha512()
    chunk = stream.read(4096)
    while len(chunk) > 0:
        sha512_hash.update(chunk)
        chunk = stream.read(4096)
    return sha512_hash.hexdigest()


def http_api_endpoint():
    router = APIRouter()

    @router.get("/ping")
    async def ping() -> bool:
        return True

    @router.post("/enqueue")
    async def enqueue(file: UploadFile) -> EnqueueResult:
        filename = file.filename  # noqa: F841
        content_type = file.content_type  # noqa: F841
        contents = await file.read()
        data = BytesIO(contents)

        return EnqueueResult(
            result=True,
            sha512_hash=sha512_hash_stream(data),
            processed=True
        )
    app = FastAPI(
        title="Rockfield Mercuto Logger Duplicator",
        version="1.0.0",
        description="This API duplicates logger file across multiple disks",
    )
    app.include_router(router, prefix="", tags=["Duplicator"])
    return app


test_url = "http://test-server:9999"


@pytest.fixture
def http_test_client():
    with requests_mock.Mocker() as m:
        client = TestClient(http_api_endpoint())

        def ping(proxy: _RequestObjectProxy, context: _Context):
            result = client.get("/ping")
            context.status_code = result.status_code
            return result.json()

        def enqueue(proxy: _RequestObjectProxy, context: _Context):
            boundary = proxy.text.split('\r\n')[0].strip()[2:]
            data = StringIO()
            print("MIME-Version: 1.0", file=data, end='\r\n')
            print(f"Content-Type: multipart/form-data; boundary={boundary}", file=data, end='\r\n')
            print(file=data, end='\r\n')
            print(proxy.text, file=data, end='\r\n')
            msg = email.message_from_string(data.getvalue())
            files = {}
            if msg.is_multipart():
                for part in msg.get_payload():
                    if isinstance(part, Message):
                        name = part.get_param('name', header='content-disposition')
                        filename = part.get_param('filename', header='content-disposition')
                        content_type = part.get_content_type()
                        payload = part.get_payload()
                        if isinstance(payload, str):
                            files[name] = (filename, BytesIO(payload.encode('utf-8')), content_type)
                        if isinstance(payload, bytes):
                            files[name] = (filename, BytesIO(payload), content_type)
            result = client.post('/enqueue', files=files)
            context.status_code = result.status_code
            return result.json()

        m.get(f"{test_url}/ping", json=ping)
        m.post(f"{test_url}/enqueue", json=enqueue)

        yield client


@pytest.fixture
def http_test_client_simple_fail():
    with requests_mock.Mocker() as m:
        m.post(f"{test_url}/enqueue", json={
            "result": False,
            "sha512_hash": "xxxxxx",
            "processed": False,
        })
        yield m


def test_http_backup(http_test_client):
    assert HTTPBackup(urlparse(f'{test_url}/enqueue')).process_file(__file__)


def test_http_backup_fail(http_test_client_simple_fail):
    assert not HTTPBackup(urlparse(f'{test_url}/enqueue')).process_file(__file__)


class MockResponse:
    def __init__(self, result, status_code=200):
        self.status_code = status_code
        self.result = result
        self.request_url = None
        self.params = {}

    def __call__(self, *args, **kwargs):
        self.request_url = args[0]
        self.params = kwargs
        return self

    def json(self):
        return self.result


def test_http_backup_501(monkeypatch):
    result = {
            "result": False,
            "sha512_hash": "xxxxxx",
            "processed": False,
        }
    monkeypatch.setattr(requests, "post", MockResponse(result, status_code=501))
    monkeypatch.setattr(requests, "get", MockResponse(result))
    result = HTTPBackup(urlparse(f'{test_url}/enqueue'))._process_file(__file__)
    assert not result.result
    assert result.status_code == 501

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
