import pytest

from ... import MercutoClient
from ...exceptions import MercutoHTTPException
from ...modules.assets import DeviceChannel, MetadataEntry


def test_healthcheck_and_ping(client: MercutoClient) -> None:
    project = client.assets().create_project(tenant='tenant-a', name='Bridge A')
    health = client.assets().healthcheck()
    client.assets().ping_project(project=project.code, ip_address='1.2.3.4')

    assert health.status == 'ok'

    with pytest.raises(MercutoHTTPException, match='valid IP'):
        client.assets().ping_project(project=project.code, ip_address='not-an-ip')


def test_project_crud(client: MercutoClient) -> None:
    project = client.assets().create_project(
        tenant='tenant-a',
        name='Bridge A',
        description='Test project',
        timezone='UTC',
    )

    fetched = client.assets().get_project(project.code)
    assert fetched.code == project.code
    assert fetched.name == 'Bridge A'

    updated = client.assets().update_project(
        code=project.code,
        name='Bridge A - Updated',
        description=None,
        timezone='Australia/Brisbane',
        is_active=False,
    )
    assert updated.name == 'Bridge A - Updated'
    assert updated.description is None
    assert updated.is_active is False

    listed = client.assets().list_projects()
    assert [p.code for p in listed] == [project.code]

    client.assets().delete_project(project.code)
    assert client.assets().list_projects() == []


def test_device_crud(client: MercutoClient) -> None:
    project = client.assets().create_project(tenant='tenant-a', name='Bridge A')

    parent = client.assets().create_device(
        project=project.code,
        label='Gateway',
        device_type='gateway',
    )
    child = client.assets().create_device(
        project=project.code,
        label='Strain Sensor',
        device_type='sensor',
        parent=parent.code,
        metadata={
            'serial': MetadataEntry(data_type='string', value='SN-001'),
        },
        channels=[DeviceChannel(field='strain', channel='CH-1')],
    )

    fetched_child = client.assets().get_device(child.code)
    assert fetched_child.parent == parent.code
    assert fetched_child.metadata['serial'].value == 'SN-001'
    assert len(fetched_child.channels) == 1
    assert fetched_child.channels[0].field == 'strain'

    parent_after_child = client.assets().get_device(parent.code)
    assert parent_after_child.children == [child.code]

    updated_child = client.assets().update_device(
        code=child.code,
        label='Strain Sensor v2',
        parent=parent.code,
        metadata={
            'tags': MetadataEntry(data_type='string', is_list=True, values=['A', 'B']),
        },
        channels=[DeviceChannel(field='temperature', channel='CH-2')],
    )
    assert updated_child.label == 'Strain Sensor v2'
    assert updated_child.metadata['tags'].is_list is True
    assert updated_child.channels[0].field == 'temperature'

    listed = client.assets().list_devices(project=project.code)
    assert [device.code for device in listed] == [parent.code, child.code]

    with pytest.raises(MercutoHTTPException, match='child devices'):
        client.assets().delete_device(parent.code)

    client.assets().delete_device(child.code)
    parent_after_delete = client.assets().get_device(parent.code)
    assert parent_after_delete.children == []

    client.assets().delete_device(parent.code)
    assert client.assets().list_devices(project=project.code) == []


def test_cannot_delete_project_with_devices(client: MercutoClient) -> None:
    project = client.assets().create_project(tenant='tenant-a', name='Bridge A')
    client.assets().create_device(project=project.code, label='Gateway', device_type='gateway')

    with pytest.raises(MercutoHTTPException, match='still has devices'):
        client.assets().delete_project(project.code)
