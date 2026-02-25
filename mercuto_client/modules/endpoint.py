from typing import TYPE_CHECKING, Dict, List, Optional, Union

from pydantic import Field, TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from . import PayloadType
from ._util import BaseModel


class Healthcheck(BaseModel):
    status: str


# Network Endpoint Types
class NetworkEndpointTypeOutSchema(BaseModel):
    code: str
    model: str
    manufacturer: str


# Network Endpoints
class NetworkEndpointSchema(BaseModel):
    code: str
    project_code: str
    serial_number: str
    network_endpoint_type: NetworkEndpointTypeOutSchema


# SSH Algorithm Parameters
class RSAParams(BaseModel):
    key_size: int = Field(ge=2048, le=8192, default=4096)


class Ed25519Params(BaseModel):
    pass


class RSAAlgorithm(BaseModel):
    algorithm: str = "rsa"
    params: Optional[RSAParams] = Field(default_factory=RSAParams)


class Ed25519Algorithm(BaseModel):
    algorithm: str = "ed25519"
    params: Optional[Ed25519Params] = Field(default_factory=Ed25519Params)


# SSH Key Pair
class SSHKeyPair(BaseModel):
    name: str
    public_key: str
    private_key: str


# SSH Public Key
class SSHPublicKeySchema(BaseModel):
    code: str
    network_endpoint: NetworkEndpointSchema
    public_key: str
    port: int
    comment: Optional[str] = None


# WireGuard Key Pair
class WireguardKeyPair(BaseModel):
    public_key: str
    private_key: str


# WireGuard Client
class WireguardClientSchema(BaseModel):
    code: str
    public_key: str
    client_id: int
    ip_address: str
    allowed_ips: str
    interface_code: str
    network_endpoint_code: str
    description: Optional[str] = None


# WireGuard Interface
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
    clients: Optional[List[WireguardClientSchema]] = None


# WireGuard Client Configuration
class WireguardClientConfigurationSchema(BaseModel):
    config_version_ts: float
    interface: WireguardInterfaceSchema
    network_endpoint: NetworkEndpointSchema
    client: WireguardClientSchema


# WireGuard Server Stats
class PeerStatsSchema(BaseModel):
    endpoint: str
    allowed_ips: List[str]
    latest_handshake: str
    transfer_rx: str
    transfer_tx: str
    persistent_keepalive: str


class DeviceStatsSchema(BaseModel):
    public_key: str
    listen_port: str
    fwmark: str
    peers: Dict[str, PeerStatsSchema]


class WireguardServerStatsSchema(BaseModel):
    timestamp: str
    value: Dict[str, DeviceStatsSchema]


# --- TypeAdapters for lists ---
_NetworkEndpointTypeListAdapter = TypeAdapter(list[NetworkEndpointTypeOutSchema])
_NetworkEndpointListAdapter = TypeAdapter(list[NetworkEndpointSchema])
_SSHPublicKeyListAdapter = TypeAdapter(list[SSHPublicKeySchema])


