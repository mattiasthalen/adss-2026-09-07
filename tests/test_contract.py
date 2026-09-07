"""A contract is documentation, schema and transformation in one artefact. ADR 0003."""

from pathlib import Path

import pytest

from adss.contract import ColumnType, ContractError, read_contract

FIXTURES = Path(__file__).parent / "fixtures" / "contracts"


def parent_contract():
    return read_contract(FIXTURES / "parent.yaml")


def test_the_file_stem_is_the_landed_table_name():
    assert parent_contract().table == "parent"


def test_every_declared_column_is_read_in_order():
    contract = parent_contract()
    assert len(contract.columns) == 9
    assert contract.columns[0].source_path == "ParentId"
    assert contract.columns[0].target_name == "parent_id"
    assert contract.columns[0].required is True
    assert contract.columns[1].required is False


def test_the_whole_type_vocabulary_is_exercised_by_the_fixture():
    declared = {column.type.name for column in parent_contract().columns}
    assert declared == set(ColumnType.__members__), (
        "every type in the vocabulary must appear in the neutral fixture, or its emitted "
        "expression is never tested"
    )


def test_a_primary_key_naming_no_declared_column_is_refused():
    with pytest.raises(ContractError, match="dangling"):
        read_contract(FIXTURES / "bad_dangling_key.yaml")


def test_a_target_name_that_is_not_the_snake_case_of_its_source_path_is_refused():
    with pytest.raises(ContractError, match="mechanical"):
        read_contract(FIXTURES / "bad_renamed_column.yaml")


def test_a_key_that_could_carry_business_logic_is_refused():
    with pytest.raises(ContractError, match="business logic"):
        read_contract(FIXTURES / "bad_expression_key.yaml")
