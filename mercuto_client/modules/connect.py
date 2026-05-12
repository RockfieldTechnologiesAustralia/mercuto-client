from datetime import datetime
from typing import TYPE_CHECKING, Optional

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from ..client import MercutoClient

from ..exceptions import MercutoHTTPException
from . import PayloadType
from ._util import BaseModel

# ── WireGuard Peers ──────────────────────────────────────


class WireguardPeer(BaseModel):
    id: str
    name: str
    peer_type: str
    isolation_group: Optional[str] = None
    project: Optional[str] = None
    user_code: Optional[str] = None
    public_key: str
    assigned_ip: str
    description: Optional[str] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# ── SSH Tunnels ──────────────────────────────────────────


class SshTunnel(BaseModel):
    id: str
    name: str
    project: str
    assigned_port: int
    device_public_key: str
    description: Optional[str] = None
    status: str
    last_heartbeat: Optional[datetime] = None
    is_enabled: bool
    created_at: datetime
    updated_at: datetime


# ── Server Info ──────────────────────────────────────────


class WireguardServerInfo(BaseModel):
    server_public_key: str
    server_endpoint: str
    server_port: str
    updated_at: datetime


class SshServerInfo(BaseModel):
    server_endpoint: str
    server_port: str
    host_key_fingerprint: Optional[str] = None
    updated_at: datetime


# ── WireGuard Peer Stats ────────────────────────────────


class WireguardPeerSummary(BaseModel):
    peer_id: str
    peer_name: str
    is_online: bool
    last_handshake: Optional[datetime] = None
    last_endpoint: Optional[str] = None
    last_stats_update: Optional[datetime] = None
    total_rx_bytes: int
    total_tx_bytes: int


class WireguardSnapshot(BaseModel):
    id: str
    peer_id: str
    rx_bytes: int
    tx_bytes: int
    latest_handshake: Optional[datetime] = None
    remote_endpoint: Optional[str] = None
    captured_at: datetime


class WireguardEvent(BaseModel):
    id: str
    peer_id: str
    event_type: str
    remote_endpoint: Optional[str] = None
    timestamp: datetime


# --- TypeAdapters for lists ---
_WireguardPeerListAdapter = TypeAdapter(list[WireguardPeer])
_SshTunnelListAdapter = TypeAdapter(list[SshTunnel])
_WireguardPeerSummaryListAdapter = TypeAdapter(list[WireguardPeerSummary])
_WireguardSnapshotListAdapter = TypeAdapter(list[WireguardSnapshot])
_WireguardEventListAdapter = TypeAdapter(list[WireguardEvent])


