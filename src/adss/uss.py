"""The Unified Star Schema, generated: an event bridge, a peripheral per entity, a calendar.

Keys inherit along many-to-one relationships; measures do not. Copying a parent's measure
onto every child row would multiply it when summed, which is the fan trap a bridge exists to
avoid -- so a measure is non-null only on the stage of the (entity, event) that owns it, and
every other branch of the union emits a typed NULL. ADR 0002.

Slice 1 has one entity and no relationships, so the walk that inherits keys has no edges. A
zero-edge walk is a valid walk, and the tests say so, because the alternative is meeting it
as a special case the first time an edge exists.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from adss.model import Entity, Model, Relationship
from adss.names import Relation, Schema, crossing

BRIDGE = Relation(Schema.DAR_USS, "_bridge")
CALENDAR = Relation(Schema.DAR_USS, "_calendar")

COUNT_TYPE = "BIGINT"
SUM_TYPE = "DECIMAL(28, 8)"

_GENERATED = "-- Generated from dab/model.yaml and dab/uss.yaml. Do not edit; regenerate."


class UssError(Exception):
    """A declaration the generator will not build from."""


class Aggregate(StrEnum):
    COUNT = "count"
    SUM = "sum"


class EventKind(StrEnum):
    TRANSACTION = "transaction"
    SNAPSHOT = "snapshot"


@dataclass(frozen=True, slots=True)
class Measure:
    id: str
    definition: str
    aggregate: Aggregate
    attribute_id: str | None

    @property
    def sql_type(self) -> str:
        return COUNT_TYPE if self.aggregate is Aggregate.COUNT else SUM_TYPE


@dataclass(frozen=True, slots=True)
class Event:
    id: str
    entity_id: str
    definition: str
    kind: EventKind
    date_attribute_id: str
    measures: tuple[Measure, ...]

    @property
    def name(self) -> str:
        return self.id.lower()


@dataclass(frozen=True, slots=True)
class Uss:
    path: Path
    events: tuple[Event, ...]

    def measure_columns(self) -> tuple[tuple[Event, Measure, str], ...]:
        """Every measure column in the bridge, in declaration order."""
        return tuple(
            (event, measure, f"_measure__{event.entity_id.lower()}__{measure.id.lower()}")
            for event in self.events
            for measure in event.measures
        )


def read_uss(path: Path, model: Model | None = None) -> Uss:
    """Read the declarations, refusing anything that would generate but should not."""
    document = yaml.safe_load(path.read_text())["uss"]
    events: list[Event] = []
    for declared in document["events"]:
        event_id = str(declared["id"])
        if "definition" not in declared:
            raise UssError(
                f"{path}: event {event_id} has no definition. A glossary copies these "
                f"strings verbatim, so one that does not exist becomes a blank row."
            )
        measures: list[Measure] = []
        for raw in declared.get("measures", ()):
            aggregate = Aggregate(str(raw["aggregate"]))
            if "definition" not in raw:
                raise UssError(f"{path}: measure {raw['id']} has no definition.")
            attribute_id = str(raw["attribute"]).strip() if raw.get("attribute") else None
            if aggregate is Aggregate.SUM and not attribute_id:
                raise UssError(
                    f"{path}: measure {raw['id']} declares aggregate: sum and names nothing "
                    f"to sum. A blank attribute would emit a column named after nothing."
                )
            measures.append(
                Measure(
                    id=str(raw["id"]),
                    definition=str(raw["definition"]),
                    aggregate=aggregate,
                    attribute_id=attribute_id,
                )
            )
        events.append(
            Event(
                id=event_id,
                entity_id=str(declared["entity"]),
                definition=str(declared["definition"]),
                kind=EventKind(str(declared["kind"])),
                date_attribute_id=str(declared["date_attribute"]),
                measures=tuple(measures),
            )
        )
    uss = Uss(path=path, events=tuple(events))
    resolved = model or _model_beside(path)
    _refuse_edges_that_would_collide(resolved)
    _refuse_measures_of_things_that_are_not_numbers(uss, resolved)
    return uss


def _model_beside(path: Path) -> Model:
    from adss.model import read_model

    return read_model(path.parent / "model.yaml")


def _refuse_edges_that_would_collide(model: Model) -> None:
    """Two edges into one key column is a silent loss, so it is refused rather than emitted.

    A stage carries one column per entity it inherits from, named for that entity. Two edges
    from one entity to the same target -- or an edge to the entity itself -- would emit two
    columns of the same name, and DuckDB resolves that ambiguity instead of raising, so one of
    the two inherited keys vanishes with nothing to say which. Distinguishing them means naming
    the column after the edge rather than the target, which changes a published contract, so it
    is a decision for the slice that first needs two such edges rather than a shape to guess at
    now. ADR 0006.
    """
    for entity in model.entities:
        edges = model.edges_from(entity.id)
        for edge in edges:
            if edge.target_entity_id == entity.id:
                raise UssError(
                    f"{edge.id} points at the entity it runs from, so the stage would carry "
                    f"{entity.key_column} twice under one name and lose one of them silently."
                )
        targets = [edge.target_entity_id for edge in edges]
        for target in targets:
            if targets.count(target) > 1:
                colliding = [edge.id for edge in edges if edge.target_entity_id == target]
                raise UssError(
                    f"{' and '.join(colliding)} both inherit into "
                    f"{model.entity(target).key_column}, and a stage carrying that column "
                    f"twice loses one of them with no error. Naming the column after the edge "
                    f"rather than the target would fix it and would change the bridge's "
                    f"published contract, so it is a decision rather than a patch."
                )


def _refuse_measures_of_things_that_are_not_numbers(uss: Uss, model: Model) -> None:
    for event in uss.events:
        if event.kind is not EventKind.TRANSACTION:
            raise UssError(
                f"{event.id} is declared {event.kind}, and the generator only builds "
                f"transaction stages. It would emit a transaction stage anyway and mark "
                f"every row current, which is worse than refusing: nothing downstream could "
                f"tell. A snapshot stage arrives in the slice that first needs one."
            )
        entity = model.entity(event.entity_id)
        if not entity.attribute(event.date_attribute_id).is_date:
            raise UssError(
                f"{event.id} is dated by {event.date_attribute_id}, which is not a date."
            )
        for measure in event.measures:
            if measure.attribute_id and not entity.attribute(measure.attribute_id).is_number:
                raise UssError(
                    f"{event.id}.{measure.id} sums {measure.attribute_id}, which is not a "
                    f"number. Summing what is not a number produces a number nobody can read."
                )


def _version_cte(model: Model, event: Event) -> str:
    """The version of each entity this event is measured on: the latest in which it is dated."""
    entity = model.entity(event.entity_id)
    date = crossing(event.date_attribute_id)
    held = "revision"
    lines = [
        f"    {held}.{crossing(entity.source_key)} AS {entity.key_column}",
        f"    {held}.eff_tmstp AS _observed_at",
        f"    cast({held}.{date} AS DATE) AS _event_date",
    ]
    for measure in event.measures:
        column = f"_measure__{entity.object_name}__{measure.id.lower()}"
        if measure.aggregate is Aggregate.COUNT:
            value = f"cast(1 AS {COUNT_TYPE})"
        else:
            attribute = crossing(str(measure.attribute_id))
            value = f"cast({held}.{attribute} AS {SUM_TYPE})"
        lines.append(f"    {value} AS {column}")
    selected = ",\n".join(lines)
    return (
        f"{event.name}__version AS (\n"
        f"SELECT\n{selected}\n"
        f'FROM dab."view_{entity.id}_hist" AS {held}\n'
        f"WHERE {held}.{date} IS NOT NULL\n"
        f"QUALIFY row_number() OVER (\n"
        f"    PARTITION BY {held}.{crossing(entity.source_key)}\n"
        f"    ORDER BY {held}.eff_tmstp DESC\n"
        f") = 1\n"
        f")"
    )


def _inherit_cte(model: Model, event: Event, edge: Relationship) -> str:
    """One inherited key: the pair in force when the inheriting row was observed. ADR 0006.

    Resolved per inheriting ROW rather than per key -- the partition carries the observation
    time -- because that is the whole reason ADR 0006 chose the observation time over "now".
    A stage that kept more than the latest version of an entity would otherwise hand every one
    of those versions the same parent, which is "as of now" wearing the other rule's clothes.

    Read from `v_<SRC>_<NAME>_<TGT>`, which is the raw pairs plus the relationship's name, and
    ranked here rather than by the engine. The engine's own ranked view answers a different
    question -- who the parent is *now* -- and answers it with `rank()`, which returns two rows
    for a child whose source named two parents at one instant. Two rows here would double that
    child's measures, so the ranking is `row_number()` and the tie is refused by a data check.
    """
    source = model.entity(edge.source_entity_id)
    target = model.entity(edge.target_entity_id)
    held = edge.id.lower()
    return (
        f"{event.name}__{held} AS (\n"
        f"SELECT\n"
        f"    revision.{source.key_column} AS {source.key_column},\n"
        f"    revision._observed_at AS _observed_at,\n"
        f"    pair.{crossing(target.source_key)} AS {target.key_column}\n"
        f"FROM {event.name}__version AS revision\n"
        f'LEFT JOIN dab."v_{edge.id}" AS pair\n'
        f"    ON pair.{crossing(source.source_key)} = revision.{source.key_column}\n"
        f"    AND pair.rel_name = '{edge.id}'\n"
        f"    AND pair.row_st = 'Y'\n"
        f"    AND pair.eff_tmstp <= revision._observed_at\n"
        f"QUALIFY row_number() OVER (\n"
        f"    PARTITION BY revision.{source.key_column}, revision._observed_at\n"
        f"    ORDER BY\n"
        f"        pair.eff_tmstp DESC,\n"
        f"        pair.ver_tmstp DESC,\n"
        f"        pair.{crossing(target.source_key)}\n"
        f") = 1\n"
        f")"
    )


def _stage_cte(model: Model, event: Event) -> str:
    """One stage: the entity's version, with the key of everything it inherits from."""
    entity = model.entity(event.entity_id)
    edges = model.edges_from(entity.id)
    lines = [
        f"    revision.{entity.key_column} AS {entity.key_column}",
        "    revision._observed_at AS _observed_at",
        "    revision._event_date AS _event_date",
    ]
    lines += [
        f"    {edge.id.lower()}.{model.entity(edge.target_entity_id).key_column} "
        f"AS {model.entity(edge.target_entity_id).key_column}"
        for edge in edges
    ]
    lines += [
        f"    revision._measure__{entity.object_name}__{measure.id.lower()} "
        f"AS _measure__{entity.object_name}__{measure.id.lower()}"
        for measure in event.measures
    ]
    # One row per inheriting row in each of these, so none of the joins can fan out. LEFT
    # anyway: the row that inherits nothing is kept by the join inside the CTE, and an inner
    # join here would undo that one level up.
    joins = "".join(
        f"\nLEFT JOIN {event.name}__{edge.id.lower()} AS {edge.id.lower()}\n"
        f"    ON {edge.id.lower()}.{entity.key_column} = revision.{entity.key_column}\n"
        f"    AND {edge.id.lower()}._observed_at = revision._observed_at"
        for edge in edges
    )
    selected = ",\n".join(lines)
    return (
        f"{event.name} AS (\nSELECT\n{selected}\nFROM {event.name}__version AS revision{joins}\n)"
    )


