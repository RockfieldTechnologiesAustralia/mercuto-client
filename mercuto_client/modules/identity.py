from typing import TYPE_CHECKING, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
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
    email_address: Optional[str] = None
    mobile_number: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class UserActivitySummary(BaseModel):
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    session_count: int
    relative_activity: int


class User(BaseModel):
    code: str
    username: Optional[str] = None
    description: str
    tenant: str
    permission_group: str
    details: Optional[UserDetails] = None
    is_sso: bool = False
    activity: Optional[UserActivitySummary] = None


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
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Verify routes ---

    def get_my_permissions(self) -> VerifyMyPermissions:
        r = self._client.request(f"{self._path}/verify/me", "GET")
        return VerifyMyPermissions.model_validate_json(r.text)

    # --- User routes ---

    def list_users(self, tenant: Optional[str] = None) -> list[User]:
        params: PayloadType = {}
        if tenant is not None:
            params["tenant"] = tenant
        r = self._client.request(f"{self._path}/users", "GET", params=params)
        return _UserlistAdapter.validate_json(r.text)

    def create_user(
        self,
        username: str,
        tenant: str,
        description: str,
        group: str,
        default_password: Optional[str] = None
    ) -> User:
        payload: PayloadType = {
            "username": username,
            "tenant_code": tenant,
            "description": description,
            "group_code": group,
            "default_password": default_password,
        }
        r = self._client.request(f"{self._path}/users", "POST", json=payload)
        return User.model_validate_json(r.text)

    def get_current_user(self) -> CurrentUser:
        r = self._client.request(f"{self._path}/users/me", "GET")
        return CurrentUser.model_validate_json(r.text)

    def get_user(self, code: str) -> User:
        r = self._client.request(f"{self._path}/users/{code}", "GET")
        return User.model_validate_json(r.text)

    def delete_user(self, code: str) -> None:
        self._client.request(f"{self._path}/users/{code}", "DELETE")

    def edit_user(
        self,
        code: str,
        description: Optional[str] = None,
        group: Optional[str] = None,
        details: Optional[UserDetails] = None,
    ) -> User:
        """
        Update a user. Only the arguments given are changed. Within `details`, only fields that were explicitly set are
        changed, and setting a field to None clears it.
        """
        payload: PayloadType = {}
        if description is not None:
            payload["description"] = description
        if group is not None:
            payload["group_code"] = group
        if details is not None:
            payload["details"] = details.model_dump(exclude_unset=True)
        r = self._client.request(f"{self._path}/users/{code}", "PATCH", json=payload)
        return User.model_validate_json(r.text)

    def get_user_api_keys(self, user: str) -> list[HiddenUserAPIKey]:
        r = self._client.request(f"{self._path}/users/{user}/api-keys", "GET")
        return _HiddenUserAPIKeylistAdapter.validate_json(r.text)

    def generate_api_key_for_user(
        self,
        user: str,
        description: str,
        custom_policy: Optional[str] = None
    ) -> VisibleUserAPIKey:
        payload: PayloadType = {
            "description": description,
            "custom_policy": custom_policy,
        }
        r = self._client.request(f"{self._path}/users/{user}/api-keys", "POST", json=payload)
        return VisibleUserAPIKey.model_validate_json(r.text)

    def delete_api_key(self, user: str, key_code: str) -> None:
        self._client.request(f"{self._path}/users/{user}/api-keys/{key_code}", "DELETE")

    # --- Tenants routes ---

    def list_tenants(self) -> list[Tenant]:
        r = self._client.request(f"{self._path}/tenants", "GET")
        return _TenantlistAdapter.validate_json(r.text)

    def get_tenant(self, code: str) -> Tenant:
        r = self._client.request(f"{self._path}/tenants/{code}", "GET")
        return Tenant.model_validate_json(r.text)

    def create_tenant(
        self,
        name: str,
        description: str,
        logo_url: Optional[str] = None
    ) -> Tenant:
        payload: PayloadType = {
            "name": name,
            "description": description,
            "logo_url": logo_url,
        }
        r = self._client.request(f"{self._path}/tenants", "POST", json=payload)
        return Tenant.model_validate_json(r.text)

    # --- Permission Groups routes ---

    def get_permission_groups(self, tenant: Optional[str] = None) -> list[PermissionGroup]:
        params: PayloadType = {}
        if tenant is not None:
            params["tenant"] = tenant
        r = self._client.request(f"{self._path}/permission-groups", "GET", params=params)
        return _PermissionGrouplistAdapter.validate_json(r.text)

    def create_permission_group(
        self,
        tenant: str,
        label: str,
        acl_policy: str
    ) -> PermissionGroup:
        payload: PayloadType = {
            "tenant": tenant,
            "label": label,
            "acl_policy": acl_policy,
        }
        r = self._client.request(f"{self._path}/permission-groups", "POST", json=payload)
        return PermissionGroup.model_validate_json(r.text)

    def get_permission_group(self, group: str) -> PermissionGroup:
        r = self._client.request(f"{self._path}/permission-groups/{group}", "GET")
        return PermissionGroup.model_validate_json(r.text)

    def delete_permission_group(self, group: str) -> None:
        self._client.request(f"{self._path}/permission-groups/{group}", "DELETE")

    def modify_permission_group(
        self,
        group: str,
        label: Optional[str] = None,
        acl_policy: Optional[str] = None
    ) -> PermissionGroup:
        """Update a permission group. Only the arguments given are changed."""
        payload: PayloadType = {}
        if label is not None:
            payload["label"] = label
        if acl_policy is not None:
            payload["acl_policy"] = acl_policy
        r = self._client.request(f"{self._path}/permission-groups/{group}", "PATCH", json=payload)
        return PermissionGroup.model_validate_json(r.text)
