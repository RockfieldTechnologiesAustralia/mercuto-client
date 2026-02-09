from enum import Enum
from typing import TYPE_CHECKING, List, Optional

from pydantic import BaseModel, Field, TypeAdapter, model_validator
from pydantic_core.core_schema import bool_schema

from mercuto_client.exceptions import (MercutoClientException,
                                       MercutoHTTPException,
                                       MercutoNotFoundException)

if TYPE_CHECKING:
    from ..client import MercutoClient


class KnownAlgorithm(str, Enum):
    RSA = "RSA"
    Ed25519 = "ed25519"


class Algorithm(BaseModel):
    algorithm: KnownAlgorithm
    params: dict = Field(default_factory=dict)


class SSHKeyPairSchema(BaseModel):
    name: str
    public_key: str
    private_key: str


class WireguardKeyPairSchema(BaseModel):
    public_key: str
    private_key: str


class GeneratedKeysSchema(BaseModel):
    ssh: SSHKeyPairSchema
    wg: WireguardKeyPairSchema


class HealthcheckSchema(BaseModel):
    status: str


class WireguardClientSchema(BaseModel):
    code: str
    public_key: str
    client_id: int
    ip_address: str
    allowed_ips: str
    description: Optional[str] = None


class WireguardInterfaceSchema(BaseModel):
    code: str
    tenant_code: Optional[str] = None
    isolation_group_code: Optional[str] = None
    interface_name: str
    private_key: Optional[str] = None
    public_key: str
    port: int
    subnet: int
    bits: int
    hostname: str
    ip_address: Optional[str] = None
    devices: List[WireguardClientSchema] = Field(default_factory=list)

    @model_validator(mode='after')
    def has_tenant_or_issolation_group(self):
        if self.tenant_code is None and self.isolation_group_code is None:
            raise ValueError('Either "tenent_code" or "isolation_group_code" is required.')


class WireguardServerListSchema(BaseModel):
    servers: List[WireguardInterfaceSchema]
    config_version_ts: None | float


class NetworkEndpointTypeSchema(BaseModel):
    code: str
    model: str
    manufacturer: str


class NetworkEndpointSchema(BaseModel):
    code: str
    project_code: str
    serial_number: str
    network_endpoint_type: NetworkEndpointTypeSchema


class WireguardClientConfigurationSchema(BaseModel):
    interface: WireguardInterfaceSchema
    network_endpoint: NetworkEndpointSchema
    client: WireguardClientSchema
    config_version_ts: None | float


class SSHPublicKeySchema(BaseModel):
    code: str
    network_endpoint: NetworkEndpointSchema
    public_key: str
    port: int
    comment: Optional[str]


_HealthcheckAdaptor = TypeAdapter(HealthcheckSchema)
_GeneratedKeysAdaptor = TypeAdapter(GeneratedKeysSchema)
_SSHPublicKeyListAdaptor = TypeAdapter(List[SSHPublicKeySchema])
_SSHPublicKeyAdaptor = TypeAdapter(SSHPublicKeySchema)
_NetworkEndpointAdaptor = TypeAdapter(NetworkEndpointSchema)
_WireguardClientAdaptor = TypeAdapter(WireguardClientSchema)
_BoolAdaptor: TypeAdapter = TypeAdapter(bool_schema())
_WireguardClientConfigurationAdaptor = TypeAdapter(WireguardClientConfigurationSchema)
_WireguardServerListAdaptor = TypeAdapter(WireguardServerListSchema)
_OptionalFloatAdaptor: TypeAdapter[float | None] = TypeAdapter(float | None)