def _branch(model: Model, uss: Uss, event: Event, keys: tuple[str, ...]) -> str:
    """One branch of the union: this stage's own columns, and a typed NULL for the rest."""
    entity = model.entity(event.entity_id)
    carried = {entity.key_column} | {
        model.entity(edge.target_entity_id).key_column for edge in model.edges_from(entity.id)
    }
    lines = [
        f"    '{entity.object_name}' AS _stage",
        f"    '{event.name}' AS _event",
        f"    {event.name}._event_date AS _event_date",
        "    TRUE AS _is_current",
        f"    {event.name}._observed_at AS _observed_at",
    ]
    for key in keys:
        value = f"{event.name}.{key}" if key in carried else "cast(NULL AS VARCHAR)"
        lines.append(f"    {value} AS {key}")
    owned = {column for candidate, _, column in uss.measure_columns() if candidate is event}
    for _, measure, column in uss.measure_columns():
        value = f"{event.name}.{column}" if column in owned else f"cast(NULL AS {measure.sql_type})"
        lines.append(f"    {value} AS {column}")
    return "SELECT\n" + ",\n".join(lines) + f"\nFROM {event.name} AS {event.name}"


def entity_ids(model: Model, uss: Uss) -> tuple[str, ...]:
    """Every entity the bridge names, in MODEL order: the ones with events, and the ones they
    inherit from. An entity reached only by inheritance still needs a peripheral, or the bridge
    carries a key that joins to nothing.
    """
    touched = {event.entity_id for event in uss.events}
    touched |= {
        edge.target_entity_id for event in uss.events for edge in model.edges_from(event.entity_id)
    }
    return tuple(entity.id for entity in model.entities if entity.id in touched)


