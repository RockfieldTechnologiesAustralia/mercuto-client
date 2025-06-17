import base64
import contextlib
import logging
import mimetypes
import os
import time
import urllib.parse
from contextlib import nullcontext
from datetime import datetime, timedelta
from typing import (Any, BinaryIO, Iterable, Iterator, List, Literal, Mapping,
                    Optional, Sequence, TextIO, Type, TypeVar)

import requests
import requests.cookies

from ._util import timedelta_isoformat
from .exceptions import MercutoClientException, MercutoHTTPException
from .types import (CHANNEL_CLASSIFICATION, AlertConfiguration,
                    AuthHealthcheckResult, Camera, Channel, Condition,
                    ContactGroup, Dashboards, Datalogger, DataRequest,
                    DataSample, Device, DeviceType, Event, FatigueConnection,
                    Image, ListAlertsResponseType, NewUserApiKey, Object,
                    PermissionGroup, Project, RainflowConfiguration,
                    ScheduledReport, ScheduledReportLog,
                    SystemHealthcheckResult, Tenant, Units, User,
                    UserContactMethod, UserDetails, VerifyMeResult, Video)

logger = logging.getLogger(__name__)


class IAuthenticationMethod:
    def update_header(self, header: dict[str, str]) -> None:
        return

    def unique_key(self) -> str:
        raise NotImplementedError(
            f"unique_key not implemented for type {self.__class__.__name__}")


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
                                 headers: Optional[Mapping[str, str]] = None) -> IAuthenticationMethod:
    if api_key is not None and service_token is not None and headers is not None:
        raise MercutoClientException(
            "Only one of api_key or service_token can be provided")
    authorization_header = None
    if headers is not None:
        api_key = headers.get('X-Api-Key', None)
        service_token = headers.get('X-Service-Token', None)
        authorization_header = headers.get('Authorization', None)
    if api_key is not None:
        return ApiKeyAuthentication(api_key)
    elif service_token is not None:
        return ServiceTokenAuthentication(service_token)
    elif authorization_header is not None:
        return AuthorizationHeaderAuthentication(authorization_header)
    else:
        return NullAuthenticationMethod()


class Module:
    def __init__(self, client: 'MercutoClient') -> None:
        self._client = client

    @property
    def client(self) -> 'MercutoClient':
        return self._client


T = TypeVar('T', bound='Module')


