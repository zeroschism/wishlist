"""
    wishlist flask application for storing and sharing wishlists
    Copyright (C) 2024 Adam Schumacher

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as
    published by the Free Software Foundation, either version 3 of the
    License, or (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.

    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
"""

import datetime
import json
import secrets
import wishlist.validator as validator
import sqlite3
import uuid

from email.headerregistry import Address

DB_NAME = "wishlist.sqlite3"


class InvalidToken(Exception):
    """ Raised when a passed token doesn't exist """
    pass


class InvalidShareToken(InvalidToken):
    """ Raised when a passed token is valid for sharing """
    pass


class InvalidManageToken(InvalidToken):
    """ Raised when a passed manage token doesn't exist """
    pass

class UnverifiedWishlist(Exception):
    """ Raised when trying to access or update a wishlist that hasn't been verified yet """
    pass

class WishlistNotFoundError(Exception):
    """ Raised when a requested wishlist id does not exist """
    pass


class RateLimitError(Exception):
    """ Raised when some rate limit is reached """
    pass

 
class InvalidParameter(ValueError):
    """ Raised when some input doesn't validate """
    pass


class InvalidEmailError(InvalidParameter):
    """ A more specific version of InvalidParamter for when an email address doesn't validate """
    pass

class MissingRequiredParameterError(Exception):
    """ Raised when a required element is empty """
    pass


class WishlistJSONEncoder(json.JSONEncoder):
    """ A JSON Encoder specifically for wishlist objects """

    def default(self, o):
        """ default encoder for wishlist objects.  Returns the default JSONEncoder for any other kind of object. """
        if isinstance(o, WishlistItem):
            return {
                "id": o.id,
                "name": o.name,
                "url": o.url,
                "description": o.description,
                "gotten": o.gotten,
                "getter": o.getter,
            }
        elif isinstance(o, Wishlist):
            return {"name": o.name, "items": [item for item in o.items.values()]}
        else:
            return super().default(o)


class WishlistItem:
    """ Represents an individual item in a wishlist """

    def __init__(
        self,
        id: str = None,
        name: str = None,
        url: str = None,
        description: str = None,
        gotten: bool = False,
        getter: str = None,
    ):
        if not id:
            self._id = uuid.uuid4()
        else:
            self._id = uuid.UUID(id)
        
        if name is not None:
            self.name = validator.normalize_words(name)
        else:
            raise MissingRequiredParameterError("Must supply an item name")
        
        if url is not None and len(url) > 0:
            try:
                self.url = validator.normalize_url(url)
            except ValueError as v:
                raise InvalidParameter(f"{v}")
        else:
            self.url = ""
    
        self.description = validator.normalize_words(description)
        self.gotten = gotten
        self.getter = getter

    def __str__(self) -> str:
        return json.dumps(self, cls=WishlistJSONEncoder, ensure_ascii=False)

    @property
    def id(self) -> str:
        return str(self._id)


class Wishlist:
    """ Represents a wishlist containing items"""
    def __init__(
        self,
        id: str = None,
        name: str = "My Wishlist",
        username: str = None,
        email: str = None,
        email_verified: bool = False,
        owner_token: str = None,
        share_token: str = None
    ):
        self.items = {}
        self.name = validator.normalize_words(name)
        self.username = validator.normalize_words(username)
        self.email_verified = email_verified

        if email is not None:
            if validator.is_email(email):
                self.email = email
            else:
                raise InvalidEmailError("Email address is not valid")
        else:
            raise MissingRequiredParameterError("Email address must be specified")

        if not id:
            self._id = uuid.uuid4()
        else:
            self._id = uuid.UUID(id)

        if not owner_token:
            self._owner_token = secrets.token_urlsafe(32)
        else:
            self._owner_token = owner_token

        if not share_token:
            self._share_token = secrets.token_urlsafe(32)
        else:
            self._share_token = share_token

    @property
    def id(self) -> str:
        return str(self._id)

    @property
    def owner_token(self) -> str:
        return self._owner_token

    @property
    def share_token(self) -> str:
        return self._share_token

    @property
    def get_addr(self) -> str:
        if str(self.email) == "<>":
            return ""

        return str(self.email)


