import argparse
import atexit
import logging
import sys
from pathlib import Path

from zc.lockfile import LockError, LockFile  # type: ignore[import-untyped]

logger = logging.getLogger(__name__)


class PidFile:
    """
    Context manager for creating and removing a PID lock file.
    :param lock_file: Path to the lock file to create. If None, no lock file is created.
    :param content_template: Template for the content of the lock file. Default is '{pid}'.
    """

    def __init__(self, lock_file: Path | None = None, content_template: str = '{pid}'):
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

    def __exit__(self, exc_type: type | None, exc_val: BaseException | None, exc_tb: object | None) -> None:
        if self.lock is not None:
            self.lock.close()
            self.lock = None
            self.__cleanup()
            atexit.unregister(self.__cleanup)


def main():
    locked = 0
    unlocked = 1
    parser = argparse.ArgumentParser()
    parser.add_argument('pidfile', type=Path)

    args = parser.parse_args()
    if args.pidfile.exists():
        try:
            lock = LockFile(args.pidfile)
            lock.close()
            print(f"pid file '{args.pidfile}' is not locked", file=sys.stderr)

        except LockError:
            print(f"pid file '{args.pidfile}' is locked", file=sys.stderr)
            sys.exit(locked)

    else:
        print(f"pid file '{args.pidfile}' does not exist", file=sys.stderr)
    sys.exit(unlocked)


if __name__ == '__main__':
    main()
