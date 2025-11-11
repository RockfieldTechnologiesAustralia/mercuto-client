from ... import MercutoClient


def test_add_and_list_users(client: MercutoClient) -> None:
    client.identity().create_user("test_user", "test-tenant", "Description", "Test Group")
    users = client.identity().list_users()
    assert len(users) == 1
    assert "test_user" in [user.username for user in users]