class WishlistDB:
    """ Abstraction layer for persisting a wishlist to a database """

    def __init__(self, db_loc: str = DB_NAME):
        self._db_loc = db_loc
        self.connect()

    @staticmethod
    def create_db(db_loc: str = DB_NAME) -> None:
        """ Generates the database schema in an empty SQLite3 database 

            Keyword arguments:
            db_loc -- Path to a sqlite3 db file. Default: wishlist.DB_NAME
        """
        wishlist = "CREATE TABLE wishlist(id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL, email TEXT NOT NULL, email_verified INTEGER DEFAULT 0, owner_token TEXT NOT NULL, share_token TEXT NOT NULL, added TEXT DEFAULT CURRENT_TIMESTAMP)"
        #CREATE TABLE wishlist(id TEXT PRIMARY KEY, name TEXT NOT NULL, username TEXT NOT NULL, email TEXT NOT NULL, owner_token TEXT NOT NULL, share_token TEXT NOT NULL, added TEXT DEFAULT CURRENT_TIMESTAMP)"
        wishlist_item = "CREATE TABLE wishlist_item(id TEXT PRIMARY KEY, wishlist_id TEXT, name TEXT NOT NULL, url TEXT, description TEXT, gotten INTEGER, getter TEXT, added TEXT DEFAULT CURRENT_TIMESTAMP,FOREIGN KEY(wishlist_id) REFERENCES wishlist(id) ON DELETE CASCADE, FOREIGN KEY(getter) REFERENCES wishlist_session(session_id))"
        wishlist_session = "CREATE TABLE wishlist_session(id TEXT PRIMARY KEY,ip_address TEXT, started TEXT DEFAULT CURRENT_TIMESTAMP)"
        wishlist_email_log = "CREATE TABLE email_record(email TEXT NOT NULL, sender_session_id TEXT NOT NULL, sent_time TEXT DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY(sender_session_id) REFERENCES wishlist_session(id))"

        conn = sqlite3.connect(db_loc, autocommit=False)
        cur = sqlite3.cursor()
        cur.execute("PRAGMA foreign_keys = ON")
        cur.execute(wishlist)
        cur.execute(wishlist_item)
        cur.execute(wishlist_session)
        cur.execute(wishlist_email_log)
        cur.close()
        conn.close()

    @staticmethod
    def wishlist_factory(cur, row):
        """ Factory method for creating a wishlist object from a DB result

            Arguments:
            cur -- sqlite3.cursor() of the query
            row -- result row from the query as an array
        """
        # id, name, username , email, email_verified, owner_token, share_token, added
        return Wishlist(row[0], row[1], row[2], row[3], row[4], row[5], row[6])

    @staticmethod
    def wishitem_factory(cur, row):
        """ Factory method for creating a WishlistItem object from a DB result

            Arguments:
            cur -- sqlite3.cursor() from the query
            row -- result row from the query as an array
        """
        return WishlistItem(row[0], row[1], row[2], row[3], row[4], row[5])

    def _cursor_factory(self, row_factory=None):
        """ Factory method for creating db cursor objects with the needed row_factory

            Arguments:
            row_factory -- factory method to use when retrieving a row from the query for this cursor.  Default: None
        """
        cur = self._conn.cursor()
        cur.arraysize = 25
        if row_factory:
            cur.row_factory = row_factory

        return cur

    def connect(self) -> None:
        """ Connects to database and configure settings for connection """
        self._conn = sqlite3.connect(
            self._db_loc, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        )
        self._do_pragmas()

    def _do_pragmas(self) -> None:
        """ Apply specific sqlite3 settings to the connection """
        connect_cur = self._conn.cursor()
        pragmas = """PRAGMA foreign_keys = ON;
                     PRAGMA journal_mode = WAL;
                     PRAGMA temp_store = memory;"""
        connect_cur.executescript(pragmas)

    def save(self) -> None:
        """ Save (commits) changes to the database """
        self._conn.commit()

    def get_wishlist(self, wishlist_id: str) -> Wishlist:
        """ Returns a wishlist object matching the given wishlist_id or raises a WishlistNotFoundError

            Arguments:
            wishlist_id -- uuid representing a wishlist

            Returns:
            Wishlist object
    
            Throws:
            WihslistNotFoundError
        """
        # id, name, username , email, email_verified, owner_token, share_token, added
        get_list = "SELECT id, name, username, email, email_verified, owner_token, share_token from wishlist where id = ?"
        cur = self._cursor_factory(WishlistDB.wishlist_factory)
        cur.execute(get_list, (wishlist_id,))
        my_wishlist = cur.fetchone()
        if not my_wishlist:
            raise WishlistNotFoundError("No wishlist found")
        my_wishlist.items = self.get_wishlist_items(wishlist_id)
        return my_wishlist

    def get_wishlist_item(self, wishlist_id: str, item_id: str) -> WishlistItem:
        """ Returns a WishlistItem object matching a given wishlist id + item id

            Arguments:
            wishlist_id -- uuid representing a wishlist
            item_id     -- uuid representing an item on a wishlist

            Returns:
            WishlistItem object
        """
        get_item = "SELECT id, name, url, description, gotten, getter FROM wishlist_item WHERE id = ? and wishlist_id = ?"
        cur = self._conn.cursor()
        cur.row_factory = WishlistDB.wishitem_factory
        cur.execute(get_item, (item_id, wishlist_id))
        return cur.fetchone()

    def get_wishlist_items(self, wishlist_id: str) -> dict[WishlistItem]:
        """ Returns a dictionary of WishlistItem of all items associated with a given wishlist_id

            Arguments:
            wishlist_id -- uuid representing a wishlist

            Returns:
            dict[WishlistItem]
        """
        get_items = "SELECT id, name, url, description, gotten, getter FROM wishlist_item WHERE wishlist_id = ?"
        cur = self._cursor_factory(WishlistDB.wishitem_factory)
        cur.execute(get_items, (wishlist_id,))

        all_items = {}
        for row in cur:
            all_items[row.id] = row

        return all_items

    def update_wishlist_item(self, item: WishlistItem) -> None:
        """ Replaces an item in the wishlist

            Arguments:
            item -- a WishlistItem that exists in the database

            Returns:
            None

            Throws:
            sqlite3.DatabaseError
        """
        update_item = "UPDATE wishlist_item set name = ?, url = ?, description = ?, gotten = ?, getter = ? WHERE id = ?"
        cur = self._cursor_factory()
        cur.execute(
            update_item,
            (
                item.name,
                item.url,
                item.description,
                item.gotten,
                item.getter,
                str(item.id),
            ),
        )

    def remove_wishlist_item(self, item_id: str, wishlist_id: str) -> None:
        """ Removes an existing item from a wishlist.  Raises a sqlite3.DatabaseError if the item doesn't already exist

            Arguments:
            item_id -- uuid of the item to remove
            wishlist_id -- uuid of wishlist from which to remove said item

            Returns:
            None

            Throws:
            sqlite3.DatabaseError
        """
        delete_item = "DELETE FROM wishlist_item WHERE id = ? and wishlist_id = ?"
        cur = self._cursor_factory()
        cur.execute(delete_item, (item_id, wishlist_id))

    def add_items(self, wishlist_id: str, items: list[WishlistItem]) -> None:
        insert_item = f"INSERT INTO wishlist_item (id,wishlist_id,name,url,description,gotten,getter) VALUES(:id,'{wishlist_id}',:name,:url,:description,:gotten,:getter)"
        cur = self._conn.cursor()

        items_dict = [
            json.loads(json.dumps(i, cls=WishlistJSONEncoder, ensure_ascii=False))
            for i in items
        ]

        cur.executemany(insert_item, items_dict)

    def add_wishlist(self, wish_list: Wishlist) -> None:
        insert_wishlist = "INSERT INTO wishlist (id, name, username, email, owner_token, share_token) VALUES (?, ?, ?, ?, ?, ?)"
        cur = self._conn.cursor()
        cur.execute(
            insert_wishlist,
            (
                wish_list.id,
                wish_list.name,
                wish_list.username,
                wish_list.get_addr,
                wish_list.owner_token,
                wish_list.share_token,
            ),
        )

    def verify_share_token(self, wishlist_id: str, token: str) -> bool:
        count_share_token = (
            "SELECT COUNT(1) FROM wishlist WHERE id = ? and share_token = ?"
        )
        cur = self._conn.cursor()
        try:
            cur.execute(count_share_token, (wishlist_id, token))
            count = cur.fetchone()[0]
            if count > 0:
                return True
        except Exception as e:
            pass

        return False

    def verify_owner_token(self, wishlist_id: str, token: str) -> bool:
        count_owner_token = (
            "SELECT COUNT(1) FROM wishlist WHERE id = ? and owner_token = ?"
        )
        cur = self._conn.cursor()
        try:
            cur.execute(count_owner_token, (wishlist_id, token))
            count = cur.fetchone()[0]
            if count > 0:
                return True
        except Exception as e:
            pass

        return False

    def mark_valid_email(self, wishlist_id: str) -> None:
        """ Marks a wishlist as having a validated email associated with it """
        mark_valid = "UPDATE wishlist SET email_verified = 1 WHERE id = ?"
        cur = self._conn.cursor()
        cur.execute(mark_valid, (wishlist_id,))
        self.save()

    def new_session(self, session_id: str, ip: str) -> None:
        """ Stores a new session into the database """
        add_session = "INSERT INTO wishlist_session(id, ip_address) VALUES (?, ?)"
        cur = self._conn.cursor()
        cur.execute(add_session, (session_id, ip))

    def get_session(self, session_id: str) -> dict:
        """ Returns the details of an existing session from the database """
        select_session = (
            "SELECT id, ip_address, started FROM wishlist_session where id = ?"
        )
        cur = self._conn.cursor()
        cur.execute(select_session, (session_id,))
        return cur.fetchone()

    def get_session_items(self, session_id: str) -> list[WishlistItem]:
        """ Returns an array of WishlistItems that were gotten by a given session """
        select_session_items = "SELECT i.id, i.name, i.url, i.description, i.gotten, i.getter FROM wishlist_item i WHERE getter = ?"
        cur = self._cursor_factory(WishlistDB.wishitem_factory)
        cur.execute(select_session_items, (session_id,))
        return cur.fetchall()

    def sent_email(self, email: str, session_id: str ) -> None:
        """ Records a record of having sent an email to a specific addres """
        send_email = "INSERT INTO email_record(email, sender_session_id) VALUES (?, ?)"
        cur = self._conn.cursor()
        cur.execute(send_email, (email, session_id))
        self.save()

    def recent_email_count(self, email: str, since: datetime.datetime) -> int:
        """ Returns a cound of emails sent to a specific address since the provided timestamp """
        count_emails = "SELECT count(1) FROM email_record WHERE email = ? and sent_time >= ?"
        cur = self._conn.cursor()
        cur.execute(count_emails, (email, since.isoformat()))
        return cur.fetchone()[0]


