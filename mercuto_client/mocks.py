import contextlib
import dataclasses
import re
import uuid
from typing import Any, Optional, Protocol

from .exceptions import MercutoClientException
from .types import Tenant, User, UserDetails, VerifyMeResult

"""
This module provides a context manager for mocking the Mercuto Client.

Within the mock_client() context, any calls to the Mercuto Client will be intercepted and handled by the MercutoMocker.


Usage:

client = MercutoClient()

with mock_client() as mock:
    # Create a user in the system
    api_key = mock.add_user()

    # Login using the generated user key
    client.connect(api_key = api_key)

    # Call Mercuto Client endpoints as normal
    client.identity().verify_me()

"""


class MakeRequestHookType(Protocol):
    def __call__(self, method: str, url: str, *args, **kwargs) -> Any:
        """
        *args and **kwargs are arguments passed to requests.request(method, url, *args, **kwargs)
        """
        pass


@contextlib.contextmanager
def mock_client():
    from .client import MercutoClient
    original = MercutoClient._make_request
    mocker = MercutoMocker()
    try:
        setattr(MercutoClient, '_make_request', mocker._on_make_request)
        yield mocker
    finally:
        setattr(MercutoClient, '_make_request', original)


class MercutoMocker:
    @dataclasses.dataclass
    class MockedUser:
        code: str
        username: str
        description: str
        tenant: str
        permission_group: str
        mobile_number: Optional[str] = None

    def __init__(self) -> None:
        self._hooks: dict[tuple[str, str], MakeRequestHookType] = {}

        # Users based on Api-Key
        self._known_users: dict[str, MercutoMocker.MockedUser] = {}
        self._known_tenants: dict[str, Tenant] = {}

        self._setup_default_hooks()

    def on(self, method: str, path: str, callback: MakeRequestHookType):
        self._hooks[(method, path)] = callback

    def add_tenant(self, code: Optional[str] = None) -> None:
        if code is None:
            code = str(uuid.uuid4())
        self._known_tenants[code] = Tenant(
            code=code,
            name=f"Tenant {code}",
            description=f"Tenant {code}",
            logo_url=None,
        )

    def add_user(self,
                 user: Optional[str] = None,
                 tenant: Optional[str] = None,
                 permission_group: Optional[str] = None,
                 key: Optional[str] = None,
                 username: Optional[str] = None,
                 description: Optional[str] = None,
                 mobile_number: Optional[str] = None,
                 ):
        if user is None:
            # User code
            user = str(uuid.uuid4())
        if tenant is None:
            tenant = str(uuid.uuid4())
        if permission_group is None:
            permission_group = str(uuid.uuid4())
        if key is None:
            key = str(uuid.uuid4())
        if username is None:
            username = f"{user.replace(' ', '')}@example.com"
        if description is None:
            description = f"User {user}"

        mocked = self.MockedUser(user, username, description, tenant, permission_group,
                                 mobile_number=mobile_number)
        self._known_users[key] = mocked
        return key

    def delete_user(self, key: Optional[str] = None, code: Optional[str] = None):
        if key is not None and key in self._known_users:
            del self._known_users[key]

        if code is not None:
            key = next((k for k, u in self._known_users.items()
                       if u.code == code), None)
            if key is not None:
                del self._known_users[key]

    def _mocked_get_tenant(self, method: str, url: str, *args, **kwargs) -> Tenant:
        key = kwargs.get('headers', {}).get('X-Api-Key', None)
        if key is None:
            raise MercutoClientException("No X-Api-Key header provided")
        tenant = self._known_tenants.get(key, None)
        if tenant is None:
            raise MercutoClientException("Tenant not found")
        return tenant

    def _mocked_verify_me(self, method: str, url: str, *args, **kwargs) -> VerifyMeResult:
        key = kwargs.get('headers', {}).get('X-Api-Key', None)
        if key is None:
            raise MercutoClientException("No X-Api-Key header provided")
        user = self._known_users.get(key, None)
        if user is None:
            raise MercutoClientException(f"User {user} not found")
        return VerifyMeResult(
            user=user.code,
            tenant=user.tenant,
            permission_group=user.permission_group,
            acl_policy='{"version": 1, "permissions": []}'
        )

    def _mocked_get_user(self, method: str, url: str, *args, **kwargs) -> User:
        apikey = kwargs.get('headers', {}).get('X-Api-Key', None)
        servicekey = kwargs.get('headers', {}).get('X-Service-Token', None)
        if apikey is None and servicekey is None:
            raise MercutoClientException(
                "No X-Api-Key or X-Service-Token header provided")
        user_code = url.split('/')[-1]
        user = next((u for u in self._known_users.values()
                    if u.code == user_code), None)
        if user is None:
            raise MercutoClientException("User not found")
        return User(
            code=user.code,
            username=user.username,
            description=user.description,
            tenant=user.tenant,
            permission_group=user.permission_group,
        )

    def _mocked_get_user_details(self, method: str, url: str, *args, **kwargs) -> UserDetails:
        apikey = kwargs.get('headers', {}).get('X-Api-Key', None)
        servicekey = kwargs.get('headers', {}).get('X-Service-Token', None)
        if apikey is None and servicekey is None:
            raise MercutoClientException(
                "No X-Api-Key or X-Service-Token header provided")
        url_parts = url.split('/')
        assert url_parts[-1] == 'details'
        user_code = url_parts[-2]
        user = next((u for u in self._known_users.values()
                    if u.code == user_code), None)
        if user is None:
            raise MercutoClientException("User not found")
        return UserDetails(
            code=user.code,
            username=user.username,
            mobile_number=user.mobile_number,
            email_address=None,
            first_name=None,
            last_name=None,
            api_keys=[]
        )

    def _setup_default_hooks(self) -> None:
        self.on('GET', r'\/identity\/verify\/me', self._mocked_verify_me)
        self.on('GET', r'\/identity\/users\/[^\/]+', self._mocked_get_user)
        self.on('GET', r'\/identity\/tenant\/[^\/]+', self._mocked_get_tenant)
        self.on(
            'GET', r'\/identity\/users\/[^\/]+\/details', self._mocked_get_user_details)

    def _on_make_request(self, method: str, url: str, *args, **kwargs) -> Any:

        # First check any custom hooks
        for (hook_method, pattern), callback in self._hooks.items():
            if method == hook_method and re.fullmatch(pattern, url) is not None:
                return callback(method, url, *args, **kwargs)

        raise NotImplementedError(
            "Mocking is not supported for this endpoint: %s %s" % (method, url))
