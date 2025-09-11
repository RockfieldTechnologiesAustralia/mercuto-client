from typing import TYPE_CHECKING, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import _PayloadType
from ._util import BaseModel


class PermissionGroup(BaseModel):
    tenant: str
    code: str
    label: str
    acl_policy: str


class Tenant(BaseModel):
    code: str
    name: str
    description: str
    logo_url: Optional[str] = None


class HiddenUserAPIKey(BaseModel):
    code: str
    description: str
    last_used: Optional[str]
    custom_policy: Optional[str] = None


class UserDetails(BaseModel):
    code: str
    username: Optional[str] = None
    email_address: Optional[str] = None
    mobile_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    api_keys: list[HiddenUserAPIKey] = []


class User(BaseModel):
    code: str
    username: Optional[str] = None
    description: str
    tenant: str
    permission_group: str


class CurrentUser(BaseModel):
    code: str
    username: Optional[str] = None
    description: str
    tenant: Tenant
    permission_group: PermissionGroup
    current_permission_policy: str


class VisibleUserAPIKey(BaseModel):
    code: str
    new_api_key: str
    description: str
    custom_policy: Optional[str]


class VerifyMyPermissions(BaseModel):
    user: Optional[str]
    acl_policy: str


class Healthcheck(BaseModel):
    status: str


# --- TypeAdapters for lists ---
_PermissionGrouplistAdapter = TypeAdapter(list[PermissionGroup])
_TenantlistAdapter = TypeAdapter(list[Tenant])
_UserlistAdapter = TypeAdapter(list[User])
_HiddenUserAPIKeylistAdapter = TypeAdapter(list[HiddenUserAPIKey])


class MercutoIdentityService:
    def __init__(self, client: 'MercutoClient', path: str = '/identity') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client._http_request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Verify routes ---

    def get_my_permissions(self) -> VerifyMyPermissions:
        r = self._client._http_request(f"{self._path}/verify/me", "GET")
        return VerifyMyPermissions.model_validate_json(r.text)

    # --- User routes ---

    def list_users(self, tenant: Optional[str] = None) -> list[User]:
        params: _PayloadType = {}
        if tenant is not None:
            params["tenant"] = tenant
        r = self._client._http_request(f"{self._path}/users", "GET", params=params)
        return _UserlistAdapter.validate_json(r.text)

    def create_user(
        self,
        username: str,
        tenant: str,
        description: str,
        group: str,
        default_password: Optional[str] = None
    ) -> User:
        payload: _PayloadType = {
            "username": username,
            "tenant_code": tenant,
            "description": description,
            "group_code": group,
            "default_password": default_password,
        }
        r = self._client._http_request(f"{self._path}/users", "PUT", json=payload)
        return User.model_validate_json(r.text)

    def get_current_user(self) -> CurrentUser:
        r = self._client._http_request(f"{self._path}/users/me", "GET")
        return CurrentUser.model_validate_json(r.text)

    def get_user(self, code: str) -> User:
        r = self._client._http_request(f"{self._path}/users/{code}", "GET")
        return User.model_validate_json(r.text)

    def delete_user(self, code: str) -> None:
        self._client._http_request(f"{self._path}/users/{code}", "DELETE")

    def edit_user(
        self,
        code: str,
        description: str,
        group: str
    ) -> User:
        payload: _PayloadType = {
            "description": description,
            "group_code": group,
        }
        r = self._client._http_request(f"{self._path}/users/{code}", "PATCH", json=payload)
        return User.model_validate_json(r.text)

    def get_user_details(self, code: str) -> UserDetails:
        r = self._client._http_request(f"{self._path}/users/{code}/details", "GET")
        return UserDetails.model_validate_json(r.text)

    def set_user_details(
        self,
        code: str,
        email_address: Optional[str] = None,
        mobile_number: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None
    ) -> UserDetails:
        payload: _PayloadType = {
            "email_address": email_address,
            "mobile_number": mobile_number,
            "first_name": first_name,
            "last_name": last_name,
        }
        r = self._client._http_request(f"{self._path}/users/{code}/details", "PATCH", json=payload)
        return UserDetails.model_validate_json(r.text)

    def get_user_api_keys(self, user: str) -> list[HiddenUserAPIKey]:
        r = self._client._http_request(f"{self._path}/users/{user}/api_keys", "GET")
        return _HiddenUserAPIKeylistAdapter.validate_json(r.text)

    def generate_api_key_for_user(
        self,
        user: str,
        description: str,
        custom_policy: Optional[str] = None
    ) -> VisibleUserAPIKey:
        payload: _PayloadType = {
            "description": description,
            "custom_policy": custom_policy,
        }
        r = self._client._http_request(f"{self._path}/users/{user}/api_keys", "POST", json=payload)
        return VisibleUserAPIKey.model_validate_json(r.text)

    def delete_api_key(self, user: str, key_code: str) -> None:
        self._client._http_request(f"{self._path}/users/{user}/api_keys/{key_code}", "DELETE")

    # --- Tenants routes ---

    def list_tenants(self) -> list[Tenant]:
        r = self._client._http_request(f"{self._path}/tenants", "GET")
        return _TenantlistAdapter.validate_json(r.text)

    def get_tenant(self, code: str) -> Tenant:
        r = self._client._http_request(f"{self._path}/tenants/{code}", "GET")
        return Tenant.model_validate_json(r.text)

    def create_tenant(
        self,
        name: str,
        description: str,
        logo_url: Optional[str] = None
    ) -> Tenant:
        payload: _PayloadType = {
            "name": name,
            "description": description,
            "logo_url": logo_url,
        }
        r = self._client._http_request(f"{self._path}/tenants", "PUT", json=payload)
        return Tenant.model_validate_json(r.text)

    # --- Permission Groups routes ---

    def get_permission_groups(self, tenant: Optional[str] = None) -> list[PermissionGroup]:
        params = {}
        if tenant is not None:
            params["tenant"] = tenant
        r = self._client._http_request(f"{self._path}/permissions", "GET", params=params)
        return _PermissionGrouplistAdapter.validate_json(r.text)

    def create_permission_group(
        self,
        tenant: str,
        label: str,
        acl_policy: str
    ) -> PermissionGroup:
        payload: _PayloadType = {
            "tenant": tenant,
            "label": label,
            "acl_policy": acl_policy,
        }
        r = self._client._http_request(f"{self._path}/permissions", "PUT", json=payload)
        return PermissionGroup.model_validate_json(r.text)

    def get_permission_group(self, group: str) -> PermissionGroup:
        r = self._client._http_request(f"{self._path}/permissions/{group}", "GET")
        return PermissionGroup.model_validate_json(r.text)

    def delete_permission_group(self, group: str) -> None:
        self._client._http_request(f"{self._path}/permissions/{group}", "DELETE")

    def modify_permission_group(
        self,
        group: str,
        label: str,
        acl_policy: str
    ) -> None:
        payload: _PayloadType = {
            "label": label,
            "acl_policy": acl_policy,
        }
        self._client._http_request(f"{self._path}/permissions/{group}", "PATCH", json=payload)