class MercutoClient:
    def __init__(self, url: Optional[str] = None, verify_ssl: bool = True, active_session: Optional[requests.Session] = None) -> None:
        if url is None:
            url = os.environ.get(
                'MERCUTO_API_URL', 'https://api.rockfieldcloud.com.au')
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

        self._modules: dict[str, Module] = {}

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
                       headers: Optional[Mapping[str, str]] = None) -> Iterator['MercutoClient']:
        """
        Same as .connect(), but as a context manager. Will automatically logout when exiting the context.
        """
        # TODO: We are passing the current session along to re-use connections for speed. Will this cause security issues?
        other = MercutoClient(self._url, self._verify_ssl,
                              self._current_session)
        try:
            yield other.connect(api_key=api_key, service_token=service_token, headers=headers)
        finally:
            other.logout()

    def connect(self, *, api_key: Optional[str] = None,
                service_token: Optional[str] = None,
                headers: Optional[Mapping[str, str]] = None) -> 'MercutoClient':
        """
        Attempt to connect using any available method.
        if api_key is provided, use the api_key.
        if service_token is provided, use the service_token.
        if headers is provided, attempt to extract either api_key or service_token from given header set.
            headers should be a dictionary of headers that would be sent in a request. Useful for using existing authenation mechanism for forwarding.

        """
        authentication = create_authentication_method(
            api_key=api_key, service_token=service_token, headers=headers)
        self.login(authentication)
        return self

    def _update_headers(self, headers: dict[str, str]) -> dict[str, str]:
        base: dict[str, str] = {}

        if self._auth_method is not None:
            self._auth_method.update_header(base)
        base.update(headers)
        return base

    def build_url(self, path: str, **params: Any) -> str:
        if path.startswith('/'):
            path = path[1:]
        if path.endswith('/'):
            path = path[:-1]
        return f"{self._url}/{path}/?{urllib.parse.urlencode(params)}"

    def _request_json(self, method: str, url: str, *args: Any, **kwargs: Any) -> Any:
        if 'timeout' not in kwargs:
            kwargs['timeout'] = 10
        kwargs['headers'] = self._update_headers(kwargs.get('headers', {}))

        if 'verify' not in kwargs:
            kwargs['verify'] = self._verify_ssl

        if 'cookies' not in kwargs:
            kwargs['cookies'] = self._cookies
        return self._make_request(method, url, *args, **kwargs)

    def _make_request(self, method: str, url: str, *args: Any, **kwargs: Any) -> Any:
        if url.startswith('/'):
            url = url[1:]
        full_url = f"{self._url}/{url}"
        start = time.time()
        resp = self._current_session.request(method, full_url, *args, **kwargs)
        duration = time.time() - start
        logger.debug("Made request to %s %s in %.2f seconds (code=%s)",
                     method, full_url, duration, resp.status_code)
        if not resp.ok:
            raise MercutoHTTPException(resp.text, resp.status_code)
        if resp.headers.get('Content-Type', '') != 'application/json':
            raise MercutoClientException(f"Response is not JSON: {resp.text}")
        resp.cookies.update(self._cookies)
        return resp.json()

    def request(self, method: str, url: str, *args: Any, **kwargs: Any) -> Any:
        return self._request_json(method, url, *args, **kwargs)

    def add_and_fetch_module(self, name: str, module: Type[T]) -> T:
        if name not in self._modules:
            self._modules[name] = module(self)
        return self._modules[name]  # type: ignore

    def identity(self) -> 'MercutoIdentityService':
        return self.add_and_fetch_module('identity', MercutoIdentityService)

    def projects(self) -> 'MercutoProjectService':
        return self.add_and_fetch_module('projects', MercutoProjectService)

    def fatigue(self) -> 'MercutoFatigueService':
        return self.add_and_fetch_module('fatigue', MercutoFatigueService)

    def channels(self) -> 'MercutoChannelService':
        return self.add_and_fetch_module('channels', MercutoChannelService)

    def data(self) -> 'MercutoDataService':
        return self.add_and_fetch_module('data', MercutoDataService)

    def events(self) -> 'MercutoEventService':
        return self.add_and_fetch_module('events', MercutoEventService)

    def alerts(self) -> 'MercutoAlertService':
        return self.add_and_fetch_module('alerts', MercutoAlertService)

    def devices(self) -> 'MercutoDeviceService':
        return self.add_and_fetch_module('devices', MercutoDeviceService)

    def notifications(self) -> 'MercutoNotificationsService':
        return self.add_and_fetch_module('notifications', MercutoNotificationsService)

    def reports(self) -> 'MercutoReportingService':
        return self.add_and_fetch_module('reports', MercutoReportingService)

    def objects(self) -> 'MercutoObjectService':
        return self.add_and_fetch_module('objects', MercutoObjectService)

    def media(self) -> 'MercutoMediaService':
        return self.add_and_fetch_module('media', MercutoMediaService)

    def login(self, authentication: IAuthenticationMethod) -> None:
        self._auth_method = authentication

    def logout(self) -> None:
        self._auth_method = None

    def healthcheck(self) -> SystemHealthcheckResult:
        return self._request_json('GET', '/healthcheck')  # type: ignore[no-any-return]


