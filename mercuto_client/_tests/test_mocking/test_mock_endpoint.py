from ... import MercutoClient
from ...modules.endpoint import (Ed25519Algorithm, NetworkEndpointSchema,
                                 NetworkEndpointTypeOutSchema, RSAAlgorithm,
                                 RSAParams, SSHPublicKeySchema,
                                 WireguardClientConfigurationSchema,
                                 WireguardClientSchema,
                                 WireguardInterfaceSchema, WireguardKeyPair,
                                 WireguardServerStatsSchema)


def test_healthcheck(client: MercutoClient) -> None:
    """Test endpoint service healthcheck."""
    health = client.endpoint().healthcheck()
    assert health.status == "ok"


# --- Network Endpoint Types Tests ---


def test_create_and_list_network_endpoint_types(client: MercutoClient) -> None:
    """Test creating and listing network endpoint types."""
    # Create a network endpoint type
    endpoint_type = client.endpoint().create_network_endpoint_type(
        model="RaspberryPi4", manufacturer="Raspberry Pi Foundation"
    )
    assert isinstance(endpoint_type, NetworkEndpointTypeOutSchema)
    assert endpoint_type.model == "RaspberryPi4"
    assert endpoint_type.manufacturer == "Raspberry Pi Foundation"

    # List all endpoint types
    types = client.endpoint().list_network_endpoint_types()
    assert isinstance(types, list)
    assert len(types) == 1
    assert types[0].code == endpoint_type.code


def test_list_network_endpoint_types_pagination(client: MercutoClient) -> None:
    """Test pagination for listing network endpoint types."""
    # Create multiple endpoint types
    client.endpoint().create_network_endpoint_type("Model1", "Manufacturer1")
    client.endpoint().create_network_endpoint_type("Model2", "Manufacturer2")
    client.endpoint().create_network_endpoint_type("Model3", "Manufacturer3")

    # Get total count
    count = client.endpoint().list_network_endpoint_types(limit=0)
    assert count == 3

    # Get paginated results
    page1 = client.endpoint().list_network_endpoint_types(offset=0, limit=2)
    assert isinstance(page1, list)
    assert len(page1) == 2

    page2 = client.endpoint().list_network_endpoint_types(offset=2, limit=2)
    assert isinstance(page2, list)
    assert len(page2) == 1


# --- Network Endpoints Tests ---


def test_create_and_list_network_endpoints(client: MercutoClient) -> None:
    """Test creating and listing network endpoints."""
    # Create endpoint type first
    endpoint_type = client.endpoint().create_network_endpoint_type(
        model="TestModel", manufacturer="TestManufacturer"
    )

    # Create network endpoint
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN12345",
        project_code="test-project",
    )
    assert isinstance(endpoint, NetworkEndpointSchema)
    assert endpoint.serial_number == "SN12345"
    assert endpoint.project_code == "test-project"
    assert endpoint.network_endpoint_type.code == endpoint_type.code

    # List endpoints
    endpoints = client.endpoint().list_network_endpoints(project_code="test-project")
    assert isinstance(endpoints, list)
    assert len(endpoints) == 1
    assert endpoints[0].code == endpoint.code


def test_get_network_endpoint_by_code(client: MercutoClient) -> None:
    """Test retrieving network endpoint by code."""
    # Create endpoint
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    created = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )

    # Get by code
    retrieved = client.endpoint().get_network_endpoint(
        network_endpoint_code=created.code
    )
    assert retrieved.code == created.code
    assert retrieved.serial_number == "SN001"


def test_get_network_endpoint_by_serial_number(client: MercutoClient) -> None:
    """Test retrieving network endpoint by serial number."""
    # Create endpoint
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    created = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN002",
        project_code="proj1",
    )

    # Get by serial number
    retrieved = client.endpoint().get_network_endpoint(serial_number="SN002")
    assert retrieved.code == created.code
    assert retrieved.serial_number == "SN002"


def test_list_network_endpoints_pagination(client: MercutoClient) -> None:
    """Test pagination for listing network endpoints."""
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )

    # Create multiple endpoints
    for i in range(5):
        client.endpoint().create_network_endpoint(
            network_endpoint_type_code=endpoint_type.code,
            serial_number=f"SN{i:03d}",
            project_code="proj1",
        )

    # Get total count
    count = client.endpoint().list_network_endpoints(project_code="proj1", limit=0)
    assert count == 5

    # Get paginated results
    page1 = client.endpoint().list_network_endpoints(
        project_code="proj1", offset=0, limit=2
    )
    assert isinstance(page1, list)
    assert len(page1) == 2