def entity_keys(model: Model, uss: Uss) -> tuple[str, ...]:
    """One key column per entity the bridge names, in MODEL order.

    Model order, not event order: reordering two events in the sidecar is not a model change,
    and it must not rearrange a contract that consumers are written against. The check cannot
    catch that on its own, because it derives what it expects from this same function.
    """
    return tuple(model.entity(entity_id).key_column for entity_id in entity_ids(model, uss))


def bridge_columns(model: Model, uss: Uss) -> tuple[str, ...]:
    """The published column contract, in order. A model change appends; it never rearranges."""
    keys = entity_keys(model, uss)
    structural = ("_stage", "_event", "_event_date", "_is_current", "_observed_at")
    return structural + keys + tuple(column for _, _, column in uss.measure_columns())


def bridge_sql(model: Model, uss: Uss) -> str:
    """One row per measurement event, over every stage the declarations name."""
    keys = entity_keys(model, uss)
    ctes = ",\n\n".join(
        cte
        for event in uss.events
        for cte in (
            _version_cte(model, event),
            *(_inherit_cte(model, event, edge) for edge in model.edges_from(event.entity_id)),
            _stage_cte(model, event),
        )
    )
    branches = "\n\nUNION ALL\n\n".join(_branch(model, uss, event, keys) for event in uss.events)
    return f"{_GENERATED}\nCREATE OR REPLACE TABLE {BRIDGE.sql} AS\nWITH {ctes}\n\n{branches};\n"


