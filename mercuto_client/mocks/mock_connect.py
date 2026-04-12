import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from ..client import MercutoClient
from ..exceptions import MercutoHTTPException
from ..modules.connect import (MercutoConnectService, SshServerInfo, SshTunnel,
                               WireguardEvent, WireguardPeer,
                               WireguardPeerSummary, WireguardServerInfo,
                               WireguardSnapshot)
from ._utility import EnforceOverridesMeta

logger = logging.getLogger(__name__)

_MOCK_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class MockMercutoConnectService(MercutoConnectService, metaclass=EnforceOverridesMeta):
    def __init__(self, client: 'MercutoClient'):
        super().__init__(client=client, path='/mock-connect-service-method-not-implemented')
        self._wireguard_peers: dict[str, WireguardPeer] = {}
        self._wireguard_peer_keys: dict[str, str] = {}
        self._ssh_tunnels: dict[str, SshTunnel] = {}
        self._ssh_tunnel_keys: dict[str, str] = {}
        self._wireguard_server_info: Optional[WireguardServerInfo] = None
        self._ssh_server_info: Optional[SshServerInfo] = None
        self._wireguard_summaries: dict[str, WireguardPeerSummary] = {}
        self._wireguard_snapshots: dict[str, list[WireguardSnapshot]] = {}
        self._wireguard_events: dict[str, list[WireguardEvent]] = {}

    # ── WireGuard Peers ──────────────────────────────────

    def list_wireguard_peers(self,
                             isolation_group: Optional[str] = None,
                             project: Optional[str] = None,
                             peer_type: Optional[str] = None) -> list[WireguardPeer]:
        peers = list(self._wireguard_peers.values())
        if isolation_group is not None:
            peers = [p for p in peers if p.isolation_group == isolation_group]
        if project is not None:
            peers = [p for p in peers if p.project == project]
        if peer_type is not None:
            peers = [p for p in peers if p.peer_type == peer_type]
        return peers

    def get_wireguard_peer(self, peer_id: str) -> WireguardPeer:
        if peer_id not in self._wireguard_peers:
            raise MercutoHTTPException(f"WireGuard peer not found: {peer_id}", 404)
        return self._wireguard_peers[peer_id]

    def create_wireguard_peer(self, name: str, peer_type: str,
                              isolation_group: Optional[str] = None,
                              project: Optional[str] = None,
                              user_code: Optional[str] = None,
                              description: Optional[str] = None) -> WireguardPeer:
        peer_id = str(uuid.uuid4())
        peer = WireguardPeer(
            id=peer_id, name=name, peer_type=peer_type,
            isolation_group=isolation_group, project=project,
            user_code=user_code, public_key=f"mock-pubkey-{peer_id}",
            assigned_ip=f"10.0.0.{len(self._wireguard_peers) + 2}",
            description=description, is_enabled=True,
            created_at=_MOCK_NOW, updated_at=_MOCK_NOW,
        )
        self._wireguard_peers[peer_id] = peer
        self._wireguard_peer_keys[peer_id] = f"mock-privkey-{peer_id}"
        return peer

    def update_wireguard_peer(self, peer_id: str, name: str, is_enabled: bool,
                              description: Optional[str] = None,
                              isolation_group: Optional[str] = None,
                              project: Optional[str] = None) -> WireguardPeer:
        if peer_id not in self._wireguard_peers:
            raise MercutoHTTPException(f"WireGuard peer not found: {peer_id}", 404)
        peer = self._wireguard_peers[peer_id]
        updated = peer.model_copy(update={
            'name': name,
            'is_enabled': is_enabled,
            'description': description,
            'isolation_group': isolation_group,
            'project': project,
            'updated_at': datetime.now(timezone.utc),
        })
        self._wireguard_peers[peer_id] = updated
        return updated

    def get_wireguard_peer_key(self, peer_id: str) -> str:
        if peer_id not in self._wireguard_peer_keys:
            raise MercutoHTTPException(f"WireGuard peer not found: {peer_id}", 404)
        return self._wireguard_peer_keys[peer_id]

    def delete_wireguard_peer(self, peer_id: str) -> None:
        if peer_id not in self._wireguard_peers:
            raise MercutoHTTPException(f"WireGuard peer not found: {peer_id}", 404)
        del self._wireguard_peers[peer_id]
        self._wireguard_peer_keys.pop(peer_id, None)

    # ── SSH Tunnels ──────────────────────────────────────

    def list_ssh_tunnels(self, project: Optional[str] = None) -> list[SshTunnel]:
        tunnels = list(self._ssh_tunnels.values())
        if project is not None:
            tunnels = [t for t in tunnels if t.project == project]
        return tunnels

    def get_ssh_tunnel(self, tunnel_id: str) -> SshTunnel:
        if tunnel_id not in self._ssh_tunnels:
            raise MercutoHTTPException(f"SSH tunnel not found: {tunnel_id}", 404)
        return self._ssh_tunnels[tunnel_id]

    def create_ssh_tunnel(self, name: str, project: str,
                          description: Optional[str] = None) -> SshTunnel:
        tunnel_id = str(uuid.uuid4())
        tunnel = SshTunnel(
            id=tunnel_id, name=name, project=project,
            assigned_port=22000 + len(self._ssh_tunnels),
            device_public_key=f"mock-device-pubkey-{tunnel_id}",
            description=description, status="active",
            last_heartbeat=None, is_enabled=True,
            created_at=_MOCK_NOW, updated_at=_MOCK_NOW,
        )
        self._ssh_tunnels[tunnel_id] = tunnel
        self._ssh_tunnel_keys[tunnel_id] = f"mock-device-privkey-{tunnel_id}"
        return tunnel

    def update_ssh_tunnel(self, tunnel_id: str, name: str, project: str,
                          is_enabled: bool,
                          description: Optional[str] = None) -> SshTunnel:
        if tunnel_id not in self._ssh_tunnels:
            raise MercutoHTTPException(f"SSH tunnel not found: {tunnel_id}", 404)
        tunnel = self._ssh_tunnels[tunnel_id]
        updated = tunnel.model_copy(update={
            'name': name,
            'project': project,
            'is_enabled': is_enabled,
            'description': description,
            'updated_at': datetime.now(timezone.utc),
        })
        self._ssh_tunnels[tunnel_id] = updated
        return updated

    def get_ssh_tunnel_key(self, tunnel_id: str) -> str:
        if tunnel_id not in self._ssh_tunnel_keys:
            raise MercutoHTTPException(f"SSH tunnel not found: {tunnel_id}", 404)
        return self._ssh_tunnel_keys[tunnel_id]

    def delete_ssh_tunnel(self, tunnel_id: str) -> None:
        if tunnel_id not in self._ssh_tunnels:
            raise MercutoHTTPException(f"SSH tunnel not found: {tunnel_id}", 404)
        del self._ssh_tunnels[tunnel_id]
        self._ssh_tunnel_keys.pop(tunnel_id, None)

    # ── Server Info ──────────────────────────────────────

    def get_wireguard_server_info(self) -> Optional[WireguardServerInfo]:
        return self._wireguard_server_info

    def get_ssh_server_info(self) -> Optional[SshServerInfo]:
        return self._ssh_server_info

    # ── WireGuard Peer Stats ────────────────────────────

    def get_wireguard_peer_summary(self, peer_id: str) -> WireguardPeerSummary:
        if peer_id not in self._wireguard_summaries:
            raise MercutoHTTPException(f"WireGuard peer summary not found: {peer_id}", 404)
        return self._wireguard_summaries[peer_id]

    def list_wireguard_peer_summaries(self,
                                      isolation_group: Optional[str] = None,
                                      project: Optional[str] = None) -> list[WireguardPeerSummary]:
        summaries = list(self._wireguard_summaries.values())
        if isolation_group is not None:
            summaries = [s for s in summaries
                         if self._wireguard_peers.get(s.peer_id) and
                         self._wireguard_peers[s.peer_id].isolation_group == isolation_group]
        if project is not None:
            summaries = [s for s in summaries
                         if self._wireguard_peers.get(s.peer_id) and
                         self._wireguard_peers[s.peer_id].project == project]
        return summaries

    def get_wireguard_snapshots(self, peer_id: str,
                                since: Optional[datetime] = None,
                                limit: int = 100) -> list[WireguardSnapshot]:
        snapshots = self._wireguard_snapshots.get(peer_id, [])
        if since is not None:
            snapshots = [s for s in snapshots if s.captured_at >= since]
        return snapshots[:limit]

    def get_wireguard_events(self, peer_id: str,
                             since: Optional[datetime] = None,
                             limit: int = 100) -> list[WireguardEvent]:
        events = self._wireguard_events.get(peer_id, [])
        if since is not None:
            events = [e for e in events if e.timestamp >= since]
        return events[:limit]