def list_factory(wishlist_id: uuid.UUID) -> Wishlist:
    wishdb = WishlistDB()
    return wishdb.get_wishlist(str(wishlist_id))


def item_factory(item_id: uuid.UUID, wishlist_id: uuid.UUID) -> WishlistItem:
    wishdb = WishlistDB()
    return wishdb.get_wishlist_item(str(wishlist_id), str(item_id))


def get_items(wish_list: Wishlist) -> list[WishlistItem]:
    return wish_list.items.values()


def mark_item(
    wishlist_id: uuid.UUID, item_id: uuid.UUID, session_id: str, gotten: bool
) -> None:
    wishdb = WishlistDB()
    item = wishdb.get_wishlist_item(str(wishlist_id), str(item_id))

    if gotten is False and item.getter != session_id:
        raise Exception("You cannot modify the status of an item you didn't get!")
    elif gotten is False and item.getter == session_id:
        item.gotten = gotten
        item.getter = None
    else:
        item.gotten = gotten
        item.getter = session_id
    wishdb.update_wishlist_item(item)
    wishdb.save()

def add_item(
    wishlist_id: uuid.UUID, name: str, url: str, description: str
) -> WishlistItem:
    item = WishlistItem(name=name, url=url, description=description)
    wishdb = WishlistDB()
    wishdb.add_items(str(wishlist_id), [item])
    wishdb.save()
    return item