def peripheral_sql(model: Model, entity_id: str) -> str:
    """One row per entity instance, current state, key first and attributes as declared."""
    entity: Entity = model.entity(entity_id)
    lines = [
        f"    e.{crossing(entity.source_key)} AS {entity.key_column}",
        "    e.eff_tmstp AS _observed_at",
    ]
    lines += [f"    e.{crossing(a.id)} AS {a.column}" for a in entity.attributes]
    selected = ",\n".join(lines)
    relation = Relation(Schema.DAR_USS, entity.object_name)
    return (
        f"{_GENERATED}\n"
        f"CREATE OR REPLACE TABLE {relation.sql} AS\n"
        f"SELECT\n{selected}\n"
        f'FROM dab."view_{entity.id}_hist" AS e\n'
        f"QUALIFY row_number() OVER (\n"
        f"    PARTITION BY e.{crossing(entity.source_key)}\n"
        f"    ORDER BY e.eff_tmstp DESC\n"
        f") = 1;\n"
    )


def calendar_sql() -> str:
    """Dense and daily across everything the bridge holds. Civil arithmetic only.

    A calendar containing only the days something happened is not a calendar: a month with
    no events must still appear in a time series. Fiscal periods and holidays are business
    meaning and would need a definition, so they belong in the model, not in a generator.
    """
    return (
        f"{_GENERATED}\n"
        f"CREATE OR REPLACE TABLE {CALENDAR.sql} AS\n"
        f"WITH bounds AS (\n"
        f"SELECT\n"
        f"    min(b._event_date) AS first_date,\n"
        f"    max(b._event_date) AS last_date\n"
        f"FROM {BRIDGE.sql} AS b\n"
        f"),\n\n"
        f"every_day AS (\n"
        f"SELECT\n"
        f"    cast(d.day AS DATE) AS date_key\n"
        f"FROM bounds AS bo\n"
        f"CROSS JOIN range(\n"
        f"    bo.first_date, bo.last_date + INTERVAL 1 DAY, INTERVAL 1 DAY\n"
        f") AS d (day)\n"
        f")\n\n"
        f"SELECT\n"
        f"    d.date_key AS date_key,\n"
        f"    cast(year(d.date_key) AS INTEGER) AS year_number,\n"
        f"    cast(quarter(d.date_key) AS INTEGER) AS quarter_of_year,\n"
        f"    cast(month(d.date_key) AS INTEGER) AS month_of_year,\n"
        f"    cast(day(d.date_key) AS INTEGER) AS day_of_month,\n"
        f"    cast(date_trunc('year', d.date_key) AS DATE) AS year_start,\n"
        f"    cast(date_trunc('quarter', d.date_key) AS DATE) AS quarter_start,\n"
        f"    cast(date_trunc('month', d.date_key) AS DATE) AS month_start,\n"
        f"    strftime(d.date_key, '%Y') || '-Q' || cast(quarter(d.date_key) AS VARCHAR) "
        f"AS quarter_label,\n"
        f"    strftime(d.date_key, '%Y-%m') AS month_label\n"
        f"FROM every_day AS d;\n"
    )


def definitions(model: Model, uss: Uss) -> dict[str, str]:
    """Every definition, by the token that refers to it. Copied verbatim, never composed.

    A generator that composed a definition would be a third place the data is explained,
    and the worst kind: one nobody wrote and nobody reviews.
    """
    found = dict(model.definitions())
    for event in uss.events:
        found[f"{event.entity_id}.events.{event.id}"] = event.definition
        for measure in event.measures:
            found[f"{event.entity_id}.measures.{measure.id}"] = measure.definition
    return found
