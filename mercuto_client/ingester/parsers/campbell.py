from typing import Optional

import pytz

from ...types import DataSample
from .generic_csv import parse_generic_csv_file


def parse_campbell_file(filename: str, label_to_channel_code: dict[str, str],
                        timezone: Optional[pytz.BaseTzInfo] = None) -> list[DataSample]:
    return parse_generic_csv_file(
        filename, label_to_channel_code, header_index=1, data_index=2, timezone=timezone)