# --- SSH Key Management Tests ---


def test_generate_ssh_keys_ed25519(client: MercutoClient) -> None:
    """Test generating Ed25519 SSH keys."""
    key_pair = client.endpoint().generate_ssh_keys(Ed25519Algorithm())
    assert key_pair.name == "ed25519"
    assert key_pair.public_key.startswith("ssh-ed25519")
    assert "BEGIN OPENSSH PRIVATE KEY" in key_pair.private_key


def test_generate_ssh_keys_rsa_default(client: MercutoClient) -> None:
    """Test generating RSA SSH keys with default size."""
    key_pair = client.endpoint().generate_ssh_keys(RSAAlgorithm())
    assert key_pair.name == "rsa-4096"
    assert key_pair.public_key.startswith("ssh-ed25519")  # Mock uses ed25519 format
    assert "BEGIN OPENSSH PRIVATE KEY" in key_pair.private_key


def test_generate_ssh_keys_rsa_custom_size(client: MercutoClient) -> None:
    """Test generating RSA SSH keys with custom size."""
    key_pair = client.endpoint().generate_ssh_keys(
        RSAAlgorithm(params=RSAParams(key_size=2048))
    )
    assert key_pair.name == "rsa-2048"


def test_create_and_list_ssh_public_keys(client: MercutoClient) -> None:
    """Test creating and listing SSH public keys."""
    # Setup: Create endpoint
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )

    # Create SSH public key
    ssh_key = client.endpoint().create_ssh_public_key(
        network_endpoint_code=endpoint.code,
        public_key="ssh-rsa AAAAB3NzaC1yc2EA... test@example.com",
    )
    assert isinstance(ssh_key, SSHPublicKeySchema)
    assert ssh_key.network_endpoint.code == endpoint.code
    assert ssh_key.port == 22  # Mock default

    # List SSH keys
    keys = client.endpoint().list_ssh_public_keys(project_code="proj1")
    assert isinstance(keys, list)
    assert len(keys) == 1
    assert keys[0].code == ssh_key.code


def test_get_ssh_public_key_by_code(client: MercutoClient) -> None:
    """Test retrieving SSH public key by code."""
    # Setup
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    created = client.endpoint().create_ssh_public_key(
        network_endpoint_code=endpoint.code,
        public_key="ssh-rsa AAAAB3...",
    )

    # Get by SSH public key code
    retrieved = client.endpoint().get_ssh_public_key(ssh_public_key_code=created.code)
    assert retrieved.code == created.code


def test_get_ssh_public_key_by_endpoint_code(client: MercutoClient) -> None:
    """Test retrieving SSH public key by network endpoint code."""
    # Setup
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    created = client.endpoint().create_ssh_public_key(
        network_endpoint_code=endpoint.code,
        public_key="ssh-rsa AAAAB3...",
    )

    # Get by network endpoint code
    retrieved = client.endpoint().get_ssh_public_key(
        network_endpoint_code=endpoint.code
    )
    assert retrieved.code == created.code


def test_list_ssh_public_keys_pagination(client: MercutoClient) -> None:
    """Test pagination for listing SSH public keys."""
    # Setup
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )

    # Create multiple SSH keys
    for i in range(3):
        client.endpoint().create_ssh_public_key(
            network_endpoint_code=endpoint.code,
            public_key=f"ssh-rsa AAAAB3{i}...",
        )

    # Get total count
    count = client.endpoint().list_ssh_public_keys(project_code="proj1", limit=0)
    assert count == 3

    # Get paginated results
    page1 = client.endpoint().list_ssh_public_keys(
        project_code="proj1", offset=0, limit=2
    )
    assert isinstance(page1, list)
    assert len(page1) == 2


# --- WireGuard Key Management Tests ---


def test_generate_wireguard_keys(client: MercutoClient) -> None:
    """Test generating WireGuard key pairs."""
    key_pair = client.endpoint().generate_wireguard_keys()
    assert isinstance(key_pair, WireguardKeyPair)
    assert len(key_pair.public_key) > 0
    assert len(key_pair.private_key) > 0


# --- WireGuard Interface Management Tests ---


def test_create_wireguard_interface_with_tenant(client: MercutoClient) -> None:
    """Test creating WireGuard interface for a tenant."""
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert isinstance(interface, WireguardInterfaceSchema)
    assert interface.interface_name == "wg0"
    assert interface.tenant_code == "tenant1"
    assert interface.port == 51820  # Mock default
    assert interface.public_key is not None
    # Verify server_host field
    assert interface.server_host is not None
    assert interface.server_host.code is not None
    assert interface.server_host.hostname == "localhost"


