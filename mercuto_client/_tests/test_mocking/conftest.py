from typing import Iterator

import pytest

from ... import MercutoClient
from ...mocks import mock_mercuto


@pytest.fixture
def client() -> Iterator[MercutoClient]:
    with mock_mercuto():
        client = MercutoClient("https://testserver")
        yield client
