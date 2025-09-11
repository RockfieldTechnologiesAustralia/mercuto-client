import math
import os
import tempfile

import pytest

from ...ingester.parsers import (detect_parser, parse_campbell_file,
                                 parse_worldsensing_compact_file,
                                 parse_worldsensing_standard_file)

RESOURCES_DIR = os.path.join(os.path.dirname(__file__), "resources")


def test_worldsensing_compacted_parser():
    file = os.path.join(RESOURCES_DIR, "worldsensing-compacted-sample-file.dat")
    mapper = {
        "channel1": "12345678",
        "channel2": "abcdefgh",
    }
    samples = parse_worldsensing_compact_file(file, mapper)
    assert len(samples) == 4
    assert samples[0].channel == "12345678"
    assert math.isclose(samples[0].value, -10)
    assert samples[0].timestamp.isoformat() == '2025-05-20T15:00:00'

    assert samples[1].channel == "abcdefgh"
    assert math.isclose(samples[1].value, 5)
    assert samples[0].timestamp.isoformat() == '2025-05-20T15:00:00'

    assert samples[2].channel == "12345678"
    assert math.isclose(samples[2].value, -12)
    assert samples[2].timestamp.isoformat() == '2025-05-20T16:00:00'

    assert samples[3].channel == "abcdefgh"
    assert math.isclose(samples[3].value, 10)
    assert samples[3].timestamp.isoformat() == '2025-05-20T16:00:00'


def test_worldsensing_standard_parser():
    file = os.path.join(RESOURCES_DIR, "worldsensing-standard-sample-file.csv")
    mapper = {
        "AtmPressure-85544-in-mbar": "12345678",
        "freqSqInDigit-85544-VW-Ch1": "abcdefgh",
    }
    samples = parse_worldsensing_standard_file(file, mapper)
    assert len(samples) == 10
    assert samples[0].channel == "12345678"
    assert math.isclose(samples[0].value, 930.5)
    assert samples[0].timestamp.isoformat() == '2024-04-15T12:35:00'

    assert samples[1].channel == "abcdefgh"
    assert math.isclose(samples[1].value, 726.810811024)
    assert samples[1].timestamp.isoformat() == '2024-04-15T12:35:00'

    assert samples[8].channel == "12345678"
    assert math.isclose(samples[8].value, 930.4)
    assert samples[8].timestamp.isoformat() == '2024-04-15T12:39:00'

    assert samples[9].channel == "abcdefgh"
    assert math.isclose(samples[9].value, 726.841502500)
    assert samples[9].timestamp.isoformat() == '2024-04-15T12:39:00'


def test_campbells_parser():
    file = os.path.join(RESOURCES_DIR, "campbell-sample-file.dat")
    mapper = {
        "VWu_1": "aaaaaaaa",
        "VWu_2": "bbbbbbbb",
        "Therm(1)": "cccccccc",
        "Therm(2)": "dddddddd",
        "Diag_Max(1)": "eeeeeeee",
        "Diag_Max(2)": "ffffffff",
    }
    samples = parse_campbell_file(file, mapper)
    assert len(samples) == 6*4

    assert samples[0].channel == "aaaaaaaa"
    assert math.isclose(samples[0].value, 1234.5)
    assert samples[0].timestamp.isoformat() == '2023-12-07T00:01:00'

    for i in range(1, 6):
        assert samples[i].channel == list(mapper.values())[i]
        assert math.isnan(samples[i].value)
        assert samples[i].timestamp.isoformat() == '2023-12-07T00:01:00'

    assert samples[6].channel == "aaaaaaaa"
    assert math.isclose(samples[6].value, 1234.5)
    assert samples[6].timestamp.isoformat() == '2023-12-07T00:02:00'
    for i in range(7, 12):
        assert samples[i].channel == list(mapper.values())[i-6]
        assert math.isnan(samples[i].value)
        assert samples[i].timestamp.isoformat() == '2023-12-07T00:02:00'

    assert samples[12].channel == "aaaaaaaa"
    assert math.isclose(samples[12].value, 1234.5)
    assert samples[12].timestamp.isoformat() == '2023-12-07T00:03:00'
    assert samples[13].channel == "bbbbbbbb"
    assert math.isclose(samples[13].value, 1234.5)
    assert samples[13].timestamp.isoformat() == '2023-12-07T00:03:00'

    for i in range(15, 17):
        assert samples[i].channel == list(mapper.values())[i-12]
        assert math.isnan(samples[i].value)
        assert samples[i].timestamp.isoformat() == '2023-12-07T00:03:00'
    assert samples[17].channel == "ffffffff"
    assert math.isclose(samples[17].value, 1537)
    assert samples[17].timestamp.isoformat() == '2023-12-07T00:03:00'

    assert samples[18].channel == "aaaaaaaa"
    assert math.isclose(samples[18].value, 1234.5)
    assert samples[18].timestamp.isoformat() == '2023-12-07T00:04:00'
    assert samples[19].channel == "bbbbbbbb"
    assert math.isclose(samples[19].value, 1234.5)
    assert samples[19].timestamp.isoformat() == '2023-12-07T00:04:00'
    assert samples[20].channel == "cccccccc"
    assert math.isclose(samples[20].value, 27.5)
    assert samples[20].timestamp.isoformat() == '2023-12-07T00:04:00'
    assert samples[21].channel == "dddddddd"
    assert math.isclose(samples[21].value, 25)
    assert samples[21].timestamp.isoformat() == '2023-12-07T00:04:00'
    assert samples[22].channel == "eeeeeeee"
    assert math.isclose(samples[22].value, 255)
    assert samples[22].timestamp.isoformat() == '2023-12-07T00:04:00'
    assert samples[23].channel == "ffffffff"
    assert math.isclose(samples[23].value, 0)
    assert samples[23].timestamp.isoformat() == '2023-12-07T00:04:00'


def test_detect_file_type():
    compacted_file = os.path.join(RESOURCES_DIR, "worldsensing-compacted-sample-file.dat")
    standard_file = os.path.join(RESOURCES_DIR, "worldsensing-standard-sample-file.csv")
    campbell_file = os.path.join(RESOURCES_DIR, "campbell-sample-file.dat")

    assert detect_parser(compacted_file) == parse_worldsensing_compact_file
    assert detect_parser(standard_file) == parse_worldsensing_standard_file
    assert detect_parser(campbell_file) == parse_campbell_file

    # Test with an unknown file type
    with tempfile.TemporaryDirectory() as dir:
        unknown_file = os.path.join(dir, "unknown-file.txt")
        with open(unknown_file, "w") as f:
            f.write("This is an unknown file format.")

        with pytest.raises(ValueError):
            detect_parser(unknown_file)