def remove_item(id: uuid.UUID, wishlist_id: uuid.UUID) -> bool:
    wishdb = WishlistDB()
    n_deleted = wishdb.remove_wishlist_item(str(id), str(wishlist_id))
    wishdb.save()
    if n_deleted > 0:
        return True
    else:
        return False

def new_session(ip_addr: str) -> str:
    wishdb = WishlistDB()
    session_id = secrets.token_urlsafe(32)
    wishdb.new_session(session_id, ip_addr)
    wishdb.save()
    return session_id

def verify_session(session_id: str) -> bool:
    wishdb = WishlistDB()
    if wishdb.get_session(session_id):
        return True

    return False

def verify_share_token(user_wishlist: Wishlist, token: str) -> None:
    if user_wishlist.share_token !=  token:
        raise InvalidShareToken("Invalid Token") 

def verify_manage_token(user_wishlist: Wishlist, token: str) -> None:
    if not user_wishlist.owner_token == token:
        raise InvalidManageToken("Invalid Token")
    
    if not user_wishlist.email_verified:
        wishdb = WishlistDB()
        wishdb.mark_valid_email(user_wishlist.id)
        wishdb.save()
        user_wishlist.email_verified = True


def verify_any_token(user_wishlist: Wishlist, token: str) -> None:
    if token not in [user_wishlist.owner_token, user_wishlist.share_token]:
        raise InvalidToken("Invalid Token!")


def check_mail_limit(email_addr) -> None:
    if not validator.is_email(email_addr):
        raise InvalidEmailError("Recipient email is not valid.")
    
    wishdb = WishlistDB()
    email = Address(addr_spec=email_addr)
    check_time = datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=5)
    if wishdb.recent_email_count(email.addr_spec,check_time) > 1:
        raise RateLimitError("Too many emails to the same address!")


def log_email(email_addr: str, session_id: str) -> None:
    wishdb = WishlistDB()
    email = Address(addr_spec=email_addr)
    wishdb.sent_email(email.addr_spec, session_id)


def mark_verified(wishlist_id: str) -> None:
    wishdb = WishlistDB()
    wishdb.mark_valid_email(wishlist_id)
    wishdb.save()
