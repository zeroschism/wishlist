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

import smtplib

import wishlist.wishlist as wishlist
import wishlist.validator as validator

from email.headerregistry import Address
from email.message import EmailMessage



class Mailer:
    """ Represents a way to send email somewhere """
    def __init__(self,mailhost: str, port: int = 25, username: str = None, password: str = None):
        self.mailhost = mailhost
        self.port = port
        self.username = username
        self.password = password

    def send_email(self, from_addr: str, to_addr: str, subject: str, body: str) -> None:
        msg = EmailMessage()
        msg["Subject"] = f"{subject}"
        msg["From"] = Address(addr_spec=f"{from_addr}")
        msg["To"] = Address(addr_spec=f"{to_addr}")
        msg.set_content(f"{body}")
        # render_callable('email_verify.eml',name=self.name,url=url))

        with smtplib.SMTP(self.mailhost, self.port) as mail_server:
            mail_server.send_message(msg)

    def send_share_email(self, user_wishlist: wishlist.Wishlist, sender_email: str, recipient_email: str, body: str) -> None:
        if not validator.is_email(recipient_email):
            raise wishlist.InvalidEmailError("Recipient email is not valid")
        
        subject = f"{user_wishlist.username} has shared a wishlist with you!"
        to = str(recipient_email).strip().lower()
        self.send_email(sender_email, to, subject, body)

    def send_validate_email(self, user_wishlist: wishlist.Wishlist, sender_email: str, body: str) -> None:
        """ Sends an email to the email associated with a validation url for confirming control of the associated email account

            Arguments:
            render_callable -- function reference that will turn the jinja template into a valid email
        """

        if not validator.is_email(user_wishlist.email):
            raise wishlist.InvalidEmailError("Recipient address does not appear to be a valid email.")

        subject = "New Wishlist: Verify your Email"
        self.send_email(sender_email, user_wishlist.email, subject, body)

    def send_manage_email(self, user_wishlist: wishlist.Wishlist, sender_email: str, body: str) -> None:
        if not wishlist.get_addr:
            raise wishlist.InvalidEmailError("Unable to send email.  No valid address")
        """
        body = render_callable(
            "email_manage.eml",
            name=wishlist.name,
            modify_url=f"{base_url}/{wishlist.id}?token={wishlist.owner_token}",
        )
        """
        subject = "Manage your wishlist!"
        self.send_email(sender_email, user_wishlist.email, subject, body)
