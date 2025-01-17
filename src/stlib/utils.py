#!/usr/bin/env python
#
# Lara Maia <dev@lara.monster> 2015 ~ 2023
#
# The stlib is free software: you can redistribute it and/or
# modify it under the terms of the GNU General Public License as
# published by the Free Software Foundation, either version 3 of
# the License, or (at your option) any later version.
#
# The stlib is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see http://www.gnu.org/licenses/.
#
"""
`utils` is used internaly by stlib to provide other stlib interfaces.
"""

import asyncio
import atexit
import contextlib
import http.cookies
import json
import locale
import logging
from typing import Dict, Any, Optional, NamedTuple, Union

import aiohttp
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)
_session_cache: Dict[str, Dict[int, Union['Base', aiohttp.ClientSession]]] = {'http_session': {}}


class Response(NamedTuple):
    status: int
    """Status code"""
    info: aiohttp.RequestInfo
    """Request Info"""
    cookies: http.cookies.SimpleCookie[Any]
    """Cookies"""
    content: Union[str, bytes]
    """Content as string"""
    content_type: str
    """Content type"""


class Base:
    """
    You should not instantiate this class directly!
    See `get_session`
    """

    def __new__(cls) -> None:  # type: ignore
        raise SyntaxError(
            "Don't instantiate this class directly! "
            "Use get_session(<index>) to support multiple sessions."
        )

    def __init__(self, http_session: Optional[aiohttp.ClientSession] = None, *args, **kwargs) -> None:
        self._http_session = http_session
        atexit.register(self.__close_http_session)

    def __close_http_session(self) -> None:
        coro = self._http_session.close()

        try:
            asyncio.create_task(coro)
        except RuntimeError:
            asyncio.run(coro)

    @property
    def http_session(self) -> aiohttp.ClientSession:
        """Returns the default http session"""
        if not self._http_session:
            raise AttributeError("There's no http session")

        return self._http_session

    def update_cookies(self, cookies: http.cookies.SimpleCookie[Any]) -> None:
        """Update cookies for the current http session"""
        self.http_session.cookie_jar.update_cookies(cookies)

    @classmethod
    async def new_http_session(
            cls,
            session_index: int,
            raise_for_status: bool = True,
            *args: Any, **kwargs: Any,
    ) -> aiohttp.ClientSession:
        """
        Create a http session at given `session_index`.
        If a previous instance exists in cache at same index, it will raise IndexError.

        :param session_index: Session number
        :param raise_for_status: Raise if the response status is 400 or higher.
        :param args: extra args when creating a new http session
        :param kwargs: extra kwargs when creating a new http session
        :return: Instance of module
        """
        if session_index in _session_cache['http_session']:
            raise IndexError(f"There's already a http_session session at index {session_index}")

        if 'headers' not in kwargs:
            kwargs['headers'] = {'User-Agent': 'Unknown/0.0.0'}

        log.info("Creating a new http session at index %s for custom http session", session_index)
        http_session = aiohttp.ClientSession(*args, raise_for_status=raise_for_status, **kwargs)
        _session_cache['http_session'][session_index] = http_session

        assert isinstance(http_session, aiohttp.ClientSession), "Wrong session type"
        return http_session

    @classmethod
    async def new_session(cls, session_index: int, *args: Any, **kwargs: Any) -> 'Base':
        """
        Create an instance of module at given `session_index`.
        If a previous instance exists in cache at same index, it will raise IndexError.
        The instance will be associated with a http session at same index.
        If a http session is not present in cache, it'll create a new one.
        If you need custom params for http session, use `new_http_session` before calling this method.

        :param session_index: Session number
        :param args: extra args when creating a new instance
        :param kwargs: extra kwargs when creating a new instance
        :return: Instance of module
        """
        cache_name = f'{cls.__module__}.{cls.__name__}'

        if cache_name not in _session_cache:
            log.debug("Creating a new cache object at %s for %s", session_index, cache_name)
            _session_cache[cache_name] = {}

        if session_index in _session_cache['http_session']:
            log.info("Reusing http session at index %s for %s", session_index, cache_name)
            http_session = _session_cache['http_session'][session_index]
        else:
            http_session = await cls.new_http_session(session_index)
            _session_cache['http_session'][session_index] = http_session

        if session_index in _session_cache[cache_name]:
            raise IndexError(f"There's already a {cache_name} session at index {session_index}")

        log.info("Creating a new %s session at %s", cache_name, session_index)
        session = _session_cache[cache_name][session_index] = super().__new__(cls)

        log.debug("Initializing instance for %s", cache_name)
        session.__init__(http_session=http_session, *args, **kwargs)

        assert isinstance(session, Base), "Wrong session type"
        return session

    @classmethod
    async def destroy_session(cls, session_index: int, no_fail: bool = False) -> None:
        """
        Destroy an instance of module at `session_index` and remove from cache.
        :param session_index: Session number
        :param no_fail: suppress errors if there is no session at given index
        """
        cache_name = f'{cls.__module__}.{cls.__name__}'

        if cache_name in _session_cache and session_index in _session_cache[cache_name]:
            del _session_cache[cache_name][session_index]
            http_session = _session_cache['http_session'][session_index]
            assert isinstance(http_session, aiohttp.ClientSession), "Wrong http session type"
            await http_session.close()
            del _session_cache['http_session'][session_index]
        elif not no_fail:
            raise IndexError(f"There's no session at {session_index}")

    @classmethod
    def get_session(cls, session_index: int) -> 'Base':
        """
        Get an instance of module from cache at `session_index`.
        If session isn't present in cache, it will raise IndexError
        :param session_index: session number
        :return: instance of module
        """
        cache_name = f'{cls.__module__}.{cls.__name__}'

        if cache_name not in _session_cache or session_index not in _session_cache[cache_name]:
            raise IndexError(f"There's no session for {cache_name} at {session_index}")

        session = _session_cache[cache_name][session_index]
        assert isinstance(session, Base), "Wrong session type"
        return session

    @staticmethod
    def get_json_from_js_func(javascript: BeautifulSoup, target: str, separator: str = '\t+') -> Dict[str, Any]:
        """
        get json data from javascript functions
        :param javascript: javascript parsed with data. Usually contents of a ''script''  tag
        :param target: the function to get data from
        :param separator: delimiter string where to split data while parsing
        :return: json data
        """
        json_data = {}
        for line in str(javascript).split(separator):
            if target in line:
                for item in line.split(','):
                    with contextlib.suppress(ValueError):
                        key_raw, value_raw = item.split(':"')
                        key = key_raw.replace('"', '')
                        value = bytes(value_raw.replace('"', ''), 'utf-8').decode('unicode_escape')
                        json_data[key] = value

                break

        return json_data

    @staticmethod
    def get_vars_from_js(javascript: BeautifulSoup, separator: str = '\n') -> Dict[str, Any]:
        """
        get variables and it's values from javascript
        :param javascript: javascript parsed with data. Usually contents of a ''script'' tag
        :param separator: delimiter string where to split data while parsing
        :return: a dict with variables data
        """
        vars_data = {}

        for line in str(javascript).split(separator):
            with contextlib.suppress(ValueError):
                key_raw, value_raw = line.split(" = ")
                key = key_raw.replace("var ", '').strip()
                value = value_raw[:-2].strip()
                vars_data[key] = json.loads(value)

        return vars_data

    @staticmethod
    async def get_html(response: Response) -> BeautifulSoup:
        """
        get html parsed from response
        It's a convenient helper for `request`
        """
        return BeautifulSoup(response.content, 'html.parser')

    async def request_json(self, *args: str, **kwargs: Any) -> Dict[str, Any]:
        """
        make a new http request and returns json data
        It's a convenient helper for `request`
        """
        response = await self.request(*args, **kwargs)
        json_data = json.loads(response.content)

        assert isinstance(json_data, dict)
        return json_data

    async def request_json_from_js_func(
            self,
            *args: str,
            script_index: int = 0,
            target: str,
            separator: str = '\t+',
            **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        make a new http request and returns json data from javascript at given index
        It's a convenient helper for `get_json_from_js`
        :param args: request args
        :param script_index: index of script at html page
        :param target: the function to get data from
        :param separator: delimiter string where to split data while parsing
        :param kwargs: request kwargs
        :return: json_data as Dict
        """
        html = await self.request_html(*args, **kwargs)
        javascript = html.find_all('script')[script_index]
        return self.get_json_from_js_func(javascript, target, separator)

    async def request_vars_from_js(
            self,
            *args: str,
            script_index: int = 0,
            separator: str = '\n',
            **kwargs: Any,
    ) -> Dict[str, str]:
        """
        make a new http request and returns vars data from javascript at given index
        It's a convenient helper for `get_vars_from_js`
        :param args: request args
        :param script_index: index of script at html page
        :param separator: delimiter string where to split data while parsing
        :param kwargs: request kwargs
        :return: vars_data as Dict
        """
        html = await self.request_html(*args, **kwargs)
        javascript = html.find_all('script')[script_index]
        return self.get_vars_from_js(javascript, separator)

    async def request_html(self, *args: str, **kwargs: Any) -> BeautifulSoup:
        """
        make a new http request and returns html
        It's a convenient helper for `request`
        """
        response = await self.request(*args, **kwargs)
        return await self.get_html(response)

    async def request(
            self,
            url: str,
            *,
            params: Optional[Dict[str, str]] = None,
            data: Optional[Dict[str, str]] = None,
            auto_recovery: bool = True,
            raw_data: bool = False,
            **kwargs: Any,
    ) -> Response:
        """
        Make a new http request
        :param url: URL to request
        :param params: Http parameters
        :param data: Form data
        :param auto_recovery: If defined and http request fail, it will try again
        :param raw_data: If defined it will return raw data instead text
        :param kwargs: Extra kwargs passed directly to http request
        :return: `Request`
        """
        if not params:
            params = {}

        http_method = 'POST' if data else 'GET'

        request_params: Dict[str, Any] = {
            'method': http_method,
            'url': url,
            'params': params,
            'data': data,
            **kwargs,
        }

        log.debug("Requesting %s via %s with %s:%s", url, http_method, params, data)
        try_count = 0

        while True:
            try:
                async with self.http_session.request(**request_params) as response:
                    if len(response.history) >= 1:
                        location = response.history[0].headers['Location']
                    else:
                        location = response.headers.get('Location', '')

                    if 'login/home/?goto=' in location:
                        from .login import LoginError as _LoginError  # avoid circular imports
                        raise _LoginError('User are not logged in')

                    result = Response(
                        response.status,
                        response.request_info,
                        response.cookies,
                        await response.read() if raw_data else await response.text(),
                        response.content_type,
                    )
                    break
            except (aiohttp.ClientConnectorError, asyncio.TimeoutError) as exception:
                log.debug("Connection error %s", str(exception))

                if auto_recovery:
                    log.debug("Trying again in 5 seconds")
                    await asyncio.sleep(5)
                    continue

                raise exception from None
            except aiohttp.ClientResponseError as exception:
                log.debug("Response error %s", exception.status)

                if 400 <= exception.status <= 499:
                    raise exception from None

                if auto_recovery and try_count < 3:
                    log.debug("Auto recovering in 5 seconds")
                    await asyncio.sleep(5)
                    try_count += 1
                    continue

                raise exception from None

        return result


def convert_steam_price(price: Union[str, int]) -> str:
    """
    convert raw int steam price to real monetary price
    :param price: raw steam int price
    :return: a `str` representing a monetary price
    """
    price_raw = str(price)

    if len(price_raw) == 1:
        price_raw = float(f".0{price_raw}")
    else:
        price_raw = float(f"{price_raw[:-2]}.{price_raw[-2:]}")

    locale.setlocale(locale.LC_MONETARY, "")
    return locale.currency(price_raw)
