from typing import Optional

import pytz

from .generic_csv import DataSample, parse_generic_csv_file


def parse_worldsensing_standard_file(filename: str, label_to_channel_code: dict[str, str],
                                     timezone: Optional[pytz.BaseTzInfo] = None) -> list[DataSample]:
    """
    Parse a worldsensing standard CSV file provided when downloading data or using standard CSV export.
    """
    return parse_generic_csv_file(
        filename, label_to_channel_code, header_index=9, data_index=0, timezone=timezone)


def parse_worldsensing_compact_file(filename: str, label_to_channel_code: dict[str, str],
                                    timezone: Optional[pytz.BaseTzInfo] = None) -> list[DataSample]:
    """
    Parse a worldsensing custom CSV file. These are generated when using compacted CSV mechanism.
    """
    return parse_generic_csv_file(
        filename, label_to_channel_code, header_index=1, data_index=0, timezone=timezone)
