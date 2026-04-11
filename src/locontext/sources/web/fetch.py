from __future__ import annotations

from dataclasses import dataclass

import httpx


@dataclass(slots=True)
class FetchedWebPage:
    requested_locator: str
    resolved_locator: str
    status_code: int
    headers: dict[str, str]
    content: bytes

    @property
    def content_type(self) -> str | None:
        return self.headers.get("content-type")


class WebFetchError(Exception):
    pass


class WebRequestError(WebFetchError):
    def __init__(self, locator: str, message: str) -> None:
        super().__init__(message)
        self.locator: str = locator


class WebHTTPStatusError(WebFetchError):
    def __init__(self, locator: str, status_code: int, message: str) -> None:
        super().__init__(message)
        self.locator: str = locator
        self.status_code: int = status_code


def fetch_web_page(
    locator: str,
    *,
    client: httpx.Client | None = None,
    timeout: float | httpx.Timeout = 10.0,
) -> FetchedWebPage:
    if client is None:
        with httpx.Client(follow_redirects=True, timeout=timeout) as owned_client:
            return _fetch_with_client(locator, owned_client, timeout)
    return _fetch_with_client(locator, client, timeout)


def _fetch_with_client(
    locator: str,
    client: httpx.Client,
    timeout: float | httpx.Timeout,
) -> FetchedWebPage:
    try:
        response = client.get(locator, follow_redirects=True, timeout=timeout)
        _ = response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise WebHTTPStatusError(
            locator=locator,
            status_code=exc.response.status_code,
            message=str(exc),
        ) from exc
    except httpx.RequestError as exc:
        raise WebRequestError(locator=locator, message=str(exc)) from exc

    return FetchedWebPage(
        requested_locator=locator,
        resolved_locator=str(response.url),
        status_code=response.status_code,
        headers={key.lower(): value for key, value in response.headers.items()},
        content=response.content,
    )
