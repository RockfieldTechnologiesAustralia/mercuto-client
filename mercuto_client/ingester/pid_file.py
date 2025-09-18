import atexit
import logging
from pathlib import Path

from zc.lockfile import LockFile  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class PidFile:
    def __init__(self, lock_file: Path | None = None, content_template='{pid}'):
        self.content_template = content_template
        self.lock_path = Path(lock_file) if lock_file else None
        self.lock: LockFile | None = None

    def __cleanup(self):
        if self.lock_path is not None:
            self.lock_path.unlink(missing_ok=True)

    def __enter__(self):
        if self.lock_path is not None:
            self.lock = LockFile(self.lock_path, content_template=self.content_template)
            logger.warning(f'Created lock file {self.lock}')
            atexit.register(self.__cleanup)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock is not None:
            self.lock.close()
            self.lock = None
            self.__cleanup()
            atexit.unregister(self.__cleanup)
