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

import tomllib, socket

class ConfigurationException(Exception):
    pass

class AppConfig:
    def __init__(self,config=None):
        self.host_name: str = "localhost"
        self.base_uri: str = "/"
        self.title: str = "My Wishlist"
        self.is_ssl: bool = False
        self.is_proxied: bool = False
        self.session_key: str = ""
        self.location: str = f"http://{self.host_name}{self.base_uri}"
        self.description: str = "A list of wishes to share with everyone"
        if config:
            self.load_config(config)

    def load_config(self,config: dict[str,any]) -> None:
        try:
            if not isinstance(config["host_name"],str):
                raise TypeError("Configuration item 'host_name' in [app] must be a string!")
            else:
                self.host_name = config["host_name"]
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["base_uri"], str):
                raise TypeError("Configuration item 'base_uri' in [app] must be a string!")
            else:               
                self.base_uri = config["base_uri"]
                # prepend leading "/" if it is missing
                if self.base_uri[0] != "/":
                    self.base_uri = f"/{self.base_uri}"
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["title"],str):
                raise TypeError("Configuration item 'title' in [app] must be a string!")
            else:
                self.title = config["title"]
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["description"],str):
                raise TypeError("Configuration item 'description' in [app] must be a string!")
            else:
                self.description = config["description"]
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["is_ssl"],bool):
                raise TypeError("Configuration item 'is_ssl' in [app] must be either True of False")
            else:
                self.is_ssl = config["is_ssl"]
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["is_proxied"],bool):
                raise TypeError("Configuration item 'is_proxied' in [app] must be either True of False")
            else:
                self.is_proxied = config["is_proxied"]
        except KeyError:
            # We will just take the default
            pass

        try:
            if not isinstance(config["session_key"],str):
                raise TypeError("Configuration item 'session_key' in [app] must be a string!")
            else:
                self.session_key = config["session_key"]
        except KeyError:
            raise ConfigurationException("Missing required value for [app] -> 'session_key' in configuration!")

        prefix = "http"
        if self.is_ssl:
            prefix = "https"

        self.location = f"{prefix}://{self.host_name}{self.base_uri}"


class EmailConfig:
    def __init__(self,config=None):
        self.from_address: str = f"wishlist-no-reply@{'.'.join(socket.getfqdn().split('.')[1:])}"
        self.relay_server: str = "localhost"
        self.relay_port: int = 25
        if config:
            self.load_config(config)

    def load_config(self, config: dict[str,any]) -> None:
        try:
            if not isinstance(config["from_address"],str):
                raise TypeError("Configuration item 'from_address' in [email] must be a string")
            else:
                self.from_address = config["from_address"]
        except KeyError:
            # Accept the defaults
            pass

        try:
            if not isinstance(config["relay_server"],str):
                raise TypeError("Configuration item 'relay_server' in [email] must be a string")
            else:
                self.relay_server = config["relay_server"]
        except KeyError:
            # Accept the defaults
            pass


class WishlistConfig:
    def __init__(self,conffile="config.toml"):
        self._config = self.load_config(conffile)
        try:
            self.app = AppConfig(self._config["app"])
        except KeyError:
            #missing configuration section.  We will just load the defaults
            self.app = AppConfig()

        try:
            self.email = EmailConfig(self._config["email"])
        except KeyError:
            #missing configuration section.  We will just load the defaults
            self.email = EmailConfig()
            
    def load_config(self,conffile: str) -> dict[str, any]:
        with open(conffile, "rb") as conf_file:
            return tomllib.load(conf_file)
        
    
