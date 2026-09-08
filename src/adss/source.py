"""Reading a source once, and replaying that reading everywhere else.

A replay follows the same code path and the same requests as a live read: the only thing
swapped is what answers them. That sameness is the whole value -- a replay that took a
different path would prove nothing about the live run. ADR 0003.
"""

from __future__ import annotations

import json
import urllib.request
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from adss.contract import Endpoint

# A request, answered. Injected so a replay and a live read differ in nothing else.
Fetch = Callable[[str], bytes]

MANIFEST = "manifest.json"


class RecordingError(Exception):
    """A replay was asked for something the recording does not hold."""


def page_url(endpoint: Endpoint, skip: int) -> str:
    """One page of an entity set, always asking for the total so paging can end."""
    return f"{endpoint.url}?$count=true&$top={endpoint.page_size}&$skip={skip}"


def pages(endpoint: Endpoint, fetch: Fetch) -> Iterator[tuple[str, list[dict[str, Any]]]]:
    """Every page of the entity set, as (url, records).

    The url is yielded because it is provenance: it is what the row will carry to say where
    it came from.
    """
    skip = 0
    total: int | None = None
    while total is None or skip < total:
        url = page_url(endpoint, skip)
        document = json.loads(fetch(url))
        total = int(document["@odata.count"]) if total is None else total
        records = list(document["value"])
        if not records:
            return
        yield url, records
        skip += len(records)


def over_http(url: str) -> bytes:
    with urllib.request.urlopen(url, timeout=60) as response:
        return bytes(response.read())


def record(endpoint: Endpoint, fetch: Fetch, directory: Path) -> int:
    """Read the source and keep every response body verbatim, with the request beside it.

    Verbatim because a recording that keeps only the records it parsed is a recording of our
    parser. When the source changes, the diff on these files is the change, visible.
    """
    directory.mkdir(parents=True, exist_ok=True)
    for stale in directory.glob("page-*.json"):
        stale.unlink()

    requests: dict[str, str] = {}
    skip = 0
    total: int | None = None
    while total is None or skip < total:
        url = page_url(endpoint, skip)
        body = fetch(url)
        document = json.loads(body)
        total = int(document["@odata.count"]) if total is None else total
        records = list(document["value"])
        if not records:
            break
        name = f"page-{len(requests):04d}.json"
        (directory / name).write_bytes(body)
        requests[url] = name
        skip += len(records)

    (directory / MANIFEST).write_text(
        json.dumps({"entity": endpoint.entity, "requests": requests}, indent=2) + "\n"
    )
    return len(requests)


def replay(directory: Path) -> Fetch:
    """Answer requests from a recording, and refuse anything it does not cover."""
    manifest = json.loads((directory / MANIFEST).read_text())
    recorded = manifest["requests"]
    assert isinstance(recorded, dict), f"{directory / MANIFEST} has no request index"
    requests: dict[str, str] = {str(url): str(name) for url, name in recorded.items()}

    def fetch(url: str) -> bytes:
        name = requests.get(url)
        if name is None:
            raise RecordingError(
                f"the recording in {directory} does not cover {url}. Re-record it with "
                f"`adss das record`, and read the diff: it is what changed upstream."
            )
        return (directory / name).read_bytes()

    return fetch
