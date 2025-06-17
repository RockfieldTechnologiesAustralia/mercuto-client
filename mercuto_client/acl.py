import json
from typing import TypeVar

from .types import AccessControlListJson, AccessControlListJsonEntry


class ResourceTypes:
    WILDCARD = '*'

    class Mercuto:
        """
        Resource types available for ServiceTypes.MERCUTO
        """
        PROJECT = 'project'
        SYSTEM = 'system'
        WILDCARD = '*'

    class Identity:
        """
        Resource types available for ServiceTypes.IDENTITY
        """
        TENANT = 'tenant'
        WILDCARD = '*'


class AllowedActions:
    WILDCARD = '*'

    class Mercuto:
        """
        Actions available for ServiceTypes.MERCUTO
        """
        WILDCARD = '*'
        VIEW_PROJECT = 'MERCUTO:VIEW_PROJECT'
        MANAGE_PROJECT = 'MERCUTO:MANAGE_PROJECT'
        EDIT_PROJECT = 'MERCUTO:EDIT_PROJECT'
        UPLOAD_DATA = 'MERCUTO:UPLOAD_DATA'
        EDIT_SYSTEM = 'MERCUTO:EDIT_SYSTEM'

    class Identity:
        """
        Actions available for ServiceTypes.IDENTITY
        """
        WILDCARD = '*'
        VIEW_TENANT = 'IDENTITY:VIEW_TENANT'
        MANAGE_TENANT = 'IDENTITY:MANAGE_TENANT'
        EDIT_TENANT = 'IDENTITY:EDIT_TENANT'
        VIEW_USER_DETAILED_INFO = 'IDENTITY:VIEW_USER_DETAILED_INFO'
        CREATE_NEW_TENANTS = 'IDENTITY:CREATE_NEW_TENANTS'


class ServiceTypes:
    class Mercuto:
        Name = 'mercuto'
        ResourceTypes = ResourceTypes.Mercuto
        AllowedActions = AllowedActions.Mercuto

    class Identity:
        Name = 'identity'
        ResourceTypes = ResourceTypes.Identity
        AllowedActions = AllowedActions.Identity

    IDENTITY = Identity.Name
    MERCUTO = Mercuto.Name
    WILDCARD = '*'


T = TypeVar('T', bound='AclPolicyBuilder')


class AclPolicyBuilder:
    def __init__(self) -> None:
        self._permissions: list[AccessControlListJsonEntry] = []

    def allow(self: T, action: str, resource: str) -> T:
        self._permissions.append({
            'action': action,
            'resource': resource
        })
        return self

    def allow_all(self: T, action: str) -> T:
        self.allow(action, f"mrn:{ServiceTypes.WILDCARD}:{ResourceTypes.WILDCARD}/{ResourceTypes.WILDCARD}")
        return self

    def allow_project(self: T, action: str, project_code: str) -> T:
        self.allow(action, f"mrn:{ServiceTypes.MERCUTO}:{ResourceTypes.Mercuto.PROJECT}/{project_code}")
        return self

    def allow_tenant(self: T, action: str, tenant_code: str) -> T:
        self.allow(action, f"mrn:{ServiceTypes.IDENTITY}:{ResourceTypes.Identity.TENANT}/{tenant_code}")
        return self

    def as_string(self) -> str:
        return json.dumps(self.as_dict())

    def as_dict(self) -> AccessControlListJson:
        return {
            'version': 1,
            'permissions': self._permissions
        }
