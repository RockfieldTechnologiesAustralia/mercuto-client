import contextlib
from typing import Callable, Iterator, Optional

from mercuto_client.modules.identity import VerifyMyPermissions

from ..client import MercutoClient


@contextlib.contextmanager
def mock_mercuto(data: bool = True,
                 identity: bool = True,
                 fatigue: bool = True,
                 core: bool = True,
                 media: bool = True,
                 notifications: bool = True,
                 verify_service_token: Optional[Callable[[str], VerifyMyPermissions]] = None) -> Iterator[None]:
    """
    While this context is active, all calls to MercutoClient will use mocked services.

    :param data: Whether to mock the data module.
    :param identity: Whether to mock the identity module.
    :param fatigue: Whether to mock the fatigue module.
    :param verify_service_token: Optional function to mock the verify_service_token behavior. Only used for the mock identity service.
    """
    with contextlib.ExitStack() as stack:
        if data:
            stack.enter_context(mock_data_module())
        if identity:
            stack.enter_context(mock_identity_module(
                verify_service_token=verify_service_token))
        if fatigue:
            stack.enter_context(mock_fatigue_module())
        if core:
            stack.enter_context(mock_core_module())
        if media:
            stack.enter_context(mock_media_module())
        if notifications:
            stack.enter_context(mock_notifications_module())
        yield


@contextlib.contextmanager
def mock_core_module() -> Iterator[None]:
    from .mock_core import MockMercutoCoreService
    original = MercutoClient.core

    _cache: Optional[MockMercutoCoreService] = None

    def stub(self: MercutoClient) -> MockMercutoCoreService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoCoreService(self)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'core', stub)
        yield
    finally:
        setattr(MercutoClient, 'core', original)


@contextlib.contextmanager
def mock_data_module() -> Iterator[None]:
    from .mock_data import MockMercutoDataService
    original = MercutoClient.data

    _cache: Optional[MockMercutoDataService] = None

    def stub(self: MercutoClient) -> MockMercutoDataService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoDataService(self)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'data', stub)
        yield
    finally:
        setattr(MercutoClient, 'data', original)


@contextlib.contextmanager
def mock_identity_module(verify_service_token: Optional[Callable[[str], VerifyMyPermissions]] = None) -> Iterator[None]:
    from .mock_identity import MockMercutoIdentityService
    original = MercutoClient.identity

    _cache: Optional[MockMercutoIdentityService] = None

    def stub(self: MercutoClient) -> MockMercutoIdentityService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoIdentityService(
                self, verify_service_token=verify_service_token)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'identity', stub)
        yield
    finally:
        setattr(MercutoClient, 'identity', original)


@contextlib.contextmanager
def mock_fatigue_module() -> Iterator[None]:
    from .mock_fatigue import MockMercutoFatigueService
    original = MercutoClient.fatigue

    _cache: Optional[MockMercutoFatigueService] = None

    def stub(self: MercutoClient) -> MockMercutoFatigueService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoFatigueService(self)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'fatigue', stub)
        yield
    finally:
        setattr(MercutoClient, 'fatigue', original)


@contextlib.contextmanager
def mock_media_module() -> Iterator[None]:
    from .mock_media import MockMercutoMediaService
    original = MercutoClient.media

    _cache: Optional[MockMercutoMediaService] = None

    def stub(self: MercutoClient) -> MockMercutoMediaService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoMediaService(self)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'media', stub)
        yield
    finally:
        setattr(MercutoClient, 'media', original)


@contextlib.contextmanager
def mock_notifications_module() -> Iterator[None]:
    from .mock_notifications import MockMercutoNotificationService
    original = MercutoClient.notifications

    _cache: Optional[MockMercutoNotificationService] = None

    def stub(self: MercutoClient) -> MockMercutoNotificationService:
        nonlocal _cache
        if _cache is None:
            _cache = MockMercutoNotificationService(self)
        _cache._client = self
        return _cache

    try:
        setattr(MercutoClient, 'notifications', stub)
        yield
    finally:
        setattr(MercutoClient, 'notifications', original)
