from typing import Optional

import pytz

from ...modules.data import SecondaryDataSample
from .generic_csv import parse_generic_csv_file


def parse_campbell_file(filename: str, label_to_channel_code: dict[str, str],
                        timezone: Optional[pytz.BaseTzInfo] = None) -> list[SecondaryDataSample]:
    return parse_generic_csv_file(
        filename, label_to_channel_code, header_index=1, data_index=2, timezone=timezone)