class MercutoDataService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def upload_samples(self, samples: Sequence[DataSample]) -> None:
        self._client._request_json(
            'POST', '/data/upload/samples', json=samples)

    def upload_file(self, project: str, datatable: str, file: str | bytes | TextIO | BinaryIO, filename: Optional[str] = None) -> None:
        if isinstance(file, str):
            ctx = open(file, 'rb')
            filename = filename or os.path.basename(file)
        else:
            ctx = nullcontext(file)  # type: ignore
            filename = filename or 'file.dat'

        with ctx as f:
            self._client._request_json('POST', '/files/upload/small', params={'project_code': project, 'datatable_code': datatable},
                                       files={'file': (filename, f, 'text/csv')})

    def get_data_url(
        self,
        project_code: str,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        event_code: str | None = None,
        channel_codes: Iterable[str] | None = None,
        primary_channels: bool | None = None,
        channels_like: str | None = None,
        file_format: Literal['DAT', 'CSV', 'PARQUET', 'FEATHER'] = 'DAT',
        frame_format: Literal['RECORDS', 'COLUMNS'] = 'COLUMNS',
        channel_format: Literal['CODE', 'LABEL'] = 'LABEL',
        timeout: timedelta | None = timedelta(seconds=20),
    ) -> str:
        request = self.get_data_request(
            project_code=project_code,
            start_time=start_time,
            end_time=end_time,
            event_code=event_code,
            channel_codes=channel_codes,
            primary_channels=primary_channels,
            channels_like=channels_like,
            file_format=file_format,
            frame_format=frame_format,
            channel_format=channel_format,
            timeout=timeout,
        )
        if request['presigned_url'] is None:
            raise MercutoClientException("No presigned URL available")

        return request['presigned_url']

    def get_data_request(
        self,
        project_code: str,
        start_time: datetime | str | None = None,
        end_time: datetime | str | None = None,
        event_code: str | None = None,
        channel_codes: Iterable[str] | None = None,
        primary_channels: bool | None = None,
        channels_like: str | None = None,
        file_format: Literal['DAT', 'CSV', 'PARQUET', 'FEATHER'] = 'DAT',
        frame_format: Literal['RECORDS', 'COLUMNS'] = 'COLUMNS',
        channel_format: Literal['CODE', 'LABEL'] = 'LABEL',
        timeout: timedelta | None = timedelta(seconds=20),
    ) -> DataRequest:
        params = {
            'timeout': 0
        }

        body = {
            'project_code': project_code,
            'start_time': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
            'end_time': end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            'event_code': event_code,
            'channel_codes': channel_codes,
            'primary_channels': primary_channels,
            'channels_like': channels_like,
            'data_format': file_format,
            'frame_format': frame_format,
            'channel_format': channel_format,
        }

        request: DataRequest = self._client._request_json(
            'POST',
            '/data/requests',
            params=params,
            json=body)

        start = time.time()
        while True:
            if timeout is not None and time.time() - start > timeout.total_seconds():
                raise MercutoClientException(
                    "Timeout waiting for data request")
            if request['completed_at'] is not None:
                return request

            time.sleep(1)
            request = self._client._request_json(
                'GET', f'/data/requests/{request["code"]}')


class MercutoEventService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def list_events(self, project: str) -> list[Event]:
        params: dict[str, str] = {'project_code': project}
        return self._client._request_json('GET', '/events', params=params)

    def get_nearest_event(
        self,
        project_code: str,
        to: datetime | str,
        maximum_delta: timedelta | None = None,
    ) -> Event:
        params = {
            'project_code': project_code,
            'to': to.isoformat() if isinstance(to, datetime) else to,
            'maximum_delta': timedelta_isoformat(maximum_delta) if maximum_delta is not None else None,
        }

        return self.client._request_json('GET', '/events/nearest', params=params)

    def get_nearest_event_url(
            self,
            project_code: str,
            to: datetime | str,
            maximum_delta: timedelta | None = None,
            file_format: Literal['DAT', 'CSV', 'PARQUET', 'FEATHER'] = 'DAT',
            frame_format: Literal['COLUMNS', 'RECORDS'] = 'COLUMNS',
    ) -> str:
        event = self.get_nearest_event(project_code, to, maximum_delta)

        return self.client.data().get_data_url(
            project_code=project_code,
            event_code=event['code'],
            primary_channels=True,
            file_format=file_format,
            frame_format=frame_format)


