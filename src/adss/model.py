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
class Model:
    path: Path
    entities: tuple[Entity, ...]

    def entity(self, entity_id: str) -> Entity:
        for entity in self.entities:
            if entity.id == entity_id:
                return entity
        raise KeyError(f"{self.path} has no entity {entity_id!r}")

    def definitions(self) -> dict[str, str]:
        """Every definition, by the token that refers to it. Copied, never composed."""
        found: dict[str, str] = {}
        for entity in self.entities:
            found[entity.id] = entity.definition
            for attribute in entity.attributes:
                found[f"{entity.id}.{attribute.id}"] = attribute.definition
        return found


def read_model(path: Path) -> Model:
    document = yaml.safe_load(path.read_text())["model"]
    entities = tuple(
        Entity(
            id=str(entity["id"]),
            definition=str(entity["definition"]),
            attributes=tuple(
                Attribute(
                    id=str(attribute["id"]),
                    type=AttributeType(str(attribute["type"])),
                    definition=str(attribute["definition"]),
                )
                for attribute in entity["attributes"]
            ),
        )
        for entity in document["entities"]
    )
    return Model(path=path, entities=entities)