class MercutoConnectService:
    def __init__(self, client: 'MercutoClient', path: str = '/connect') -> None:
        self._client = client
        self._path = path

    # ── WireGuard Peers ──────────────────────────────────

    def list_wireguard_peers(self,
                             isolation_group: Optional[str] = None,
                             project: Optional[str] = None,
                             peer_type: Optional[str] = None) -> list[WireguardPeer]:
        params: PayloadType = {}
        if isolation_group is not None:
            params['isolation_group'] = isolation_group
        if project is not None:
            params['project'] = project
        if peer_type is not None:
            params['peer_type'] = peer_type
        r = self._client.request(f"{self._path}/wireguard/peers/", "GET",
                                 params=params if params else None)
        return _WireguardPeerListAdapter.validate_json(r.text)

    def get_wireguard_peer(self, peer_id: str) -> WireguardPeer:
        r = self._client.request(f"{self._path}/wireguard/peers/{peer_id}", "GET")
        return WireguardPeer.model_validate_json(r.text)

    def create_wireguard_peer(self, name: str, peer_type: str,
                              isolation_group: Optional[str] = None,
                              project: Optional[str] = None,
                              user_code: Optional[str] = None,
                              description: Optional[str] = None) -> WireguardPeer:
        body: PayloadType = {
            'name': name,
            'peer_type': peer_type,
        }
        if isolation_group is not None:
            body['isolation_group'] = isolation_group
        if project is not None:
            body['project'] = project
        if user_code is not None:
            body['user_code'] = user_code
        if description is not None:
            body['description'] = description
        r = self._client.request(f"{self._path}/wireguard/peers/", "POST", json=body)
        return WireguardPeer.model_validate_json(r.text)

    def update_wireguard_peer(self, peer_id: str, name: str, is_enabled: bool,
                              description: Optional[str] = None,
                              isolation_group: Optional[str] = None,
                              project: Optional[str] = None) -> WireguardPeer:
        body: PayloadType = {
            'name': name,
            'is_enabled': is_enabled,
        }
        if description is not None:
            body['description'] = description
        if isolation_group is not None:
            body['isolation_group'] = isolation_group
        if project is not None:
            body['project'] = project
        r = self._client.request(f"{self._path}/wireguard/peers/{peer_id}", "PUT", json=body)
        return WireguardPeer.model_validate_json(r.text)

    def get_wireguard_peer_key(self, peer_id: str) -> str:
        r = self._client.request(f"{self._path}/wireguard/peers/{peer_id}/key", "GET")
        return r.json()['private_key']

    def delete_wireguard_peer(self, peer_id: str) -> None:
        self._client.request(f"{self._path}/wireguard/peers/{peer_id}", "DELETE")

    # ── SSH Tunnels ──────────────────────────────────────

    def list_ssh_tunnels(self, project: Optional[str] = None) -> list[SshTunnel]:
        params: PayloadType = {}
        if project is not None:
            params['project'] = project
        r = self._client.request(f"{self._path}/ssh/tunnels/", "GET",
                                 params=params if params else None)
        return _SshTunnelListAdapter.validate_json(r.text)

    def get_ssh_tunnel(self, tunnel_id: str) -> SshTunnel:
        r = self._client.request(f"{self._path}/ssh/tunnels/{tunnel_id}", "GET")
        return SshTunnel.model_validate_json(r.text)

    def create_ssh_tunnel(self, name: str, project: str,
                          description: Optional[str] = None) -> SshTunnel:
        body: PayloadType = {'name': name, 'project': project}
        if description is not None:
            body['description'] = description
        r = self._client.request(f"{self._path}/ssh/tunnels/", "POST", json=body)
        return SshTunnel.model_validate_json(r.text)

    def update_ssh_tunnel(self, tunnel_id: str, name: str, project: str,
                          is_enabled: bool,
                          description: Optional[str] = None) -> SshTunnel:
        body: PayloadType = {
            'name': name,
            'project': project,
            'is_enabled': is_enabled,
        }
        if description is not None:
            body['description'] = description
        r = self._client.request(f"{self._path}/ssh/tunnels/{tunnel_id}", "PUT", json=body)
        return SshTunnel.model_validate_json(r.text)

    def get_ssh_tunnel_key(self, tunnel_id: str) -> str:
        r = self._client.request(f"{self._path}/ssh/tunnels/{tunnel_id}/key", "GET")
        return r.json()['device_private_key']

    def delete_ssh_tunnel(self, tunnel_id: str) -> None:
        self._client.request(f"{self._path}/ssh/tunnels/{tunnel_id}", "DELETE")

    # ── Server Info ──────────────────────────────────────

    def get_wireguard_server_info(self) -> Optional[WireguardServerInfo]:
        r = self._client.request(f"{self._path}/wireguard/server-info", "GET", raise_for_status=False)
        if r.status_code == 503:
            return None
        if not r.ok:
            raise MercutoHTTPException(r.text, r.status_code)
        return WireguardServerInfo.model_validate_json(r.text)

    def get_ssh_server_info(self) -> Optional[SshServerInfo]:
        r = self._client.request(f"{self._path}/ssh/server-info", "GET", raise_for_status=False)
        if r.status_code == 503:
            return None
        if not r.ok:
            raise MercutoHTTPException(r.text, r.status_code)
        return SshServerInfo.model_validate_json(r.text)

    # ── WireGuard Peer Stats ────────────────────────────

    def get_wireguard_peer_summary(self, peer_id: str) -> WireguardPeerSummary:
        r = self._client.request(f"{self._path}/wireguard/peer-stats/summary/{peer_id}", "GET")
        return WireguardPeerSummary.model_validate_json(r.text)

    def list_wireguard_peer_summaries(self,
                                      isolation_group: Optional[str] = None,
                                      project: Optional[str] = None) -> list[WireguardPeerSummary]:
        params: PayloadType = {}
        if isolation_group is not None:
            params['isolation_group'] = isolation_group
        if project is not None:
            params['project'] = project
        r = self._client.request(f"{self._path}/wireguard/peer-stats/summary/", "GET",
                                 params=params if params else None)
        return _WireguardPeerSummaryListAdapter.validate_json(r.text)

    def get_wireguard_snapshots(self, peer_id: str,
                                since: Optional[datetime] = None,
                                limit: int = 100) -> list[WireguardSnapshot]:
        params: PayloadType = {'limit': limit}
        if since is not None:
            params['since'] = since.isoformat()
        r = self._client.request(f"{self._path}/wireguard/peer-stats/snapshots/{peer_id}", "GET",
                                 params=params)
        return _WireguardSnapshotListAdapter.validate_json(r.text)

    def get_wireguard_events(self, peer_id: str,
                             since: Optional[datetime] = None,
                             limit: int = 100) -> list[WireguardEvent]:
        params: PayloadType = {'limit': limit}
        if since is not None:
            params['since'] = since.isoformat()
        r = self._client.request(f"{self._path}/wireguard/peer-stats/events/{peer_id}", "GET",
                                 params=params)
        return _WireguardEventListAdapter.validate_json(r.text)