class MercutoAlertService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def get_condition(self, code: str) -> Condition:
        return self._client._request_json('GET', f'/alerts/conditions/{code}')

    def create_condition(self, source: str, description: str, *,
                         lower_bound: Optional[float] = None,
                         upper_bound: Optional[float] = None,
                         neutral_position: float = 0) -> Condition:
        json = {
            'source_channel_code': source,
            'description': description,
            'neutral_position': neutral_position
        }
        if lower_bound is not None:
            json['lower_inclusive_bound'] = lower_bound
        if upper_bound is not None:
            json['upper_exclusive_bound'] = upper_bound
        return self._client._request_json('PUT', '/alerts/conditions', json=json)

    def create_configuration(self, label: str, conditions: list[str], contact_group: Optional[str] = None) -> AlertConfiguration:
        json = {
            'label': label,
            'conditions': conditions,

        }
        if contact_group is not None:
            json['contact_group'] = contact_group
        return self._client._request_json('PUT', '/alerts/configurations', json=json)

    def get_alert_configuration(self, code: str) -> AlertConfiguration:
        return self._client._request_json('GET', f'/alerts/configurations/{code}')

    def list_logs(
            self,
            project: str | None = None,
            configuration: str | None = None,
            channels: list[str] | None = None,
            start_time: datetime | str | None = None,
            end_time: datetime | str | None = None,
            limit: int = 10,
            offset: int = 0,
            latest_only: bool = False,
    ) -> ListAlertsResponseType:
        params = {
            'project': project,
            'configuration_code': configuration,
            'channels': channels,
            'start_time': start_time.isoformat() if isinstance(start_time, datetime) else start_time,
            'end_time': end_time.isoformat() if isinstance(end_time, datetime) else end_time,
            'limit': limit,
            'offset': offset,
            'latest_only': latest_only,
        }

        return self._client._request_json('GET', '/alerts/logs', params=params)


class MercutoProjectService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def get_project(self, code: str) -> Project:
        return self._client._request_json('GET', f'/projects/{code}')

    def get_projects(self) -> list[Project]:
        return self._client._request_json('GET', '/projects')

    def create_project(self, name: str, project_number: str, description: str, tenant: str,
                       timezone: str, latitude: Optional[float] = None,
                       longitude: Optional[float] = None) -> Project:

        return self._client._request_json('PUT', '/projects',
                                          json={'name': name, 'project_number': project_number, 'description': description,
                                                'tenant_code': tenant,
                                                'timezone': timezone,
                                                'latitude': latitude,
                                                'longitude': longitude,
                                                'project_type': 1,
                                                'channels': []})

    def ping_project(self, project: str, ip_address: str) -> None:
        self._client._request_json(
            'POST', f'/projects/{project}/ping', json={'ip_address': ip_address})

    def create_channel(self, project: str, label: str,  sampling_period: timedelta) -> Channel:
        return self._client._request_json('PUT', '/channels', json={
            'project_code': project,
            'label': label,
            'classification': 'SECONDARY',
            'sampling_period': timedelta_isoformat(sampling_period),
        })

    def create_dashboard(self, project_code: str, dashboards: Dashboards) -> bool:
        return self._client._request_json('POST', f'/projects/{project_code}/dashboard', json=dashboards) is None


