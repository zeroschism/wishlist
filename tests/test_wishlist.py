import wishlist.wishlist as wishlist

def test_wishlist():
    import uuid, secrets

    id = str(uuid.uuid4())
    name = "test wishlist"
    username = "Wisher"
    email = "tester@test.test"
    token =  secrets.token_urlsafe(32)
    verified = False

    test_wishlist = wishlist.Wishlist(
        id,
        name,
        username,
        email,
        verified,
        token,
        token
    )

    assert id == test_wishlist.id
    assert name == test_wishlist.name
    assert username == test_wishlist.username
    assert token == test_wishlist.owner_token
    assert token == test_wishlist.share_token
    assert verified == test_wishlist.email_verified


def test_wishlist_item():
    import uuid

    id = str(uuid.uuid4())
    name = "test"
    url = "http://test.test"
    description = "test"
    gotten = False
    getter = "def"

    test_item = wishlist.WishlistItem(
        id, name, url, description, gotten, getter
    )

    assert id == test_item.id
    assert name == test_item.name
    assert url == test_item.url
    assert description == test_item.description
    assert gotten == test_item.gotten
    assert getter == test_item.getter