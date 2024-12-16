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

import re, unicodedata, sys
from urllib.parse import urlparse, urlunparse

FORBIDDEN_UNICODE_CATEGORIES = {'Cc', 'Cf', 'Cs', 'Co', 'Cn', 'Zp', 'Zl', 'Mn', 'Mc', 'Me'}

FORBIDDEN_UNICODE_CHARACTERS = {
    i: None for i in range(sys.maxunicode) if unicodedata.category(chr(i)) in FORBIDDEN_UNICODE_CATEGORIES
}

def sanitize_unicode(input: str) -> str:
    """ Strip out any undesirable unicode characters"""
    input = unicodedata.normalize('NFC', input)
    return input.translate(FORBIDDEN_UNICODE_CHARACTERS)

def normalize_words(input: str, max_length: int = 256) -> str:
    """ Return string with extra whitespace and unpleasant unicode characters removed """
    return sanitize_unicode(f"{input[:max_length]}".strip())

def normalize_url(input: str) -> str:
    if is_url(input):
        parsed_url = urlparse(input,'http')
        parsed_url = parsed_url._replace(netloc=parsed_url.netloc.lower())
        return str(urlunparse(parsed_url))
    else:
        raise ValueError("Not a URL: Cannot normalize")

def is_valid_hostname(input: str) -> bool:
    """ Perform some basic validation to ensure we have something that at least seems like a valid DNS hostname """
    valid_hostname = re.compile("(?!-)[a-z\d-]{1,63}(?<!-)$", re.IGNORECASE|re.ASCII)

    if len(input) > 255:
        return False
    
    # Strip the dot on the far right, if it exists
    try:
        if input[-1] == ".":
            input = input[:-1]
    except IndexError:
        pass

    return all(valid_hostname.match(x) for x in input.split('.'))

def is_email(input: str) -> bool:
    """ Perform some basic validation to ensure we have something that at least seems like an email address """
    valid_username = re.compile("(?![^a-z0-9]).+(?<![^a-z0-9])$", re.IGNORECASE|re.ASCII)

    parts = normalize_words(input).split('@')
    if len(parts) != 2:
        return False

    return is_valid_hostname(parts[1]) and valid_username.match(parts[0]) is not None

def is_url(input: str) -> bool:
    """ Perform some basic validation to ensure we have something that at least looks like an acceptable web url """
    try:
        parsed_url = urlparse(str(input),'http')
    except ValueError:
        return False

    if parsed_url.scheme not in {'http', 'https'}:
        return False
    
    if not is_valid_hostname(parsed_url.netloc.split(':')[0]):
        return False
    
    return True