class MercutoFatigueService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def setup_rainflow(self, project: str,
                       max_bins: int,
                       bin_size: float,
                       multiplier: float,
                       channels: list[str],
                       reservoir_adjustment: bool = True,
                       enable_root_mean_cubed: bool = True,
                       enable_root_sum_cubed: bool = True) -> RainflowConfiguration:
        return self.client._request_json('PUT', '/fatigue/rainflow/setup', json=dict(
            project=project,
            max_bins=max_bins,
            bin_size=bin_size,
            multiplier=multiplier,
            reservoir_adjustment=reservoir_adjustment,
            channels=channels,
            enable_root_mean_cubed=enable_root_mean_cubed,
            enable_root_sum_cubed=enable_root_sum_cubed
        ))

    def add_connection(self, project: str, label: str,
                       multiplier: float, c_d: float, m: float, s_0: float,
                       bs7608_failure_probability: float, bs7608_detail_category: str,
                       initial_date: datetime, initial_damage: float,
                       sources: list[str]) -> FatigueConnection:
        """
        Sources should be a list of Primary Channel codes.
        """
        return self.client._request_json('PUT', '/fatigue/connections', json=dict(
            project=project,
            label=label,
            multiplier=multiplier,
            c_d=c_d,
            m=m,
            s_0=s_0,
            bs7608_failure_probability=bs7608_failure_probability,
            bs7608_detail_category=bs7608_detail_category,
            initial_date=initial_date.isoformat(),
            initial_damage=initial_damage,
            sources=sources
        ))


class MercutoChannelService(Module):
    def __init__(self, client: MercutoClient) -> None:
        super().__init__(client)

    def get_units(self) -> List[Units]:
        return self._client._request_json('GET', '/channels/units')

    def create_units(self, name: str, unit: str) -> Units:
        return self._client._request_json('PUT', '/channels/units', json=dict(name=name, unit=unit))

    def create_channel(self, project_code: str, label: str, classification: CHANNEL_CLASSIFICATION, sampling_period: timedelta) -> Channel:
        return self._client._request_json('PUT', '/channels', json=dict(
            project_code=project_code,
            label=label,
            classification=classification,
            sampling_period=timedelta_isoformat(sampling_period)))

    def modify_channel(self,
                       channel: str,
                       label:  Optional[str] = None,
                       units_code:  Optional[str] = None,
                       device_code:  Optional[str] = None,
                       metric:  Optional[str] = None,
                       multiplier: float = 1,
                       offset: float = 0) -> Channel:
        data: dict = {}
        if label is not None:
            data['label'] = label
        if units_code is not None:
            data['units_code'] = units_code
        if metric is not None:
            data['metric'] = metric
        if device_code is not None:
            data['device_code'] = device_code
        data['multiplier'] = multiplier
        data['offset'] = offset
        return self._client._request_json('PATCH', f'/channels/{channel}', json=data)

    def get_channels(
        self,
        project_code: str | None = None,
        classification: CHANNEL_CLASSIFICATION | None = None,
        aggregate: str | None = None,
        metric: str | None = None,
    ) -> list[Channel]:
        limit = 200
        offset = 0
        channels: list[Channel] = []

        while True:
            params = {
                'project_code': project_code,
                'classification': classification,
                'aggregate': aggregate,
                'metric': metric,
                'limit': limit,
                'offset': offset,
            }

            resp = self._client._request_json(
                'GET', '/channels', params=params)
            channels.extend(resp)

            if len(resp) < limit:
                break

            offset += limit

        return channels


class MercutoDeviceService(Module):
    def __init__(self, client: MercutoClient) -> None:
        super().__init__(client)

    def get_device_types(self) -> list[DeviceType]:
        return self._client._request_json('GET', '/devices/types')

    def create_device_type(self, description: str, manufacturer: str, model_number: str) -> DeviceType:
        return self._client._request_json('PUT', '/devices/types', json=dict(
            description=description,
            manufacturer=manufacturer,
            model_number=model_number))

    def get_devices(self, project_code: str, limit: int, offset: int) -> list[Device]:
        return self._client._request_json('GET', '/devices', params=dict(project_code=project_code, limit=limit, offset=offset))

    def get_device(self, device_code: str) -> Device:
        return self._client._request_json('GET', f'/devices/{device_code}')

    def create_device(self,
                      project_code: str,
                      label: str,
                      device_type_code: str,
                      groups: list[str],
                      location_description: Optional[str] = None) -> Device:
        return self._client._request_json('PUT', '/devices', json=dict(
            project_code=project_code,
            label=label,
            device_type_code=device_type_code,
            groups=groups,
            location_description=location_description))

    def list_dataloggers(self, project: str) -> list[Datalogger]:
        return self._client._request_json('GET', '/dataloggers', params={'project_code': project})


