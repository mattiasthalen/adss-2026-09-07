"""Landing: every source record, whole, appended to a hive-partitioned parquet lake.

Nothing here decides what a field is. The record arrives as one JSON value and stays that
way, so a field the contract has never heard of still lands and is simply not yet
extracted -- which is what makes an upstream change a contract edit rather than an outage.
ADR 0003.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import dlt
from dlt.destinations import filesystem

from adss.contract import Contract
from adss.names import Schema
from adss.source import Fetch, pages

# The load's own clock names the partition. Placeholders are the loader's, and it rejects
# any it does not know, so a typo here fails loudly rather than landing somewhere odd.
LAYOUT = "{table_name}/extracted_on={YYYY}-{MM}-{DD}/{load_id}.{file_id}.{ext}"


def land(contract: Contract, fetch: Fetch, root: Path, pipelines_dir: Path) -> list[str]:
    """Append one load of one contract's entity set to the lake. Returns the load ids."""

    @dlt.resource(  # type: ignore[misc]
        name=contract.table,
        write_disposition="append",
        columns={"payload": {"data_type": "json"}},
    )
    def records() -> Iterator[dict[str, Any]]:
        for url, page in pages(contract.source, fetch):
            for record in page:
                # payload is a single json-typed column, so nothing inside it is inferred,
                # split into columns, or promoted to a child table.
                yield {
                    "payload": record,
                    "source_system": contract.source.service,
                    "source_entity": contract.source.entity,
                    "source_url": url,
                }

    destination = filesystem(
        bucket_url=root.absolute().as_uri(),
        layout=LAYOUT,
        # Without this the dataset name is normalised and das__raw quietly becomes das_raw,
        # with only a warning to say so.
        enable_dataset_name_normalization=False,
    )
    pipeline = dlt.pipeline(
        pipeline_name=f"adss_das_{contract.table}",
        destination=destination,
        dataset_name=str(Schema.DAS_RAW),
        pipelines_dir=str(pipelines_dir),
    )
    info = pipeline.run(records(), loader_file_format="parquet")
    return list(info.loads_ids)