class MercutoEndpointService:
    def __init__(
        self, client: "MercutoClient", path: str = "/endpoint-service"
    ) -> None:
        self._client = client
        self._path = path

    def healthcheck(self) -> Healthcheck:
        r = self._client.request(f"{self._path}/healthcheck", "GET")
        return Healthcheck.model_validate_json(r.text)

    # --- Network Endpoint Types ---
    def list_network_endpoint_types(
        self, offset: int = 0, limit: int = 100
    ) -> Union[List[NetworkEndpointTypeOutSchema], int]:
        """
        Retrieve all registered network endpoint types with pagination.
        Set limit=0 to get total count.
        """
        r = self._client.request(
            f"{self._path}/network_endpoint_types",
            "GET",
            params={"offset": offset, "limit": limit},
        )
        if limit == 0:
            return int(r.text)
        return _NetworkEndpointTypeListAdapter.validate_json(r.text)

    def create_network_endpoint_type(
        self, model: str, manufacturer: str
    ) -> NetworkEndpointTypeOutSchema:
        """
        Register a new type of network endpoint device (e.g., router, access point)
        by model and manufacturer.
        """
        r = self._client.request(
            f"{self._path}/network_endpoint_types",
            "POST",
            params={"model": model, "manufacturer": manufacturer},
        )
        return NetworkEndpointTypeOutSchema.model_validate_json(r.text)

    # --- Network Endpoints ---
    def list_network_endpoints(
        self, project_code: str, offset: int = 0, limit: int = 100
    ) -> Union[List[NetworkEndpointSchema], int]:
        """
        Retrieve all network endpoints for a project with pagination.
        Set limit=0 to get total count.
        """
        r = self._client.request(
            f"{self._path}/network_endpoints",
            "GET",
            params={"project_code": project_code, "offset": offset, "limit": limit},
        )
        if limit == 0:
            return int(r.text)
        return _NetworkEndpointListAdapter.validate_json(r.text)

    def create_network_endpoint(
        self, network_endpoint_type_code: str, serial_number: str, project_code: str
    ) -> NetworkEndpointSchema:
        """
        Register a new network endpoint device with a type, serial number,
        and associated project.
        """
        r = self._client.request(
            f"{self._path}/network_endpoint",
            "POST",
            params={
                "network_endpoint_type_code": network_endpoint_type_code,
                "serial_number": serial_number,
                "project_code": project_code,
            },
        )
        return NetworkEndpointSchema.model_validate_json(r.text)

    def get_network_endpoint(
        self,
        network_endpoint_code: Optional[str] = None,
        serial_number: Optional[str] = None,
    ) -> NetworkEndpointSchema:
        """
        Retrieve a specific network endpoint by code or serial number.
        Provide either network_endpoint_code OR serial_number (not both).
        """
        params: PayloadType = {}
        if network_endpoint_code is not None:
            params["network_endpoint_code"] = network_endpoint_code
        if serial_number is not None:
            params["serial_number"] = serial_number
        r = self._client.request(
            f"{self._path}/network_endpoint",
            "GET",
            params=params,
        )
        return NetworkEndpointSchema.model_validate_json(r.text)

    # --- SSH Key Management ---
    def generate_ssh_keys(
        self, algorithm: Union[RSAAlgorithm, Ed25519Algorithm]
    ) -> SSHKeyPair:
        """
        Generate a new SSH key pair with the specified algorithm.
        For RSA keys, you can specify key_size (2048-8192, default 4096).
        For Ed25519 keys, no additional parameters are needed.

        Example:
            # Generate RSA key with default size (4096)
            client.endpoint.generate_ssh_keys(RSAAlgorithm())

            # Generate RSA key with custom size
            client.endpoint.generate_ssh_keys(
                RSAAlgorithm(params=RSAParams(key_size=2048))
            )

            # Generate Ed25519 key
            client.endpoint.generate_ssh_keys(Ed25519Algorithm())
        """
        r = self._client.request(
            f"{self._path}/ssh/generate_keys",
            "POST",
            json=algorithm.model_dump(),
        )
        return SSHKeyPair.model_validate_json(r.text)

    def list_ssh_public_keys(
        self, project_code: str, offset: int = 0, limit: int = 100
    ) -> Union[List[SSHPublicKeySchema], int]:
        """
        Retrieve all SSH public keys for a project with pagination.
        Set limit=0 to get total count.
        """
        r = self._client.request(
            f"{self._path}/ssh/public_keys",
            "GET",
            params={"project_code": project_code, "offset": offset, "limit": limit},
        )
        if limit == 0:
            return int(r.text)
        return _SSHPublicKeyListAdapter.validate_json(r.text)

    def create_ssh_public_key(
        self,
        network_endpoint_code: str,
        public_key: str,
    ) -> SSHPublicKeySchema:
        """
        Register a new SSH public key for a network endpoint.
        """
        r = self._client.request(
            f"{self._path}/ssh/public_key",
            "POST",
            json={
                "network_endpoint_code": network_endpoint_code,
                "public_key": public_key,
            },
        )
        return SSHPublicKeySchema.model_validate_json(r.text)

    def get_ssh_public_key(
        self,
        network_endpoint_code: Optional[str] = None,
        ssh_public_key_code: Optional[str] = None,
    ) -> SSHPublicKeySchema:
        """
        Retrieve a specific SSH public key by network endpoint code or SSH public key code.
        Provide either network_endpoint_code OR ssh_public_key_code (not both).
        """
        params: PayloadType = {}
        if network_endpoint_code is not None:
            params["network_endpoint_code"] = network_endpoint_code
        if ssh_public_key_code is not None:
            params["ssh_public_key_code"] = ssh_public_key_code
        r = self._client.request(
            f"{self._path}/ssh/public_key",
            "GET",
            params=params,
        )
        return SSHPublicKeySchema.model_validate_json(r.text)

    # --- WireGuard Key Management ---
    def generate_wireguard_keys(self) -> WireguardKeyPair:
        """
        Generate a new WireGuard key pair.
        """
        r = self._client.request(f"{self._path}/wireguard/generate_keys", "POST")
        return WireguardKeyPair.model_validate_json(r.text)

    # --- WireGuard Interface Management ---
    def create_wireguard_interface(
        self,
        interface_name: str,
        tenant_code: Optional[str] = None,
        isolation_group_code: Optional[str] = None,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
    ) -> WireguardInterfaceSchema:
        """
        Create a new WireGuard interface for a tenant or isolation group.
        Optionally provide keys or let the system generate them.
        Must provide exactly one of tenant_code or isolation_group_code.
        """
        body: PayloadType = {
            "interface_name": interface_name,
        }
        if tenant_code is not None:
            body["tenant_code"] = tenant_code
        if isolation_group_code is not None:
            body["isolation_group_code"] = isolation_group_code
        if private_key is not None:
            body["private_key"] = private_key
        if public_key is not None:
            body["public_key"] = public_key

        r = self._client.request(f"{self._path}/wireguard/interface", "POST", json=body)
        return WireguardInterfaceSchema.model_validate_json(r.text)

    def get_wireguard_interface(
        self,
        interface_code: Optional[str] = None,
        tenant_code: Optional[str] = None,
    ) -> WireguardInterfaceSchema:
        """
        Retrieve a WireGuard interface by interface code or tenant code.
        Provide either interface_code OR tenant_code (not both).
        """
        params: PayloadType = {}
        if interface_code is not None:
            params["interface_code"] = interface_code
        if tenant_code is not None:
            params["tenant_code"] = tenant_code
        r = self._client.request(
            f"{self._path}/wireguard/interface",
            "GET",
            params=params,
        )
        return WireguardInterfaceSchema.model_validate_json(r.text)

    def delete_wireguard_interface(self, interface_code: Optional[str] = None) -> bool:
        """
        Delete a WireGuard interface by its code.
        Returns True if deletion was successful.
        """
        params: PayloadType = {}
        if interface_code is not None:
            params["interface_code"] = interface_code
        r = self._client.request(
            f"{self._path}/wireguard/interface",
            "DELETE",
            params=params,
        )
        return r.json()

    # --- WireGuard Client Management ---
    def register_wireguard_client(
        self,
        network_endpoint_code: str,
        public_key: str,
        allowed_ips: str = "",
    ) -> WireguardClientSchema:
        """
        Register a new WireGuard client for a network endpoint.
        The system will automatically find the appropriate WireGuard interface
        based on the network endpoint's project/tenant.
        """
        params: PayloadType = {
            "network_endpoint_code": network_endpoint_code,
            "public_key": public_key,
            "allowed_ips": allowed_ips,
        }

        r = self._client.request(
            f"{self._path}/wireguard/client", "POST", params=params
        )
        return WireguardClientSchema.model_validate_json(r.text)

    def get_wireguard_client(
        self,
        network_endpoint_code: Optional[str] = None,
        wireguard_client_code: Optional[str] = None,
    ) -> WireguardClientSchema:
        """
        Retrieve a WireGuard client by network endpoint code or client code.
        Provide either network_endpoint_code OR wireguard_client_code (not both).
        """
        params: PayloadType = {}
        if network_endpoint_code is not None:
            params["network_endpoint_code"] = network_endpoint_code
        if wireguard_client_code is not None:
            params["wireguard_client_code"] = wireguard_client_code
        r = self._client.request(
            f"{self._path}/wireguard/client",
            "GET",
            params=params,
        )
        return WireguardClientSchema.model_validate_json(r.text)

    def delete_wireguard_client(
        self,
        network_endpoint_code: Optional[str] = None,
        wireguard_client_code: Optional[str] = None,
    ) -> bool:
        """
        Delete a WireGuard client by network endpoint code or client code.
        Provide either network_endpoint_code OR wireguard_client_code (not both).
        Returns True if deletion was successful.
        """
        params: PayloadType = {}
        if network_endpoint_code is not None:
            params["network_endpoint_code"] = network_endpoint_code
        if wireguard_client_code is not None:
            params["wireguard_client_code"] = wireguard_client_code
        r = self._client.request(
            f"{self._path}/wireguard/client",
            "DELETE",
            params=params,
        )
        return r.json()

    def get_wireguard_client_configuration(
        self,
        wireguard_client_code: Optional[str] = None,
        network_endpoint_code: Optional[str] = None,
    ) -> WireguardClientConfigurationSchema:
        """
        Retrieve the full WireGuard client configuration.
        Provide either wireguard_client_code OR network_endpoint_code.
        """
        params: PayloadType = {}
        if wireguard_client_code is not None:
            params["wireguard_client_code"] = wireguard_client_code
        if network_endpoint_code is not None:
            params["network_endpoint_code"] = network_endpoint_code
        r = self._client.request(
            f"{self._path}/wireguard/client/configuration",
            "GET",
            params=params,
        )
        return WireguardClientConfigurationSchema.model_validate_json(r.text)

    # --- WireGuard Server Information ---
    def get_wireguard_server_config_version(self) -> Optional[float]:
        """
        Get the current configuration version timestamp for the WireGuard server.
        Returns None if not set.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/config-version",
            "GET",
        )
        return r.json()

    def get_wireguard_server_version(self) -> Optional[float]:
        """
        Get the WireGuard server version timestamp.
        Returns None if not set.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/server-version",
            "GET",
        )
        return r.json()

    def get_wireguard_server_stats(
        self,
    ) -> Optional[List[WireguardServerStatsSchema]]:
        """
        Get statistics for all WireGuard server interfaces.
        Returns None if not available. Requires *:* ACL permissions.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/stats",
            "GET",
        )
        return r.json()
