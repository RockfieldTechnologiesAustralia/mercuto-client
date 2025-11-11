import itertools
import shutil
from datetime import timedelta
from pathlib import Path
from typing import Iterable, Iterator, TypeVar

import requests


def timedelta_isoformat(td: timedelta) -> str:
    """
    ISO 8601 encoding for Python timedelta object.
    Taken from pydantic source:
        https://github.com/pydantic/pydantic/blob/3704eccce4661455acdda1cdcf716bd4b3382e08/pydantic/deprecated/json.py#L135-L140

    """
    minutes, seconds = divmod(td.seconds, 60)
    hours, minutes = divmod(minutes, 60)
    return f'{"-" if td.days < 0 else ""}P{abs(td.days)}DT{hours:d}H{minutes:d}M{seconds:d}.{td.microseconds:06d}S'


def get_my_public_ip() -> str:
    """
    Fetches the public IP address of the machine making the request.
    Uses the 'checkip.amazonaws.com' service to retrieve the IP address.
    :return The public IP address as a string in the form 'x.x.x.x'.
    :raises
        requests.RequestException: If the request to the IP service fails.
        requests.Timeout: If the request times out.
    """
    r = requests.get('https://checkip.amazonaws.com', timeout=30)
    r.raise_for_status()
    return r.content.decode().strip()


def get_directory_size(directory: str) -> int:
    """
    Returns the total size (in bytes) of the target directory, including all subdirectories.

    :param directory: Path to the target directory.
    :return: Total size in bytes.
    """
    dir_path = Path(directory)
    return sum(f.stat().st_size for f in dir_path.rglob("*") if f.is_file())


def get_free_space_excluding_files(directory: str) -> int:
    """
    Returns the number of free bytes on the partition of the target directory,
    excluding the total size of files in that directory.

    :param directory: Path to the target directory.
    :return: Free bytes available in the partition after subtracting file sizes.
    """
    # Get partition's free space
    total, used, free = shutil.disk_usage(directory)

    # Calculate the total size of files in the directory
    files_size = get_directory_size(directory)

    # Exclude file sizes from free space
    return max(0, free - files_size)


T = TypeVar('T')

try:
    from itertools import batched  # type: ignore
except ImportError:
    # Python < 3.12
    def batched(iterable: Iterable[T], n: int) -> Iterator[tuple[T, ...]]:  # type: ignore[no-redef]
        """
        Implementation of itertools.batched for < Python 3.12
        """
        it = iter(iterable)
        while True:
            chunk = tuple(itertools.islice(it, n))
            if not chunk:
                break
            yield chunk
