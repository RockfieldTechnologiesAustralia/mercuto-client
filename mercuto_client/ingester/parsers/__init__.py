from typing import Optional, Protocol

import pytz

from ...modules.data import SecondaryDataSample
from .campbell import parse_campbell_file
from .worldsensing import (parse_worldsensing_compact_file,
                           parse_worldsensing_standard_file)


class Parser(Protocol):
    def __call__(self, filename: str, label_to_channel_code: dict[str, str],
                 timezone: Optional[pytz.BaseTzInfo] = None) -> list[SecondaryDataSample]:
        """
        Parse the file and return a list of SecondaryDataSample objects.
        """
        pass


def detect_parser(filename: str) -> Parser:
    """
    Detect the type of the file based on its content.
    Returns one of: "worldsensing_compact", "worldsensing_standard", "campbell", or raises ValueError if unknown.
    """
    with open(filename, 'r') as f:
        first_line = f.readline().strip()
        if first_line.startswith('"TOA5",'):
            return parse_campbell_file
        elif first_line.startswith('"Datalogger","compacted"'):
            return parse_worldsensing_compact_file
        elif first_line.startswith('"Node ID",'):
            return parse_worldsensing_standard_file
        else:
            raise ValueError(f"Unknown file type for {filename}")


__all__ = [
    "parse_campbell_file",
    "parse_worldsensing_standard_file",
    "parse_worldsensing_compact_file",
    "detect_parser",
]
