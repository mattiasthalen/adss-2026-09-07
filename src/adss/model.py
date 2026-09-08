"""A structural reading of the business model. It carries meaning; it never reads it.

The definitions in the model are the only explanation of the data there is. This module
moves them around -- into a glossary, into a check that a question's references resolve --
and never composes one, because a composed definition is a second explanation that nobody
wrote and nobody reviews.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

import yaml

from adss.names import refuse_unsafe, unsafe


class AttributeType(StrEnum):
    """The modelling language's whole type vocabulary. Semantic, not physical."""

    STRING = "STRING"
    NUMBER = "NUMBER"
    UNIT = "UNIT"
    START_TIMESTAMP = "START_TIMESTAMP"
    END_TIMESTAMP = "END_TIMESTAMP"


@dataclass(frozen=True, slots=True)
class Attribute:
    id: str
    type: AttributeType
    definition: str

    @property
    def column(self) -> str:
        """How this attribute is spelled in the generated layer."""
        return self.id.lower()

    @property
    def is_number(self) -> bool:
        return self.type is AttributeType.NUMBER

    @property
    def is_date(self) -> bool:
        return self.type in (AttributeType.START_TIMESTAMP, AttributeType.END_TIMESTAMP)


@dataclass(frozen=True, slots=True)
class Entity:
    id: str
    definition: str
    attributes: tuple[Attribute, ...]

    @property
    def object_name(self) -> str:
        """The generated layer's name for this entity: snake_case, singular."""
        return self.id.lower()

    @property
    def key_column(self) -> str:
        return f"{self.object_name}_key"

    @property
    def source_key(self) -> str:
        """What the modelling engine calls this entity's key, in its own casing."""
        return f"{self.id}_key"

    def attribute(self, attribute_id: str) -> Attribute:
        for attribute in self.attributes:
            if attribute.id == attribute_id:
                return attribute
        raise KeyError(f"{self.id} has no attribute {attribute_id!r}")


@dataclass(frozen=True, slots=True)
class Relationship:
    """A many-to-one edge, along which a key inherits and a measure does not.

    That it is many-to-one is not stated here, because the modelling language has nowhere to
    state it: `cardinality` is rejected and `type` is dropped on compile. It is inferred from
    the mapping's shape and pinned by a data check. ADR 0006.
    """

    name: str
    source_entity_id: str
    target_entity_id: str
    definition: str

    @property
    def id(self) -> str:
        """`<SRC>_<NAME>_<TGT>`, which is how every object the engine builds is named."""
        return f"{self.source_entity_id}_{self.name}_{self.target_entity_id}"


@dataclass(frozen=True, slots=True)
class Model:
    path: Path
    entities: tuple[Entity, ...]
    relationships: tuple[Relationship, ...] = ()

    def entity(self, entity_id: str) -> Entity:
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        raise KeyError(f"{self.path} has no entity {entity_id!r}")

    def edges_from(self, entity_id: str) -> tuple[Relationship, ...]:
        """The edges this entity inherits along, in model order."""
        return tuple(r for r in self.relationships if r.source_entity_id == entity_id)

    def definitions(self) -> dict[str, str]:
        """Every definition, by the token that refers to it. Copied, never composed."""
        found: dict[str, str] = {}
        for entity in self.entities:
            found[entity.id] = entity.definition
            for attribute in entity.attributes:
                found[f"{entity.id}.{attribute.id}"] = attribute.definition
        for relationship in self.relationships:
            found[relationship.id] = relationship.definition
        return found


class ModelError(Exception):
    """A model this system will not build from."""


def _named(kind: str, value: str) -> str:
    """Every id here reaches SQL as an identifier and a file name. names.py says which are safe."""
    if unsafe(value):
        raise ModelError(refuse_unsafe(kind, value))
    return value


def read_model(path: Path) -> Model:
    document = yaml.safe_load(path.read_text())["model"]
    entities = tuple(
        Entity(
            id=_named("entity", str(entity["id"])),
            definition=str(entity["definition"]),
            attributes=tuple(
                Attribute(
                    id=_named("attribute", str(attribute["id"])),
                    type=AttributeType(str(attribute["type"])),
                    definition=str(attribute["definition"]),
                )
                for attribute in entity["attributes"]
            ),
        )
        for entity in document["entities"]
    )
    relationships = tuple(
        Relationship(
            name=_named("relationship", str(declared["name"])),
            # The ends as well as the name. A relationship's id is composed from all three and
            # is spelled into generated SQL, so validating only the middle left the rule with a
            # hole -- it produced an unreadable KeyError rather than an injection, because an
            # entity id with metacharacters is refused where the entity itself is declared, but
            # a rule about ids should cover the ids.
            source_entity_id=_named("relationship source", str(declared["source_entity_id"])),
            target_entity_id=_named("relationship target", str(declared["target_entity_id"])),
            definition=str(declared["definition"]),
        )
        for declared in document.get("relationships", ())
    )
    return Model(path=path, entities=entities, relationships=relationships)
