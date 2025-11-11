import logging
import uuid
from dataclasses import dataclass
from typing import Callable, Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.identity import (CurrentUser, HiddenUserAPIKey,
                                MercutoIdentityService, PermissionGroup,
                                Tenant, User, UserDetails, VerifyMyPermissions,
                                VisibleUserAPIKey)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoIdentityService(MercutoIdentityService, metaclass=EnforceOverridesMeta):
    @dataclass
    class _GeneratedUserApiKey:
        user: str
        api_key: str
        hidden: HiddenUserAPIKey

    def __init__(self, client: 'MercutoClient', verify_service_token: Optional[Callable[[str], VerifyMyPermissions]] = None) -> None:
        """
        Initialize the mock identity service.
        :param client: The MercutoClient instance.
        :param verify_service_token: Optional callable to verify service tokens.
        """

        super().__init__(client=client, path='/mock-identity-service-method-not-implemented')
        self._verify_service_token = verify_service_token

        # In-memory stores for mock data
        self._users: dict[str, User] = {}
        self._user_details: dict[str, UserDetails] = {}
        self._tenants: dict[str, Tenant] = {}
        self._permission_groups: dict[str, PermissionGroup] = {}

        # Maps API Key to User
        self._api_keys: dict[str, MockMercutoIdentityService._GeneratedUserApiKey] = {}

    def get_my_permissions(self) -> VerifyMyPermissions:
        if self._client._auth_method is None:
            raise MercutoHTTPException('Not authenticated', 401)
        header: dict[str, str] = {}
        self._client._auth_method.update_header(header)
        if (api_key := header.get('X-Api-Key')) is not None:
            known = self._api_keys.get(api_key)
            if known is None:
                raise MercutoHTTPException('Invalid API key', 403)
            if known.hidden.custom_policy is not None:
                return VerifyMyPermissions(user=known.user, acl_policy=known.hidden.custom_policy)
            user = self._users[known.user]
            group = self._permission_groups[user.permission_group]
            return VerifyMyPermissions(user=user.code, acl_policy=group.acl_policy)
        elif (service_token := header.get('X-Service-Token')) is not None:
            if self._verify_service_token is None:
                raise MercutoHTTPException('Service token verification not implemented', 501)
            return self._verify_service_token(service_token)

        raise MercutoHTTPException('Invalid authentication method for mock implementation', 403)

    def list_users(self, tenant: Optional[str] = None) -> list[User]:
        if tenant is None:
            return list(self._users.values())
        return [u for u in self._users.values() if u.tenant == tenant]

    def create_user(
        self,
        username: str,
        tenant: str,
        description: str,
        group: str,
        default_password: Optional[str] = None
    ) -> User:
        code = str(uuid.uuid4())
        user = User(code=code, username=username, description=description, tenant=tenant, permission_group=group)
        self._users[code] = user
        self._user_details[code] = UserDetails(code=code, username=username)
        return user

    def get_current_user(self) -> CurrentUser:
        perms = self.get_my_permissions()
        if perms.user is None:
            raise MercutoHTTPException('Not authenticated', 401)
        user = self._users[perms.user]
        tenant = self._tenants[user.tenant]
        group = self._permission_groups[user.permission_group]
        return CurrentUser(
            code=user.code,
            username=user.username,
            description=user.description,
            tenant=tenant,
            permission_group=group,
            current_permission_policy=group.acl_policy
        )

    def get_user(self, code: str) -> User:
        return self._users[code]

    def delete_user(self, code: str) -> None:
        if code in self._users:
            del self._users[code]
        if code in self._user_details:
            del self._user_details[code]
        for k, v in list(self._api_keys.items()):
            if v.user == code:
                del self._api_keys[k]

    def get_user_details(self, code: str) -> UserDetails:
        return self._user_details[code]

    def set_user_details(
        self,
        code: str,
        email_address: Optional[str] = None,
        mobile_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> UserDetails:
        user_details = self._user_details[code]
        if email_address is not None:
            user_details.email_address = email_address
        if mobile_number is not None:
            user_details.mobile_number = mobile_number
        if first_name is not None:
            user_details.first_name = first_name
        if last_name is not None:
            user_details.last_name = last_name
        return user_details

    def get_user_api_keys(self, user: str) -> list[HiddenUserAPIKey]:
        return [v.hidden for v in self._api_keys.values() if v.user == user]

    def generate_api_key_for_user(
        self,
        user: str,
        description: str,
        custom_policy: Optional[str] = None
    ) -> VisibleUserAPIKey:
        key_code = str(uuid.uuid4())
        new_api_key = str(uuid.uuid4())
        hidden_key = HiddenUserAPIKey(code=key_code, description=description, last_used=None, custom_policy=custom_policy)

        if user not in self._users:
            raise MercutoHTTPException('User not found', 404)

        self._api_keys[new_api_key] = self._GeneratedUserApiKey(
            user=user, api_key=new_api_key, hidden=hidden_key
        )
        return VisibleUserAPIKey(code=key_code, new_api_key=new_api_key, description=description, custom_policy=custom_policy)

    def list_tenants(self) -> list[Tenant]:
        return list(self._tenants.values())

    def get_tenant(self, code: str) -> Tenant:
        return self._tenants[code]

    def create_tenant(
        self,
        name: str,
        description: str,
        logo_url: Optional[str] = None
    ) -> Tenant:
        code = str(uuid.uuid4())
        tenant = Tenant(code=code, name=name, description=description, logo_url=logo_url)
        self._tenants[code] = tenant
        return tenant

    def get_permission_groups(self, tenant: Optional[str] = None) -> list[PermissionGroup]:
        if tenant is None:
            return list(self._permission_groups.values())
        return [g for g in self._permission_groups.values() if g.tenant == tenant]

    def create_permission_group(
        self,
        tenant: str,
        label: str,
        acl_policy: str
    ) -> PermissionGroup:
        code = str(uuid.uuid4())
        group = PermissionGroup(tenant=tenant, code=code, label=label, acl_policy=acl_policy)
        self._permission_groups[code] = group
        return group

    def get_permission_group(self, group: str) -> PermissionGroup:
        return self._permission_groups[group]
