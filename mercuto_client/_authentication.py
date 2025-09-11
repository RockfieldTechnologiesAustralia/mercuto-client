from typing import Mapping, Optional


class IAuthenticationMethod:
    def update_header(self, header: dict[str, str]) -> None:
        return

    def unique_key(self) -> str:
        raise NotImplementedError(f"unique_key not implemented for type {self.__class__.__name__}")


class ApiKeyAuthentication(IAuthenticationMethod):
    def __init__(self, api_key: str) -> None:
        self.api_key = api_key

    def update_header(self, header: dict[str, str]) -> None:
        header['X-Api-Key'] = self.api_key

    def unique_key(self) -> str:
        return f'api-key:{self.api_key}'


class ServiceTokenAuthentication(IAuthenticationMethod):
    def __init__(self, service_token: str) -> None:
        self.service_token = service_token

    def update_header(self, header: dict[str, str]) -> None:
        header['X-Service-Token'] = self.service_token

    def unique_key(self) -> str:
        return f'service-token:{self.service_token}'


class AuthorizationHeaderAuthentication(IAuthenticationMethod):
    def __init__(self, authorization_header: str) -> None:
        if not authorization_header.startswith('Bearer '):
            authorization_header = 'Bearer ' + authorization_header
        self.authorization_header = authorization_header

    def update_header(self, header: dict[str, str]) -> None:
        header['Authorization'] = self.authorization_header

    def unique_key(self) -> str:
        return f'auth-bearer:{self.authorization_header}'


class NullAuthenticationMethod(IAuthenticationMethod):
    def update_header(self, header: dict[str, str]) -> None:
        pass

    def unique_key(self) -> str:
        return 'null-authentication'


def create_authentication_method(api_key: Optional[str] = None,
                                 service_token: Optional[str] = None,
                                 bearer_token: Optional[str] = None,
                                 headers: Optional[Mapping[str, str]] = None) -> IAuthenticationMethod:
    if api_key is not None and service_token is not None and headers is not None and bearer_token is not None:
        raise ValueError("Only one of api_key or service_token or bearer_token can be provided")
    if headers is not None:
        api_key = headers.get('X-Api-Key', None)
        service_token = headers.get('X-Service-Token', None)
        bearer_token = headers.get('Authorization', None)
    if api_key is not None:
        return ApiKeyAuthentication(api_key)
    elif service_token is not None:
        return ServiceTokenAuthentication(service_token)
    elif bearer_token is not None:
        return AuthorizationHeaderAuthentication(bearer_token)
    else:
        return NullAuthenticationMethod()
