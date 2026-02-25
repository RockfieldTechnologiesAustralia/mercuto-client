from typing import TYPE_CHECKING, Dict, List, Optional, Union

from pydantic import TypeAdapter

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
        self, project_code: str, serial_number: str
    ) -> NetworkEndpointSchema:
        """
        Retrieve a specific network endpoint by project code and serial number.
        """
        r = self._client.request(
            f"{self._path}/network_endpoint",
            "GET",
            params={"project_code": project_code, "serial_number": serial_number},
        )
        return NetworkEndpointSchema.model_validate_json(r.text)

    # --- SSH Key Management ---
    def generate_ssh_keys(self, name: str) -> SSHKeyPair:
        """
        Generate a new SSH key pair with the specified name.
        """
        r = self._client.request(
            f"{self._path}/ssh/generate_keys", "POST", params={"name": name}
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
        port: int,
        comment: Optional[str] = None,
    ) -> SSHPublicKeySchema:
        """
        Register a new SSH public key for a network endpoint.
        """
        params: PayloadType = {
            "network_endpoint_code": network_endpoint_code,
            "public_key": public_key,
            "port": port,
        }
        if comment is not None:
            params["comment"] = comment
        r = self._client.request(f"{self._path}/ssh/public_key", "POST", params=params)
        return SSHPublicKeySchema.model_validate_json(r.text)

    def get_ssh_public_key(
        self, network_endpoint_code: str, port: int
    ) -> SSHPublicKeySchema:
        """
        Retrieve a specific SSH public key by network endpoint code and port.
        """
        r = self._client.request(
            f"{self._path}/ssh/public_key",
            "GET",
            params={"network_endpoint_code": network_endpoint_code, "port": port},
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
        port: int,
        subnet: int,
        bits: int,
        hostname: str,
        tenant_code: Optional[str] = None,
        isolation_group_code: Optional[str] = None,
        private_key: Optional[str] = None,
        public_key: Optional[str] = None,
    ) -> WireguardInterfaceSchema:
        """
        Create a new WireGuard interface.
        """
        params: PayloadType = {
            "interface_name": interface_name,
            "port": port,
            "subnet": subnet,
            "bits": bits,
            "hostname": hostname,
        }
        if tenant_code is not None:
            params["tenant_code"] = tenant_code
        if isolation_group_code is not None:
            params["isolation_group_code"] = isolation_group_code
        if private_key is not None:
            params["private_key"] = private_key
        if public_key is not None:
            params["public_key"] = public_key

        r = self._client.request(
            f"{self._path}/wireguard/interface", "POST", params=params
        )
        return WireguardInterfaceSchema.model_validate_json(r.text)

    def get_wireguard_interface(self, interface_code: str) -> WireguardInterfaceSchema:
        """
        Retrieve a specific WireGuard interface by code.
        """
        r = self._client.request(
            f"{self._path}/wireguard/interface",
            "GET",
            params={"interface_code": interface_code},
        )
        return WireguardInterfaceSchema.model_validate_json(r.text)

    def delete_wireguard_interface(self, interface_code: str) -> None:
        """
        Delete a WireGuard interface.
        """
        self._client.request(
            f"{self._path}/wireguard/interface",
            "DELETE",
            params={"interface_code": interface_code},
        )
        return None

    # --- WireGuard Client Management ---
    def register_wireguard_client(
        self,
        interface_code: str,
        network_endpoint_code: str,
        public_key: str,
        allowed_ips: str,
        description: Optional[str] = None,
    ) -> WireguardClientSchema:
        """
        Register a new WireGuard client.
        """
        params: PayloadType = {
            "interface_code": interface_code,
            "network_endpoint_code": network_endpoint_code,
            "public_key": public_key,
            "allowed_ips": allowed_ips,
        }
        if description is not None:
            params["description"] = description

        r = self._client.request(
            f"{self._path}/wireguard/client", "POST", params=params
        )
        return WireguardClientSchema.model_validate_json(r.text)

    def get_wireguard_client(
        self, network_endpoint_code: str, interface_code: str
    ) -> WireguardClientSchema:
        """
        Retrieve a specific WireGuard client by network endpoint and interface.
        """
        r = self._client.request(
            f"{self._path}/wireguard/client",
            "GET",
            params={
                "network_endpoint_code": network_endpoint_code,
                "interface_code": interface_code,
            },
        )
        return WireguardClientSchema.model_validate_json(r.text)

    def delete_wireguard_client(
        self, network_endpoint_code: str, interface_code: str
    ) -> None:
        """
        Delete a WireGuard client.
        """
        self._client.request(
            f"{self._path}/wireguard/client",
            "DELETE",
            params={
                "network_endpoint_code": network_endpoint_code,
                "interface_code": interface_code,
            },
        )
        return None

    def get_wireguard_client_configuration(
        self, network_endpoint_code: str, interface_code: str
    ) -> WireguardClientConfigurationSchema:
        """
        Retrieve the full WireGuard client configuration.
        """
        r = self._client.request(
            f"{self._path}/wireguard/client/configuration",
            "GET",
            params={
                "network_endpoint_code": network_endpoint_code,
                "interface_code": interface_code,
            },
        )
        return WireguardClientConfigurationSchema.model_validate_json(r.text)

    # --- WireGuard Server Information ---
    def get_wireguard_server_config_version(self, interface_code: str) -> float:
        """
        Get the current configuration version timestamp for a WireGuard interface.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/config-version",
            "GET",
            params={"interface_code": interface_code},
        )
        return float(r.text)

    def get_wireguard_server_version(self, interface_code: str) -> str:
        """
        Get the WireGuard server version for an interface.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/server-version",
            "GET",
            params={"interface_code": interface_code},
        )
        return r.text.strip('"')

    def get_wireguard_server_stats(
        self, interface_code: str
    ) -> WireguardServerStatsSchema:
        """
        Get statistics for a WireGuard server interface.
        """
        r = self._client.request(
            f"{self._path}/wireguard/server/stats",
            "GET",
            params={"interface_code": interface_code},
        )
        return WireguardServerStatsSchema.model_validate_json(r.text)
