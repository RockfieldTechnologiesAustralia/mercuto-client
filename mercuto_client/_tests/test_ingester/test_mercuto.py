import os
from datetime import datetime
from typing import Iterator

import pytest

from ... import MercutoClient
from ...ingester.mercuto import MercutoIngester
from ...mocks import mock_mercuto

CAMPBELL_SAMPLE_FILE = os.path.join(os.path.dirname(__file__), 'resources', 'campbell-sample-file.dat')


@pytest.fixture
def mock_client() -> Iterator[MercutoClient]:
    with mock_mercuto():
        yield MercutoClient()


def test_samples_upload(mock_client: MercutoClient) -> None:
    tenant = mock_client.identity().create_tenant('Test Tenant', 'T123456789')
    project = mock_client.core().create_project(
        'test_project',
        'R123456789',
        'Test Project',
        tenant.code,
        timezone='UTC'
    )

    channel1 = mock_client.data().create_channel(
        project=project.code,
        label="VWu_1"
    )
    channel2 = mock_client.data().create_channel(
        project=project.code,
        label="VWu_2"
    )

    ingester = MercutoIngester(
        project_code=project.code,
        api_key='test_api_key',
        timezone='UTC',
    )

    assert ingester.process_file(CAMPBELL_SAMPLE_FILE)

    data = mock_client.data().load_secondary_samples(
        channels=[channel1.code, channel2.code],
        start_time=datetime.fromisoformat('2023-12-07T00:01:00+00:00'),
        end_time=datetime.fromisoformat('2023-12-07T00:04:00+00:00'),
    )
    assert len(data) == 8
