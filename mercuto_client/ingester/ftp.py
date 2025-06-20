import contextlib
import logging
import os
import shutil
import tempfile
import threading
from datetime import datetime, timezone
from typing import Callable, Iterator, Optional

from pyftpdlib import authorizers  # type: ignore[import-untyped]
from pyftpdlib.handlers import FTPHandler  # type: ignore[import-untyped]
from pyftpdlib.servers import FTPServer  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


@contextlib.contextmanager
def simple_ftp_server(directory: str,
                      username: str,
                      password: str,
                      port: int = 2121,
                      callback: Optional[Callable[[str], None]] = None,
                      workdir: Optional[str] = None,
                      rename: bool = True,
                      clock: Optional[Callable[[], datetime]] = None) -> Iterator[None]:
    """
    Wrapper for a simple FTP server that allows uploading files to a specified directory.
    Callback function can be provided which is called with the destination path of each uploaded file.
    Files are first uploaded to a workdirectory and then moved to the specified directory.
    If workdir is not specified, a temporary directory is used.

    :param directory: Directory where files will be uploaded.
    :param username: Username for FTP authentication.
    :param password: Password for FTP authentication.
    :param port: Port on which the FTP server will listen.
    :param callback: Optional callback function that is called with the destination path of each uploaded file.
    :param workdir: Optional working directory where files are initially uploaded before moving to the final directory.
    :param rename: If True, appends a timestamp to the filename to avoid overwriting existing files.
    :param clock: Function to get the current time, defaults to datetime.now with timezone UTC
    :return: Context manager that starts the FTP server and allows file uploads.

    Runs in a background thread during context manager usage.

    Example usage:

    ```python
    def my_callback(dest_path: str):
        print(f"File uploaded to: {dest_path}")

    with simple_ftp_server('/path/to/upload/dir', 'user', 'pass', port=2121, callback=my_callback) as server:
        # Your code here, e.g. processing files
        while True:
            time.sleep(10)
    ```
    """

    if clock is None:
        def clock(): return datetime.now(timezone.utc)

    def rename_file(file_path: str) -> str:
        """
        Rename the file by appending a timestamp to avoid overwriting.
        Adds the timestamp before the file extension.
        """
        base, ext = os.path.splitext(file_path)
        timestamp = clock().strftime("%Y%m%dT%H%M%S")
        new_name = f"{base}_{timestamp}{ext}"
        return new_name

    class CustomFTPHandler(FTPHandler):
        def on_file_received(self, file):
            target = os.path.join(directory, os.path.basename(file))

            if rename:
                target = rename_file(target)

            dest = shutil.move(file, target)
            if callback:
                callback(dest)

        def on_incomplete_file_received(self, file):
            try:
                os.remove(file)
            except Exception:
                logger.exception(f"Failed to remove incomplete file: {file}")

    if workdir is None:
        workdir_ctx: contextlib.AbstractContextManager[str] = tempfile.TemporaryDirectory(prefix="ftp_workdir_")
    else:
        workdir_ctx = contextlib.nullcontext(workdir)

    with workdir_ctx as workdir:
        authorizer = authorizers.DummyAuthorizer()
        authorizer.add_user(username, password,
                            workdir, perm='lwe')
        handler = CustomFTPHandler
        handler.authorizer = authorizer
        handler.banner = "FTP Server Ready."
        handler.passive_ports = range(60000, 65535)

        address = ('0.0.0.0', port)
        server = FTPServer(address, handler)
        server.max_cons = 60
        server.max_cons_per_ip = 20

        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        logger.debug(f"Starting FTP server on {port}...")
        server_thread.start()
        try:
            yield
        finally:
            logger.debug("Stopping FTP server...")
            server.close_all()
            server_thread.join(timeout=10)
            logger.debug("FTP server stopped.")
