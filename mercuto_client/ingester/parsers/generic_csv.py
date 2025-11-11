import logging
from datetime import datetime
from typing import Optional

import pytz
from dateutil import parser

from ...modules.data import SecondaryDataSample

logger = logging.getLogger(__name__)


def _clean(s: str) -> str:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s


def _clean_number(s: str) -> float | None:
    cleaned = _clean(s)
    if cleaned == 'NAN' or cleaned == 'N/A' or cleaned == 'NaN' or cleaned == 'nan' or cleaned == 'Nan':
        return float('nan')
    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_header(header: str) -> list[str]:
    columns = [h.strip() for h in header.strip().split(",")]
    if columns[0] not in ('"TIMESTAMP"', 'timestamp', 'TIMESTAMP', '"Date-and-time"'):
        raise ValueError(
            f"Invalid header found: {columns[0]}, expecting TIMESTAMP.")
    # Columns have quotes around them, remove them
    return [_clean(c) for c in columns[1:]]


def _parse_csv_line(line: str, sep: str = ',', timestamp_index: int = 0) -> tuple[datetime, list[float | None]]:
    """
    Returns timestamp, values
    """
    values = line.strip().split(sep)
    if len(values) < 2:
        raise ValueError(f"Invalid number of values found: {len(values)}")
    # First value is timestamp
    timestamp = _clean(values[timestamp_index])
    try:
        dt = parser.parse(timestamp)
    except ValueError as e:
        raise ValueError(
            f"Failed to parse timestamp: {timestamp} - {e}") from e
    # Rest are values
    return dt, [_clean_number(v) for v in values[timestamp_index+1:]]


def parse_generic_csv_file(filename: str, label_to_channel_code: dict[str, str],
                           header_index: int, data_index: int,
                           timezone: Optional[pytz.BaseTzInfo] = None) -> list[SecondaryDataSample]:
    """
    header index: Number of lines to skip before header
    data index: Number of lines to skip after the header before data

    We are avoiding using pandas here to keep dependencies minimal as this is often run on edge devices.
    """

    output: list[SecondaryDataSample] = []
    with open(filename, "r") as f:
        for _ in range(header_index):
            next(f, None)
        header = next(f, None)
        if header is None:
            logging.error(f"Failed to read header from file: {filename}")
            return []
        try:
            header_columns = _parse_header(header)
        except ValueError as e:
            logging.error(f"Failed to parse header: {e}")
            return []

        # Next 2 lines are metadata, skip
        for _ in range(data_index):
            next(f, None)
        while (line := next(f, None)):
            try:
                timestamp, line_values = _parse_csv_line(line)
            except ValueError as e:
                logging.error(f"Failed to parse line: {e}")
                return []

            if len(header_columns) != len(line_values):
                logging.error(
                    f"Invalid number of values found: {len(line_values)}, expected {len(header_columns)}")
                return []

            if timezone is not None and timestamp.tzinfo is None:
                timestamp = timezone.localize(timestamp)

            for header, value in zip(header_columns, line_values):
                if header not in label_to_channel_code:
                    logger.error(f"Label not found in table map: {header}")
                    continue

                if value is None:
                    logger.error(
                        f"Failed to parse value: {value} for column {header}")
                    continue
                channel_code = label_to_channel_code[header]

                logger.debug(
                    f"Adding entry for label: {header} with value: {value} and timestamp: {timestamp}")
                output.append(SecondaryDataSample(timestamp=timestamp,
                              channel=channel_code, value=value))
    return output