class MercutoIdentityService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def create_tenant(self, name: str, description: str, logo_url: Optional[str] = None) -> Tenant:
        return self._client._request_json('PUT', '/identity/tenants',
                                          json={'name': name, 'description': description, 'logo_url': logo_url})

    def list_tenants(self) -> list[Tenant]:
        return self._client._request_json('GET', '/identity/tenants')

    def get_tenant(self, code: str) -> Tenant:
        return self._client._request_json('GET', f'/identity/tenants/{code}')

    def create_user(self, username: str, tenant: str, description: str,
                    group: str, password: Optional[str] = None) -> User:
        return self._client._request_json('PUT', '/identity/users',
                                          json={'username': username, 'tenant_code': tenant, 'description': description,
                                                'group_code': group, 'default_password': password})

    def list_users(self, project: Optional[str] = None,
                   tenant: Optional[str] = None) -> list[User]:
        params = {}
        if project is not None:
            params['project'] = project
        if tenant is not None:
            params['tenant'] = tenant
        return self._client._request_json('GET', '/identity/users', params=params)

    def get_user(self, code: str) -> User:
        return self._client._request_json('GET', f'/identity/users/{code}')

    def get_user_details(self, code: str) -> UserDetails:
        return self._client._request_json('GET', f'/identity/users/{code}/details')

    def edit_user_details(self, code: str, first_name: Optional[str], last_name: Optional[str],
                          email_address: Optional[str], mobile_number: Optional[str]) -> UserDetails:
        return self._client._request_json('PATCH', f'/identity/users/{code}/details', json={
            'first_name': first_name,
            'last_name': last_name,
            'email_address': email_address,
            'mobile_number': mobile_number
        })

    def generate_api_key(self, user: str, description: str) -> NewUserApiKey:
        return self._client._request_json('POST', f'/identity/users/{user}/api_keys',
                                          json={'description': description})

    def grant_user_permission(self, user: str, resource: str, action: str) -> None:
        return self._client._request_json('POST', f'/identity/users/{user}/grant',
                                          json={'resource': resource, 'action': action})

    def create_permission_group(self, tenant: str, label: str,
                                acl_json: str) -> PermissionGroup:
        return self._client._request_json('PUT', '/identity/permissions', json={
            'tenant': tenant,
            'label': label,
            'acl_policy': acl_json
        })

    def list_permission_groups(self) -> list[PermissionGroup]:
        return self._client._request_json('GET', '/identity/permissions')

    def get_permission_group(self, code: str) -> PermissionGroup:
        return self._client._request_json('GET', f'/identity/permissions/{code}')

    def update_permission_group(self, code: str, label: str,
                                acl_json: str) -> None:
        return self._client._request_json('PATCH', f'/identity/permissions/{code}', json={
            'label': label,
            'acl_policy': acl_json
        })

    def verify_me(self) -> VerifyMeResult:
        return self._client._request_json('GET', '/identity/verify/me')

    def healthcheck(self) -> AuthHealthcheckResult:
        return self._client._request_json('GET', '/identity/healthcheck')


class MercutoNotificationsService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def list_contact_groups(self, project: Optional[str] = None) -> list[ContactGroup]:
        params = {}
        if project is not None:
            params['project'] = project
        return self._client._request_json('GET', '/notifications/contact_groups', params=params)

    def get_contact_group(self, code: str) -> ContactGroup:
        return self._client._request_json('GET', f'/notifications/contact_groups/{code}')

    def create_contact_group(self, project: str, label: str, users: dict[str, list[UserContactMethod]]) -> ContactGroup:
        return self._client._request_json('PUT', '/notifications/contact_groups',
                                          json={
                                              'project': project,
                                              'label': label,
                                              'users': users
                                          })


