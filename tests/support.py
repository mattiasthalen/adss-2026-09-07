"""Stand-ins the tests share. Nothing here names anything from a business."""

import json

import duckdb


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


def engine_objects(connection: duckdb.DuckDBPyConnection) -> None:
    """The objects the generator reads, shaped as the engine shapes them."""
    connection.execute("CREATE SCHEMA dab")
    connection.execute("CREATE SCHEMA dar__uss")
    connection.execute(
        'CREATE TABLE dab."view_PARENT_hist" ("PARENT_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"PARENT_NUMBER" VARCHAR, "HAPPENED_ON" TIMESTAMP, "PARENT_LABEL" VARCHAR, '
        '"PARENT_SIZE" DECIMAL(28, 8), "FINISHED_ON" TIMESTAMP)'
    )
    connection.execute(
        'CREATE TABLE dab."view_CHILD_hist" ("CHILD_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"CHILD_NUMBER" VARCHAR, "OCCURRED_ON" TIMESTAMP, "CHILD_WEIGHT" DECIMAL(28, 8))'
    )
    connection.execute(
        'CREATE TABLE dab."view_NEIGHBOUR_hist" ("NEIGHBOUR_key" VARCHAR, eff_tmstp TIMESTAMP, '
        '"NEIGHBOUR_NUMBER" VARCHAR, "NEIGHBOUR_LABEL" VARCHAR)'
    )
    for edge, source, target in (
        ("CHILD_POINTS_AT_PARENT", "CHILD", "PARENT"),
        ("CHILD_SITS_BESIDE_NEIGHBOUR", "CHILD", "NEIGHBOUR"),
    ):
        connection.execute(
            f'CREATE TABLE dab."v_{edge}" ("{source}_key" VARCHAR, "{target}_key" VARCHAR, '
            f"rel_name VARCHAR, eff_tmstp TIMESTAMP, ver_tmstp TIMESTAMP, row_st VARCHAR)"
        )
