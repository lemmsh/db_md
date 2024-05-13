#!/usr/bin/env python
#
# this is copied from the python-telegram and modified in a way when the local_address can be suppled to the Async http client to force ipv4/ipv6
# accorging to the https://github.com/encode/httpx/pull/3052
# we need to create a PR to telegram to allow for passing this parameter
#
# A library that provides a Python interface to the Telegram Bot API
# Copyright (C) 2015-2024
# Leandro Toledo de Souza <devs@python-telegram-bot.org>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser Public License for more details.
#
# You should have received a copy of the GNU Lesser Public License
# along with this program.  If not, see [http://www.gnu.org/licenses/].
"""This module contains methods to make POST and GET requests using the httpx library."""
from typing import Collection, Optional, Tuple, Union

import httpx

from telegram._utils.defaultvalue import DefaultValue
from telegram._utils.logging import get_logger
from telegram._utils.types import HTTPVersion, ODVInput, SocketOpt
from telegram._utils.warnings import warn
from telegram.error import NetworkError, TimedOut
from telegram.request._baserequest import BaseRequest
from telegram.request._requestdata import RequestData
from telegram.warnings import PTBDeprecationWarning

# Note to future devs:
# Proxies are currently only tested manually. The httpx development docs have a nice guide on that:
# https://www.python-httpx.org/contributing/#development-proxy-setup (also saved on archive.org)
# That also works with socks5. Just pass `--mode socks5` to mitmproxy

_LOGGER = get_logger(__name__, "MDHTTPXRequest")


class MDHTTPXRequest(BaseRequest):
    __slots__ = ("_client", "_client_kwargs", "_http_version", "_media_write_timeout")

    def __init__(
        self,
        connection_pool_size: int = 1,
        proxy_url: Optional[Union[str, httpx.Proxy, httpx.URL]] = None,
        read_timeout: Optional[float] = 5.0,
        write_timeout: Optional[float] = 5.0,
        connect_timeout: Optional[float] = 5.0,
        pool_timeout: Optional[float] = 1.0,
        http_version: HTTPVersion = "1.1",
        proxy: Optional[Union[str, httpx.Proxy, httpx.URL]] = None,
        media_write_timeout: Optional[float] = 20.0,
    ):
        if proxy_url is not None and proxy is not None:
            raise ValueError("The parameters `proxy_url` and `proxy` are mutually exclusive.")

        if proxy_url is not None:
            proxy = proxy_url
            warn(
                "The parameter `proxy_url` is deprecated since version 20.7. Use `proxy` "
                "instead.",
                PTBDeprecationWarning,
                stacklevel=2,
            )

        self._http_version = http_version
        self._media_write_timeout = media_write_timeout
        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )
        limits = httpx.Limits(
            max_connections=connection_pool_size,
            max_keepalive_connections=connection_pool_size,
        )

        if http_version not in ("1.1", "2", "2.0"):
            raise ValueError("`http_version` must be either '1.1', '2.0' or '2'.")

        http1 = http_version == "1.1"
        http_kwargs = {"http1": http1, "http2": not http1}
        transport = (
            httpx.AsyncHTTPTransport(
                local_address="0.0.0.0"
            )
        )
        self._client_kwargs = {
            "timeout": timeout,
            "proxy": proxy,
            "limits": limits,
            "transport": transport,
            **http_kwargs,
        }

        try:
            self._client = self._build_client()
        except ImportError as exc:
            if "httpx[http2]" not in str(exc) and "httpx[socks]" not in str(exc):
                raise exc

            if "httpx[socks]" in str(exc):
                raise RuntimeError(
                    "To use Socks5 proxies, PTB must be installed via `pip install "
                    '"python-telegram-bot[socks]"`.'
                ) from exc
            raise RuntimeError(
                "To use HTTP/2, PTB must be installed via `pip install "
                '"python-telegram-bot[http2]"`.'
            ) from exc

    @property
    def http_version(self) -> str:
        """
        :obj:`str`: Used HTTP version, see :paramref:`http_version`.

        .. versionadded:: 20.2
        """
        return self._http_version

    @property
    def read_timeout(self) -> Optional[float]:
        """See :attr:`BaseRequest.read_timeout`.

        Returns:
            :obj:`float` | :obj:`None`: The default read timeout in seconds as passed to
                :paramref:`HTTPXRequest.read_timeout`.
        """
        return self._client.timeout.read

    def _build_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(**self._client_kwargs)  # type: ignore[arg-type]

    async def initialize(self) -> None:
        """See :meth:`BaseRequest.initialize`."""
        if self._client.is_closed:
            self._client = self._build_client()

    async def shutdown(self) -> None:
        """See :meth:`BaseRequest.shutdown`."""
        if self._client.is_closed:
            _LOGGER.debug("This HTTPXRequest is already shut down. Returning.")
            return

        await self._client.aclose()

    async def do_request(
        self,
        url: str,
        method: str,
        request_data: Optional[RequestData] = None,
        read_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        write_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        connect_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
        pool_timeout: ODVInput[float] = BaseRequest.DEFAULT_NONE,
    ) -> Tuple[int, bytes]:
        """See :meth:`BaseRequest.do_request`."""
        if self._client.is_closed:
            raise RuntimeError("This HTTPXRequest is not initialized!")

        files = request_data.multipart_data if request_data else None
        data = request_data.json_parameters if request_data else None

        # If user did not specify timeouts (for e.g. in a bot method), use the default ones when we
        # created this instance.
        if isinstance(read_timeout, DefaultValue):
            read_timeout = self._client.timeout.read
        if isinstance(connect_timeout, DefaultValue):
            connect_timeout = self._client.timeout.connect
        if isinstance(pool_timeout, DefaultValue):
            pool_timeout = self._client.timeout.pool

        if isinstance(write_timeout, DefaultValue):
            write_timeout = self._client.timeout.write if not files else self._media_write_timeout

        timeout = httpx.Timeout(
            connect=connect_timeout,
            read=read_timeout,
            write=write_timeout,
            pool=pool_timeout,
        )

        try:
            res = await self._client.request(
                method=method,
                url=url,
                headers={"User-Agent": self.USER_AGENT},
                timeout=timeout,
                files=files,
                data=data,
            )
        except httpx.TimeoutException as err:
            if isinstance(err, httpx.PoolTimeout):
                raise TimedOut(
                    message=(
                        "Pool timeout: All connections in the connection pool are occupied. "
                        "Request was *not* sent to Telegram. Consider adjusting the connection "
                        "pool size or the pool timeout."
                    )
                ) from err
            raise TimedOut from err
        except httpx.HTTPError as err:
            # HTTPError must come last as its the base httpx exception class
            # TODO p4: do something smart here; for now just raise NetworkError

            # We include the class name for easier debugging. Especially useful if the error
            # message of `err` is empty.
            raise NetworkError(f"httpx.{err.__class__.__name__}: {err}") from err

        return res.status_code, res.content