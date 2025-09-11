import contextlib
import json as json_stdlib
import logging
import os
import time
from typing import Any, Iterator, Mapping, Optional, Protocol, Type, TypeVar

import requests
import requests.cookies

from ._authentication import (IAuthenticationMethod,
                              create_authentication_method)
from .exceptions import MercutoClientException, MercutoHTTPException
from .modules.core import MercutoCoreService
from .modules.data import MercutoDataService
from .modules.fatigue import MercutoFatigueService
from .modules.identity import MercutoIdentityService

logger = logging.getLogger(__name__)


class _ModuleBase(Protocol):
    def __init__(self, client: 'MercutoClient', *args: Any, **kwargs: Any) -> None:
        pass


_T = TypeVar('_T', bound=_ModuleBase)


class MercutoClient:
    def __init__(self, url: Optional[str] = None, verify_ssl: bool = True, active_session: Optional[requests.Session] = None) -> None:
        if url is None:
            url = os.environ.get('MERCUTO_API_URL', 'https://api.rockfieldcloud.com.au')
        assert isinstance(url, str)

        if url.endswith('/'):
            url = url[:-1]

        if not url.startswith('https://'):
            raise ValueError(f'Url must be https, is {url}')

        self._url = url
        self._verify_ssl = verify_ssl

        if active_session is None:
            self._current_session = requests.Session()
        else:
            self._current_session = active_session

        self._auth_method: Optional[IAuthenticationMethod] = None
        self._cookies = requests.cookies.RequestsCookieJar()

        self._modules: dict[str, _ModuleBase] = {}

    def url(self) -> str:
        return self._url

    def credentials_key(self) -> str:
        """
        Generate a unique key that identifies the current credentials set.
        """
        if self._auth_method is None:
            raise MercutoClientException("No credentials set")
        return self._auth_method.unique_key()

    def set_verify_ssl(self, verify_ssl: bool) -> None:
        self._verify_ssl = verify_ssl

    def copy(self) -> 'MercutoClient':
        return MercutoClient(self._url, self._verify_ssl, self._current_session)

    @contextlib.contextmanager
    def as_credentials(self, api_key: Optional[str] = None,
                       service_token: Optional[str] = None,
                       bearer_token: Optional[str] = None,
                       headers: Optional[Mapping[str, str]] = None) -> Iterator['MercutoClient']:
        """
        Same as .connect(), but as a context manager. Will automatically logout when exiting the context.
        """
        # TODO: We are passing the current session along to re-use connections for speed. Will this cause security issues?
        other = MercutoClient(self._url, self._verify_ssl, self._current_session)
        try:
            yield other.connect(api_key=api_key, service_token=service_token, bearer_token=bearer_token, headers=headers)
        finally:
            other.logout()

    def connect(self, *, api_key: Optional[str] = None,
                service_token: Optional[str] = None,
                bearer_token: Optional[str] = None,
                headers: Optional[Mapping[str, str]] = None) -> 'MercutoClient':
        """
        Attempt to connect using any available method.
        if api_key is provided, use the api_key.
        if service_token is provided, use the service_token.
        if headers is provided, attempt to extract either api_key or service_token from given header set.
            headers should be a dictionary of headers that would be sent in a request. Useful for using existing authenation mechanism for forwarding.

        """
        authentication = create_authentication_method(api_key=api_key, service_token=service_token, bearer_token=bearer_token, headers=headers)
        self.login(authentication)
        return self

    def _update_headers(self, headers: dict[str, str]) -> dict[str, str]:
        base: dict[str, str] = {}

        if self._auth_method is not None:
            self._auth_method.update_header(base)
        base.update(headers)
        return base

    def _http_request(self, url: str, method: str,
                      params: Optional[dict[str, Any]] = None,
                      json: Optional[dict[str, Any]] = None,
                      raise_for_status: bool = True,
                      **kwargs: Any) -> requests.Response:
        if url.startswith('/'):
            url = url[1:]
        full_url = f"{self._url}/{url}"

        if 'timeout' not in kwargs:
            kwargs['timeout'] = 10
        kwargs['headers'] = self._update_headers(kwargs.get('headers', {}))

        if 'verify' not in kwargs:
            kwargs['verify'] = self._verify_ssl

        if 'cookies' not in kwargs:
            kwargs['cookies'] = self._cookies

        # Custom parsing json to support NAN
        if json is not None and kwargs.get('data') is None:
            kwargs['data'] = json_stdlib.dumps(json, allow_nan=True)
            kwargs['headers']['Content-Type'] = 'application/json'
            json = None

        start = time.time()
        resp = self._current_session.request(method, full_url, params=params, json=json, **kwargs)
        duration = time.time() - start
        logger.debug("Made request to %s %s in %.2f seconds (code=%s)", method, full_url, duration, resp.status_code)
        if raise_for_status and not resp.ok:
            try:
                error_json = resp.json()
            except Exception:
                raise MercutoHTTPException(resp.text, resp.status_code)
            else:
                if 'detail' in error_json and isinstance(error_json['detail'], str):
                    raise MercutoHTTPException(error_json['detail'], resp.status_code)
                else:
                    raise MercutoHTTPException(resp.text, resp.status_code)
        resp.cookies.update(self._cookies)
        return resp

    def _add_and_fetch_module(self, name: str, module: Type[_T]) -> _T:
        if name not in self._modules:
            self._modules[name] = module(self)
        return self._modules[name]  # type: ignore

    def identity(self) -> 'MercutoIdentityService':
        return self._add_and_fetch_module('identity', MercutoIdentityService)

    def fatigue(self) -> 'MercutoFatigueService':
        return self._add_and_fetch_module('fatigue', MercutoFatigueService)

    def data(self) -> 'MercutoDataService':
        return self._add_and_fetch_module('data', MercutoDataService)

    def core(self) -> 'MercutoCoreService':
        return self._add_and_fetch_module('core', MercutoCoreService)

    def login(self, authentication: IAuthenticationMethod) -> None:
        self._auth_method = authentication

    def logout(self) -> None:
        self._auth_method = None

    def is_logged_in(self) -> bool:
        return self._auth_method is not None