def test_create_wireguard_interface_with_custom_keys(client: MercutoClient) -> None:
    """Test creating WireGuard interface with custom keys."""
    keys = client.endpoint().generate_wireguard_keys()
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg1",
        tenant_code="tenant1",
        private_key=keys.private_key,
        public_key=keys.public_key,
    )
    assert interface.public_key == keys.public_key
    assert interface.private_key == keys.private_key


def test_create_wireguard_interface_with_isolation_group(client: MercutoClient) -> None:
    """Test creating WireGuard interface for an isolation group."""
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg2",
        isolation_group_code="iso-group-1",
    )
    assert interface.isolation_group_code == "iso-group-1"


def test_get_wireguard_interface_by_code(client: MercutoClient) -> None:
    """Test retrieving WireGuard interface by code."""
    created = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )

    retrieved = client.endpoint().get_wireguard_interface(interface_code=created.code)
    assert retrieved.code == created.code
    assert retrieved.interface_name == "wg0"


def test_get_wireguard_interface_by_tenant(client: MercutoClient) -> None:
    """Test retrieving WireGuard interface by tenant code."""
    created = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )

    retrieved = client.endpoint().get_wireguard_interface(tenant_code="tenant1")
    assert retrieved.code == created.code
    assert retrieved.tenant_code == "tenant1"


def test_delete_wireguard_interface(client: MercutoClient) -> None:
    """Test deleting WireGuard interface."""
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )

    result = client.endpoint().delete_wireguard_interface(interface_code=interface.code)
    assert result is True

    # Verify deletion by attempting to retrieve
    try:
        client.endpoint().get_wireguard_interface(interface_code=interface.code)
        assert False, "Should have raised exception"
    except Exception:
        pass  # Expected


# --- WireGuard Client Management Tests ---


def test_register_wireguard_client(client: MercutoClient) -> None:
    """Test registering a WireGuard client."""
    # Setup: Create interface and endpoint
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.interface_name == "wg0"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )

    # Register client
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
        allowed_ips="10.0.0.0/24",
    )
    assert isinstance(wg_client, WireguardClientSchema)
    assert wg_client.network_endpoint_code == endpoint.code
    assert wg_client.public_key == keys.public_key
    assert wg_client.allowed_ips == "10.0.0.0/24"
    assert wg_client.client_id >= 2
    assert wg_client.interface_code == interface.code


def test_get_wireguard_client_by_endpoint_code(client: MercutoClient) -> None:
    """Test retrieving WireGuard client by network endpoint code."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.tenant_code == "tenant1"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    created = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Get by network endpoint code
    retrieved = client.endpoint().get_wireguard_client(
        network_endpoint_code=endpoint.code
    )
    assert retrieved.code == created.code


def test_get_wireguard_client_by_code(client: MercutoClient) -> None:
    """Test retrieving WireGuard client by client code."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.interface_name == "wg0"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    created = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Get by client code
    retrieved = client.endpoint().get_wireguard_client(
        wireguard_client_code=created.code
    )
    assert retrieved.code == created.code


def test_delete_wireguard_client_by_endpoint_code(client: MercutoClient) -> None:
    """Test deleting WireGuard client by network endpoint code."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.interface_name == "wg0"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )
    assert wg_client.interface_code == interface.code

    # Delete
    result = client.endpoint().delete_wireguard_client(
        network_endpoint_code=endpoint.code
    )
    assert result is True


def test_delete_wireguard_client_by_code(client: MercutoClient) -> None:
    """Test deleting WireGuard client by client code."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.tenant_code == "tenant1"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Delete
    result = client.endpoint().delete_wireguard_client(
        wireguard_client_code=wg_client.code
    )
    assert result is True


