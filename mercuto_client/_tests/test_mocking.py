import pytest

from .. import MercutoClient
from ..mocks import mock_client


def test_mock_injection_before_client_creation():
    count = 0

    def on_get_healthcheck(*args, **kwargs):
        nonlocal count
        count += 1
        return 'mocked'
    with mock_client() as mock:
        mock.on('GET', '/healthcheck', on_get_healthcheck)
        client = MercutoClient()
        assert client.healthcheck() == 'mocked'
    assert count == 1


def test_mock_injection_after_client_creation():
    count = 0
    client = MercutoClient()

    def on_get_healthcheck(*args, **kwargs):
        nonlocal count
        count += 1
        return 'mocked'
    with mock_client() as mock:
        mock.on('GET', '/healthcheck', on_get_healthcheck)
        assert client.healthcheck() == 'mocked'
    assert count == 1


def test_mock_releases_after_end_of_context():
    client = MercutoClient()
    with mock_client() as mock:
        key = mock.add_user(user='this is a test')
        client.connect(api_key=key)
        assert client.identity().verify_me()['user'] == 'this is a test'

    with pytest.raises(Exception):
        client.identity().verify_me()


def test_mock_verify_me():
    client = MercutoClient()
    with mock_client() as mock:
        with pytest.raises(Exception):
            client.identity().verify_me()

        client.connect(api_key='bad api key')
        with pytest.raises(Exception):
            client.identity().verify_me()

        key = mock.add_user(user='this is a test user',
                            tenant='test-tenant', permission_group='test-group')
        client.connect(api_key=key)
        assert client.identity().verify_me()['user'] == 'this is a test user'
        assert client.identity().verify_me()['tenant'] == 'test-tenant'
        assert client.identity().verify_me()[
            'permission_group'] == 'test-group'

        mock.delete_user(key)
        with pytest.raises(Exception):
            client.identity().verify_me()


def test_mock_get_user():
    client = MercutoClient()
    with mock_client() as mock:
        client.connect(api_key='bad api key')
        with pytest.raises(Exception):
            client.identity().get_user('12345')

        key = mock.add_user(user='code1', tenant='test-tenant', permission_group='test-group',
                            username='testing@example.com')
        client.connect(api_key=key)

        assert client.identity().get_user('code1')['code'] == 'code1'
        assert client.identity().get_user(
            'code1')['username'] == 'testing@example.com'

        mock.delete_user(key)
        with pytest.raises(Exception):
            client.identity().verify_me()


def test_mock_unsupported_endpoint():
    client = MercutoClient()
    with mock_client():
        with pytest.raises(NotImplementedError):
            client.identity().list_tenants()