class MercutoDevicesService:
    def __init__(self, client: 'MercutoClient', path: str = '/devices-service') -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> HealthcheckSchema:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return _HealthcheckAdaptor.validate_json(r.text)

    def generate_keys(self, ssh_algorithm) -> GeneratedKeysSchema:

        r = self._client.request(f"{self._path}/generate_keys", "POST",
                                 json=ssh_algorithm.dict()
                                 )
        return _GeneratedKeysAdaptor.validate_json(r.text)

    def ssh_public_keys(self) -> List[SSHPublicKeySchema]:
        r = self._client.request(f"{self._path}/ssh/public_keys", "GET")
        return _SSHPublicKeyListAdaptor.validate_json(r.text)

    def ssh_public_key_put(self, network_endpoint_code, ssh_public_key) -> SSHPublicKeySchema:
        r = self._client.request(f"{self._path}/ssh/public_key", "PUT",
                                 json=dict(
                                     network_endpoint_code=network_endpoint_code,
                                     public_key=ssh_public_key))
        return _SSHPublicKeyAdaptor.validate_json(r.text)

    def ssh_public_key_get(self,
                           network_endpoint_code: Optional[str] = None,
                           ssh_public_key_code: Optional[str] = None) -> SSHPublicKeySchema:
        if network_endpoint_code is not None:
            params = dict(
                network_endpoint_code=network_endpoint_code,
            )
        elif ssh_public_key_code is not None:
            params = dict(
                ssh_public_key_code=ssh_public_key_code,
            )
        else:
            raise TypeError("network_endpoint_code or ssh_public_key_code is required")
        r = self._client.request(f"{self._path}/ssh/public_key", "GET", params=params)

        return _SSHPublicKeyAdaptor.validate_json(r.text)

    def network_endpoint_create(self,
                                network_endpoint_type_code: str,
                                serial_number: str,
                                project_code: str
                                ) -> NetworkEndpointSchema:
        r = self._client.request(f"{self._path}/network_endpoint", "PUT",
                                 params=dict(
                                     network_endpoint_type_code=network_endpoint_type_code,
                                     serial_number=serial_number,
                                     project_code=project_code))
        return _NetworkEndpointAdaptor.validate_json(r.text)

    def network_endpoint(self,
                         network_endpoint_code: Optional[str] = None,
                         serial_number: Optional[str] = None
                         ) -> NetworkEndpointSchema:
        params = None
        if network_endpoint_code is not None:
            params = dict(network_endpoint_code=network_endpoint_code)
        elif serial_number is not None:
            params = dict(serial_number=serial_number)
        else:
            raise TypeError("network_endpoint_code or serial_number is required")

        try:
            r = self._client.request(f"{self._path}/network_endpoint", "GET",
                                     params=params)
            ta = TypeAdapter(NetworkEndpointSchema)
            return ta.validate_json(r.text)
        except MercutoHTTPException as e:
            if int(e.status_code) == 404:
                raise MercutoNotFoundException(e)
            raise e

    def wireguard_client_get(self,
                             network_endpoint_code: Optional[str] = None,
                             wireguard_client_code: Optional[str] = None) -> WireguardClientSchema:
        if network_endpoint_code is not None:
            params = dict(
                network_endpoint_code=network_endpoint_code,
            )
        elif wireguard_client_code is not None:
            params = dict(
                wireguard_client_code=wireguard_client_code,
            )
        else:
            raise TypeError("network_endpoint_code or wireguard_client_code is required")
        try:
            r = self._client.request(f"{self._path}/wireguard/client", "GET", params=params)
        except MercutoClientException as e:
            raise MercutoNotFoundException(e)

        return _WireguardClientAdaptor.validate_json(r.text)

    def wireguard_client_create(self,
                                network_endpoint_code: str,
                                public_key: str,
                                allowed_ips: Optional[str] = None) -> WireguardClientSchema:
        params = dict(
            network_endpoint_code=network_endpoint_code,
            public_key=public_key,
        )
        if allowed_ips is not None:
            params['allowed_ips'] = allowed_ips
        r = self._client.request(f"{self._path}/wireguard/client", "PUT", params=params)

        return _WireguardClientAdaptor.validate_json(r.text)

    def wireguard_client_delete(self,
                                network_endpoint_code: Optional[str] = None,
                                wireguard_client_code: Optional[str] = None) -> bool:
        if network_endpoint_code is not None:
            params = dict(
                network_endpoint_code=network_endpoint_code,
            )
        elif wireguard_client_code is not None:
            params = dict(
                wireguard_client_code=wireguard_client_code,
            )
        else:
            raise TypeError("network_endpoint_code or wireguard_client_code is required")
        r = self._client.request(f"{self._path}/wireguard/client", "DELETE", params=params)
        return _BoolAdaptor.validate_json(r.text)

    def wireguard_client_configuration(self, network_endpoint_code: str):
        r = self._client.request(f"{self._path}/wireguard/client/configuration", "GET",
                                 params={
                                     "network_endpoint_code": network_endpoint_code
                                 })
        return _WireguardClientConfigurationAdaptor.validate_json(r.text)

    def wireguard_server_configuration(self):
        r = self._client.request(f"{self._path}/wireguard/server/configuration", "GET")
        return _WireguardServerListAdaptor.validate_json(r.text)

    def wireguard_server_set_config_ts(self, ts: float):
        r = self._client.request(f"{self._path}/wireguard/server/config-version", "POST",
                                 params={"config_version_ts": ts})
        return _OptionalFloatAdaptor.validate_json(r.text)

    def wireguard_server_get_config_ts(self):
        r = self._client.request(f"{self._path}/wireguard/server/config-version", "GET",)
        return _OptionalFloatAdaptor.validate_json(r.text)
