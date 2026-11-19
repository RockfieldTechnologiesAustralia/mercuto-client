import json
from typing import Iterator, Optional
from unittest.mock import MagicMock, patch

import pytest
import requests

from .. import MercutoClient
from ..modules.assets import Device, DeviceType, DeviceTypeChannel, DeviceTypeFunction, DeviceTypeMetadataField


@pytest.fixture
def http_client() -> Iterator[tuple[MercutoClient, MagicMock]]:
    response = requests.Response()
    response.status_code = 200
    response._content = json.dumps({
        'code': 'device-a',
        'project': 'project-a',
        'label': 'Sensor',
        'device_type': 'worldsensing-psa',
        'created_at': '2026-10-25T00:00:00Z',
        'updated_at': '2026-10-25T00:00:00Z',
    }).encode()
    with requests.Session() as session:
        client = MercutoClient('https://testserver', active_session=session)
        with patch.object(session, 'request', autospec=True, return_value=response) as request:
            yield client, request


def test_device_type_functions() -> None:
    device_type = DeviceType.model_validate_json(json.dumps({
        'code': 'worldsensing-psa',
        'label': 'PSA',
        'functions': [{
            'key': 'natural_frequency',
            'label': 'Natural frequency tracking',
            'description': 'Track a structural mode',
            'metadata_fields': [{
                'key': 'natural_frequency_axis',
                'label': 'Mode axis',
                'data_type': 'string',
                'multiple': False,
            }],
            'channels': [{
                'field_key': 'natural_frequency',
                'field': 'Natural Frequency',
                'unit': 'Hz',
            }],
        }, {
            'key': 'cable_tension',
            'label': 'Hanger cable tension',
        }],
    }))
    function = device_type.get_function('natural_frequency')
    assert isinstance(function, DeviceTypeFunction)
    assert function.label == 'Natural frequency tracking'
    assert function.description == 'Track a structural mode'
    assert isinstance(function.metadata_fields[0], DeviceTypeMetadataField)
    assert function.metadata_fields[0].key == 'natural_frequency_axis'
    assert isinstance(function.channels[0], DeviceTypeChannel)
    assert function.channels[0].field_key == 'natural_frequency'
    assert function.channels[0].unit == 'Hz'
    cable_function = device_type.get_function('cable_tension')
    assert cable_function is not None
    assert cable_function.description is None
    assert cable_function.metadata_fields == []
    assert cable_function.channels == []
    assert device_type.get_function('unknown') is None


def test_device_type_without_functions() -> None:
    device_type = DeviceType.model_validate_json('{"code": "sensor", "label": "Sensor"}')
    assert device_type.functions == []
    assert device_type.get_function('natural_frequency') is None


@pytest.mark.parametrize('function', [None, 'cable_tension'])
def test_create_device_function(http_client: tuple[MercutoClient, MagicMock], function: Optional[str]) -> None:
    client, request = http_client
    device = client.assets().create_device(
        project='project-a', label='Sensor', device_type='worldsensing-psa', function=function,
    )
    request.assert_called_once()
    assert request.call_args.args == ('POST', 'https://testserver/assets/devices')
    assert json.loads(request.call_args.kwargs['data'])['function'] == function
    assert device.code == 'device-a'


@pytest.mark.parametrize(('passed', 'function'), [(False, None), (True, None), (True, 'natural_frequency'), (True, '')])
def test_update_device_function(http_client: tuple[MercutoClient, MagicMock], passed: bool, function: Optional[str]) -> None:
    client, request = http_client
    if passed:
        device = client.assets().update_device(code='device-a', label='Sensor', function=function)
    else:
        device = client.assets().update_device(code='device-a', label='Sensor')
    request.assert_called_once()
    assert request.call_args.args == ('PUT', 'https://testserver/assets/devices/device-a')
    body = json.loads(request.call_args.kwargs['data'])
    if passed:
        assert 'function' in body
        assert body['function'] == function
    else:
        assert 'function' not in body
    assert device.code == 'device-a'
    assert device.function is None


@pytest.mark.parametrize('function', [None, 'natural_frequency'])
def test_parse_device_function(http_client: tuple[MercutoClient, MagicMock], function: Optional[str]) -> None:
    client, request = http_client
    response = request.return_value
    body = response.json()
    body['function'] = function
    response._content = json.dumps(body).encode()
    device = client.assets().get_device('device-a')
    assert isinstance(device, Device)
    assert device.function == function