def test_get_wireguard_client_configuration(client: MercutoClient) -> None:
    """Test retrieving WireGuard client configuration."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Get configuration by network endpoint code
    config = client.endpoint().get_wireguard_client_configuration(
        network_endpoint_code=endpoint.code
    )
    assert isinstance(config, WireguardClientConfigurationSchema)
    assert config.interface.code == interface.code
    assert config.client.code == wg_client.code
    assert config.network_endpoint.code == endpoint.code
    assert config.config_version_ts > 0


def test_get_wireguard_client_configuration_by_client_code(
    client: MercutoClient,
) -> None:
    """Test retrieving WireGuard client configuration by client code."""
    # Setup
    client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Get configuration by client code
    config = client.endpoint().get_wireguard_client_configuration(
        wireguard_client_code=wg_client.code
    )
    assert config.client.code == wg_client.code


# --- WireGuard Server Information Tests ---


def test_get_wireguard_server_config_version_with_interface(
    client: MercutoClient,
) -> None:
    """Test getting WireGuard server config version when interface exists."""
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )

    version = client.endpoint().get_wireguard_server_config_version(
        server_host_code=interface.server_host.code
    )
    assert version is not None
    assert isinstance(version, float)
    assert version > 0


def test_get_wireguard_server_config_version_without_interface(
    client: MercutoClient,
) -> None:
    """Test getting WireGuard server config version when no interface exists."""
    version = client.endpoint().get_wireguard_server_config_version(
        server_host_code="non-existent-host"
    )
    assert version is None


def test_get_wireguard_server_version_with_interface(client: MercutoClient) -> None:
    """Test getting WireGuard server version when interface exists."""
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )

    # Test with interface_code
    version = client.endpoint().get_wireguard_server_version(
        interface_code=interface.code
    )
    assert version is not None
    assert isinstance(version, float)
    assert version == 1.0

    # Test with server_host_code
    version = client.endpoint().get_wireguard_server_version(
        server_host_code=interface.server_host.code
    )
    assert version is not None
    assert isinstance(version, float)
    assert version == 1.0


def test_get_wireguard_server_version_without_interface(client: MercutoClient) -> None:
    """Test getting WireGuard server version when no interface exists."""
    version = client.endpoint().get_wireguard_server_version(
        server_host_code="non-existent-host"
    )
    assert version is None


def test_get_wireguard_server_stats(client: MercutoClient) -> None:
    """Test getting WireGuard server statistics."""
    # Setup: Create interface and client
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
        allowed_ips="10.0.0.0/24",
    )
    assert wg_client.allowed_ips == "10.0.0.0/24"

    # Get stats
    stats = client.endpoint().get_wireguard_server_stats()
    assert stats is not None
    assert isinstance(stats, list)
    assert len(stats) > 0
    assert isinstance(stats[0], WireguardServerStatsSchema)
    assert stats[0].timestamp is not None
    assert "wg0" in stats[0].value
    assert stats[0].value["wg0"].public_key == interface.public_key


def test_get_wireguard_server_stats_without_interface(client: MercutoClient) -> None:
    """Test getting WireGuard server stats when no interface exists."""
    stats = client.endpoint().get_wireguard_server_stats()
    assert stats is None


def test_wireguard_interface_deletion_cascades_clients(client: MercutoClient) -> None:
    """Test that deleting a WireGuard interface also deletes associated clients."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )
    endpoint = client.endpoint().create_network_endpoint(
        network_endpoint_type_code=endpoint_type.code,
        serial_number="SN001",
        project_code="proj1",
    )
    keys = client.endpoint().generate_wireguard_keys()
    wg_client = client.endpoint().register_wireguard_client(
        network_endpoint_code=endpoint.code,
        public_key=keys.public_key,
    )

    # Delete interface
    client.endpoint().delete_wireguard_interface(interface_code=interface.code)

    # Verify client is also deleted
    try:
        client.endpoint().get_wireguard_client(wireguard_client_code=wg_client.code)
        assert False, "Should have raised exception"
    except Exception:
        pass  # Expected


def test_multiple_clients_on_same_interface(client: MercutoClient) -> None:
    """Test registering multiple clients on the same interface."""
    # Setup
    interface = client.endpoint().create_wireguard_interface(
        interface_name="wg0",
        tenant_code="tenant1",
    )
    assert interface.interface_name == "wg0"

    endpoint_type = client.endpoint().create_network_endpoint_type(
        "Model", "Manufacturer"
    )

    # Create multiple endpoints and clients
    clients = []
    for i in range(3):
        endpoint = client.endpoint().create_network_endpoint(
            network_endpoint_type_code=endpoint_type.code,
            serial_number=f"SN{i:03d}",
            project_code="proj1",
        )
        keys = client.endpoint().generate_wireguard_keys()
        wg_client = client.endpoint().register_wireguard_client(
            network_endpoint_code=endpoint.code,
            public_key=keys.public_key,
        )
        clients.append(wg_client)

    # Verify each client has unique ID and IP
    client_ids = [c.client_id for c in clients]
    assert len(set(client_ids)) == 3  # All unique

    ip_addresses = [c.ip_address for c in clients]
    assert len(set(ip_addresses)) == 3  # All unique

    # Verify all clients are on the same interface
    for c in clients:
        assert c.interface_code == interface.code
