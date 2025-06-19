import ftplib
import io
import os
import tempfile
from datetime import datetime, timezone

from ...ingester.ftp import simple_ftp_server


def test_simple_ftp_server():
    receives = []
    def clock(): return datetime(2023, 10, 1, 12, 0, 0, tzinfo=timezone.utc)

    with tempfile.TemporaryDirectory() as temp_dir:
        with simple_ftp_server(directory=temp_dir,
                               username='test', password='password', port=2121,
                               callback=lambda dest: receives.append(dest), clock=clock):
            client = ftplib.FTP()
            client.connect('localhost', 2121)
            client.login('test', 'password')

            # Upload a test file
            testbuf = io.BytesIO(b'This is a test file.')
            client.storbinary('STOR test_file.txt', testbuf)

        assert len(receives) == 1
        assert receives[0].endswith('test_file_20231001T120000.txt')

        # Verify the file was uploaded correctly
        with open(receives[0], 'rb') as f:
            content = f.read()
            assert content == b'This is a test file.'

        # Ensure that the file exists in the temp directory
        found = os.listdir(temp_dir)
        assert 'test_file_20231001T120000.txt' in found
        assert len(found) == 1  # Only one file should be present
