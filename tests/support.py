"""Stand-ins the tests share. Nothing here names anything from a business."""

import json


class Responder:
    """A stand-in service that pages the way OData does, and remembers what it was asked."""

    def __init__(self, total: int) -> None:
        self.total = total
        self.seen: list[str] = []

    def __call__(self, url: str) -> bytes:
        total = self.total
        self.seen.append(url)
        skip = int(url.split("$skip=")[1].split("&")[0]) if "$skip=" in url else 0
        top = int(url.split("$top=")[1].split("&")[0])
        rows = [{"ParentId": index} for index in range(skip, min(skip + top, total))]
        return json.dumps({"@odata.count": total, "value": rows}).encode()
