"""Records are read once from a service and replayed everywhere. ADR 0003."""

import json
from pathlib import Path

import pytest

from adss.contract import read_contract
from adss.source import RecordingError, pages, record, replay
from support import Responder

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def endpoint():
    return read_contract(FIXTURES / "parent.yaml").source


def test_paging_asks_for_a_count_and_walks_to_the_end():
    fetch = Responder(total=5)
    got = list(pages(endpoint(), fetch))
    assert [len(records) for _, records in got] == [2, 2, 1]
    assert all("$count=true" in url for url in fetch.seen)
    assert "$top=2" in fetch.seen[0]


def test_paging_stops_without_asking_for_a_page_it_knows_is_empty():
    fetch = Responder(total=4)
    list(pages(endpoint(), fetch))
    assert len(fetch.seen) == 2, "a total of 4 at 2 per page is two requests, not three"


def test_an_empty_source_yields_nothing_rather_than_failing():
    assert list(pages(endpoint(), Responder(total=0))) == []


def test_a_recording_replays_the_same_records_through_the_same_urls(tmp_path: Path):
    fetch = Responder(total=5)
    record(endpoint(), fetch, tmp_path)

    live = [records for _, records in pages(endpoint(), fetch)]
    replayed = [records for _, records in pages(endpoint(), replay(tmp_path))]
    assert replayed == live


def test_a_replay_of_a_request_that_was_never_recorded_fails_loudly(tmp_path: Path):
    record(endpoint(), Responder(total=2), tmp_path)
    (tmp_path / "manifest.json").write_text(json.dumps({"requests": {}}))
    with pytest.raises(RecordingError, match="does not cover"):
        list(pages(endpoint(), replay(tmp_path)))


def test_a_recording_keeps_the_response_body_verbatim(tmp_path: Path):
    record(endpoint(), Responder(total=1), tmp_path)
    bodies = sorted(tmp_path.glob("page-*.json"))
    assert len(bodies) == 1
    document = json.loads(bodies[0].read_text())
    assert document["@odata.count"] == 1, "the recording is the response, not the records in it"