class MercutoReportingService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def list_reports(self, project: Optional[str] = None) -> list['ScheduledReport']:
        params = {}
        if project is not None:
            params['project'] = project
        return self._client._request_json('GET', '/reports/scheduled', params=params)

    def create_report(self, project: str, label: str, schedule: str, revision: str,
                      api_key: Optional[str] = None, contact_group: Optional[str] = None) -> ScheduledReport:
        return self._client._request_json('PUT', '/reports/scheduled', json={
            'project': project,
            'label': label,
            'schedule': schedule,
            'revision': revision,
            'execution_role_api_key': api_key,
            'contact_group': contact_group
        })

    def generate_report(self, report: str, timestamp: datetime, mark_as_scheduled: bool = False) -> ScheduledReportLog:
        return self._client._request_json('PUT', f'/reports/scheduled/{report}/generate', json={
            'timestamp': timestamp.isoformat(),
            'mark_as_scheduled': mark_as_scheduled
        })

    def list_report_logs(self, report: str, project: Optional[str] = None) -> list[ScheduledReportLog]:
        params: dict[str, str] = {}
        if project is not None:
            params['project'] = project
        return self._client._request_json('GET', f'/reports/scheduled/{report}/logs', params=params)

    def get_report_log(self, report: str, log: str) -> ScheduledReportLog:
        return self._client._request_json('GET', f'/reports/scheduled/{report}/logs/{log}')


class MercutoObjectService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def upload_file(self, project_code: str, file: str, event_code: Optional[str] = None,
                    mime_type: Optional[str] = None) -> Object:
        with open(file, 'rb') as f:
            if mime_type is None:
                mime_type = mimetypes.guess_type(file, strict=False)[0]
                if mime_type is None:
                    raise MercutoClientException(
                        f"Could not determine mime type for {file}")
            base64_data = base64.b64encode(f.read()).decode('utf-8')
            data_url = f'data:{mime_type};base64,{base64_data}'

            return self._client._request_json('POST', '/objects/upload', params={
                'project_code': project_code,
                'event_code': event_code
            }, json={
                'filename': os.path.basename(file),
                'mime_type': mime_type,
                'data_url': data_url
            })


class MercutoMediaService(Module):
    def __init__(self, client: 'MercutoClient') -> None:
        super().__init__(client)

    def list_cameras(self, project: str) -> list[Camera]:
        params = {}
        params['project_code'] = project
        return self._client._request_json('GET', '/media/cameras', params=params)

    def list_videos(self, project: Optional[str] = None, event: Optional[str] = None, camera: Optional[str] = None) -> list[Video]:
        params = {}
        if project is not None:
            params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        return self._client._request_json('GET', '/media/videos', params=params)

    def list_images(self, project: Optional[str] = None, event: Optional[str] = None, camera: Optional[str] = None) -> list[Image]:
        params = {}
        if project is not None:
            params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        return self._client._request_json('GET', '/media/images', params=params)

    def get_image(self, code: str) -> Image:
        return self._client._request_json('GET', f'/media/images/{code}')  # type: ignore[no-any-return]

    def upload_image(self, project: str, file: str, event: Optional[str] = None,
                     camera: Optional[str] = None, timestamp: Optional[datetime] = None,
                     filename: Optional[str] = None) -> Image:
        if timestamp is not None and timestamp.tzinfo is None:
            raise MercutoClientException("Timestamp must be timezone aware")

        mimetype, _ = mimetypes.guess_type(file, strict=False)
        if mimetype is None or not mimetype.startswith('image/'):
            raise MercutoClientException(f"File {file} is not an image")

        if os.stat(file).st_size > 5_000_000:
            raise MercutoClientException(f"File {file} is too large")

        if filename is None:
            filename = os.path.basename(file)

        params = {}
        params['project'] = project
        if event is not None:
            params['event'] = event
        if camera is not None:
            params['camera'] = camera
        if timestamp is not None:
            params['timestamp'] = timestamp.isoformat()

        with open(file, 'rb') as f:
            return self._client._request_json('PUT', '/media/images', params=params, files={
                'file': (filename, f, mimetype)
            })
