import logging
import secrets
import uuid
from typing import Dict, List, Optional, Union

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.endpoint import (DeviceStatsSchema, Healthcheck,
                                MercutoEndpointService, NetworkEndpointSchema,
                                NetworkEndpointTypeOutSchema, PeerStatsSchema,
                                SSHKeyPair, SSHPublicKeySchema,
                                WireguardClientConfigurationSchema,
                                WireguardClientSchema,
                                WireguardInterfaceSchema, WireguardKeyPair,
                                WireguardServerStatsSchema)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)


class MockMercutoEndpointService(
    MercutoEndpointService, metaclass=EnforceOverridesMeta
):
    def __init__(self, client: "MercutoClient") -> None:
        super().__init__(
            client=client, path="/mock-endpoint-service-method-not-implemented"
        )

        # In-memory stores for mock data
        self._network_endpoint_types: Dict[str, NetworkEndpointTypeOutSchema] = {}
        self._network_endpoints: Dict[str, NetworkEndpointSchema] = {}
        self._ssh_public_keys: Dict[str, SSHPublicKeySchema] = {}
        self._wireguard_interfaces: Dict[str, WireguardInterfaceSchema] = {}
        self._wireguard_clients: Dict[str, WireguardClientSchema] = {}

    def healthcheck(self) -> Healthcheck:
        return Healthcheck(status='ok')

    # --- Network Endpoint Types ---
    def list_network_endpoint_types(
        self, offset: int = 0, limit: int = 100
    ) -> Union[List[NetworkEndpointTypeOutSchema], int]:
        all_types = list(self._network_endpoint_types.values())
        if limit == 0:
            return len(all_types)
        return all_types[offset:offset + limit]

    def create_network_endpoint_type(
        self, model: str, manufacturer: str
    ) -> NetworkEndpointTypeOutSchema:
        code = str(uuid.uuid4())
        endpoint_type = NetworkEndpointTypeOutSchema(
            code=code, model=model, manufacturer=manufacturer
        )
        self._network_endpoint_types[code] = endpoint_type
        return endpoint_type

    # --- Network Endpoints ---
    def list_network_endpoints(
        self, project_code: str, offset: int = 0, limit: int = 100
    ) -> Union[List[NetworkEndpointSchema], int]:
        endpoints = [
            e
            for e in self._network_endpoints.values()
            if e.project_code == project_code
        ]
        if limit == 0:
            return len(endpoints)
        return endpoints[offset:offset + limit]

    def create_network_endpoint(
        self, network_endpoint_type_code: str, serial_number: str, project_code: str
    ) -> NetworkEndpointSchema:
        if network_endpoint_type_code not in self._network_endpoint_types:
            raise MercutoHTTPException("Network endpoint type not found", 404)

        code = str(uuid.uuid4())
        endpoint_type = self._network_endpoint_types[network_endpoint_type_code]
        endpoint = NetworkEndpointSchema(
            code=code,
            project_code=project_code,
            serial_number=serial_number,
            network_endpoint_type=endpoint_type,
        )
        self._network_endpoints[code] = endpoint
        return endpoint

    def get_network_endpoint(
        self, project_code: str, serial_number: str
    ) -> NetworkEndpointSchema:
        for endpoint in self._network_endpoints.values():
            if (
                endpoint.project_code == project_code and endpoint.serial_number == serial_number
            ):
                return endpoint
        raise MercutoHTTPException("Network endpoint not found", 404)

    # --- SSH Key Management ---
    def generate_ssh_keys(self, name: str) -> SSHKeyPair:
        # Generate mock SSH keys
        private_key = f"-----BEGIN OPENSSH PRIVATE KEY-----\n{secrets.token_urlsafe(64)}\n-----END OPENSSH PRIVATE KEY-----"
        public_key = f"ssh-ed25519 {secrets.token_urlsafe(43)} {name}"
        return SSHKeyPair(name=name, public_key=public_key, private_key=private_key)

    def list_ssh_public_keys(
        self, project_code: str, offset: int = 0, limit: int = 100
    ) -> Union[List[SSHPublicKeySchema], int]:
        keys = [
            k
            for k in self._ssh_public_keys.values()
            if k.network_endpoint.project_code == project_code
        ]
        if limit == 0:
            return len(keys)
        return keys[offset: offset + limit]

    def create_ssh_public_key(
        self,
        network_endpoint_code: str,
        public_key: str,
        port: int,
        comment: Optional[str] = None,
    ) -> SSHPublicKeySchema:
        if network_endpoint_code not in self._network_endpoints:
            raise MercutoHTTPException("Network endpoint not found", 404)

        code = str(uuid.uuid4())
        endpoint = self._network_endpoints[network_endpoint_code]
        ssh_key = SSHPublicKeySchema(
            code=code,
            network_endpoint=endpoint,
            public_key=public_key,
            port=port,
            comment=comment,
        )
        self._ssh_public_keys[code] = ssh_key
        return ssh_key

    def get_ssh_public_key(
        self, network_endpoint_code: str, port: int
    ) -> SSHPublicKeySchema:
        for key in self._ssh_public_keys.values():
            if key.network_endpoint.code == network_endpoint_code and key.port == port:
                return key
        raise MercutoHTTPException("SSH public key not found", 404)

    # --- WireGuard Key Management ---
    def generate_wireguard_keys(self) -> WireguardKeyPair:
        # Generate mock WireGuard keys (base64-like strings)
        private_key = secrets.token_urlsafe(32)
        public_key = secrets.token_urlsafe(32)
        return WireguardKeyPair(public_key=public_key, private_key=private_key)

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
        code = str(uuid.uuid4())

        # Generate keys if not provided
        if private_key is None or public_key is None:
            keys = self.generate_wireguard_keys()
            if private_key is None:
                private_key = keys.private_key
            if public_key is None:
                public_key = keys.public_key

        # Calculate IP address from subnet and bits
        ip_address = f"{subnet}.0.0.1/{bits}"

        interface = WireguardInterfaceSchema(
            code=code,
            tenant_code=tenant_code,
            isolation_group_code=isolation_group_code,
            interface_name=interface_name,
            private_key=private_key,
            public_key=public_key,
            port=port,
            subnet=subnet,
            bits=bits,
            hostname=hostname,
            ip_address=ip_address,
            clients=[],
        )
        self._wireguard_interfaces[code] = interface
        return interface

    def get_wireguard_interface(self, interface_code: str) -> WireguardInterfaceSchema:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)
        return self._wireguard_interfaces[interface_code]

    def delete_wireguard_interface(self, interface_code: str) -> None:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)

        # Delete associated clients
        clients_to_delete = [
            code
            for code, client in self._wireguard_clients.items()
            if client.interface_code == interface_code
        ]
        for code in clients_to_delete:
            del self._wireguard_clients[code]

        del self._wireguard_interfaces[interface_code]

    # --- WireGuard Client Management ---
    def register_wireguard_client(
        self,
        interface_code: str,
        network_endpoint_code: str,
        public_key: str,
        allowed_ips: str,
        description: Optional[str] = None,
    ) -> WireguardClientSchema:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)
        if network_endpoint_code not in self._network_endpoints:
            raise MercutoHTTPException("Network endpoint not found", 404)

        interface = self._wireguard_interfaces[interface_code]

        # Generate client ID (simple incremental based on existing clients)
        existing_clients = [
            c
            for c in self._wireguard_clients.values()
            if c.interface_code == interface_code
        ]
        client_id = len(existing_clients) + 2  # Start from 2 (server is usually 1)

        # Generate IP address for client
        ip_address = f"{interface.subnet}.0.0.{client_id}/{interface.bits}"

        code = str(uuid.uuid4())
        client = WireguardClientSchema(
            code=code,
            public_key=public_key,
            client_id=client_id,
            ip_address=ip_address,
            allowed_ips=allowed_ips,
            interface_code=interface_code,
            network_endpoint_code=network_endpoint_code,
            description=description,
        )
        self._wireguard_clients[code] = client
        return client

    def get_wireguard_client(
        self, network_endpoint_code: str, interface_code: str
    ) -> WireguardClientSchema:
        for client in self._wireguard_clients.values():
            if (
                client.network_endpoint_code == network_endpoint_code and  # noqa: W504
                client.interface_code == interface_code
            ):
                return client
        raise MercutoHTTPException("WireGuard client not found", 404)

    def delete_wireguard_client(
        self, network_endpoint_code: str, interface_code: str
    ) -> None:
        for code, client in list(self._wireguard_clients.items()):
            if (
                client.network_endpoint_code == network_endpoint_code and  # noqa: W504
                client.interface_code == interface_code
            ):
                del self._wireguard_clients[code]
                return
        raise MercutoHTTPException("WireGuard client not found", 404)

    def get_wireguard_client_configuration(
        self, network_endpoint_code: str, interface_code: str
    ) -> WireguardClientConfigurationSchema:
        client = self.get_wireguard_client(network_endpoint_code, interface_code)
        interface = self.get_wireguard_interface(interface_code)

        if network_endpoint_code not in self._network_endpoints:
            raise MercutoHTTPException("Network endpoint not found", 404)

        endpoint = self._network_endpoints[network_endpoint_code]

        import time

        config_version_ts = time.time()

        return WireguardClientConfigurationSchema(
            config_version_ts=config_version_ts,
            interface=interface,
            network_endpoint=endpoint,
            client=client,
        )

    # --- WireGuard Server Information ---
    def get_wireguard_server_config_version(self, interface_code: str) -> float:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)

        import time

        return time.time()

    def get_wireguard_server_version(self, interface_code: str) -> str:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)

        return "1.0.20210914"

    def get_wireguard_server_stats(
        self, interface_code: str
    ) -> WireguardServerStatsSchema:
        if interface_code not in self._wireguard_interfaces:
            raise MercutoHTTPException("WireGuard interface not found", 404)

        interface = self._wireguard_interfaces[interface_code]

        # Create mock peer stats for clients
        peers: Dict[str, PeerStatsSchema] = {}
        clients = [
            c
            for c in self._wireguard_clients.values()
            if c.interface_code == interface_code
        ]

        for client in clients:
            peers[client.public_key] = PeerStatsSchema(
                endpoint="(none)",
                allowed_ips=[client.allowed_ips],
                latest_handshake="0",
                transfer_rx="0",
                transfer_tx="0",
                persistent_keepalive="off",
            )

        device_stats = DeviceStatsSchema(
            public_key=interface.public_key,
            listen_port=str(interface.port),
            fwmark="off",
            peers=peers,
        )

        import time

        timestamp = str(int(time.time()))

        return WireguardServerStatsSchema(
            timestamp=timestamp, value={interface.interface_name: device_stats}
        )
