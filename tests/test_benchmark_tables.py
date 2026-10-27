"""Polars-specific matching regressions; financial expectations stay in domain tests."""

import pytest

from prosper import benchmark_tables as t


def test_empty_and_all_missing_bindings_have_explicit_schema_and_source_order() -> None:
    empty = t.bind((), (), (), ())
    assert empty == t.Bindings((), (), (), (), (), (), ())
    result = t.bind(("last", "first", "empty"), (("last", 0), ("first", 0)), (), ())
    assert result.sections == result.values == (None, None, None)
    assert result.rows == result.decisions == (None, None)
    assert result.extra_sections == result.extra_rows == result.extra_values == ()


def test_shuffled_join_rules_full_locator_and_extra_rule_order_are_explicit() -> None:
    result = t.bind(
        ("b", "a", "empty"),
        (("b", 1), ("a", 1), ("b", 0)),
        ("extra-z", "a", "b", "extra-a"),
        (("b", 0), ("extra", 3), ("a", 1), ("b", 1)),
        ("empty", "b", "ghost"),
        (("a", 1), ("b", 0)),
    )
    assert result.sections == (2, 1, None)
    assert result.rows == (3, 2, 0)
    assert result.decisions == (None, 0, 1)
    assert result.values == (1, None, 0)
    assert result.extra_sections == (0, 3) and result.extra_rows == (1,)
    assert result.extra_values == (2,)


@pytest.mark.parametrize(
    "kind",
    ["source-section", "rule-section", "source-row", "rule-row", "value", "decision", "target"],
)
def test_duplicate_keys_are_refused_before_join_multiplication(kind: str) -> None:
    with pytest.raises(ValueError, match="unique"):
        if kind == "source-section":
            t.bind(("a", "a"), (), (), ())
        elif kind == "rule-section":
            t.bind(("a",), (), ("a", "a"), ())
        elif kind == "source-row":
            t.bind(("a",), (("a", 0), ("a", 0)), (), ())
        elif kind == "rule-row":
            t.bind(("a",), (("a", 0),), (), (("a", 0), ("a", 0)))
        elif kind == "value":
            t.bind(("a",), (), (), (), ("a", "a"))
        elif kind == "decision":
            t.bind(("a",), (), (), (), (), (("a", 0), ("a", 0)))
        else:
            t.link(("a",), (), (("p", 0, True), ("p", 0, True)))


def test_nullable_targets_first_valid_occurrence_and_per_section_coverage() -> None:
    result = t.link(
        ("alt", "other", "empty"),
        (
            ("alt", None, None, True),
            ("alt", "p", 1, True),
            ("alt", "p", 0, False),
            ("alt", "p", 0, True),
            ("alt", "p", 0, True),
            ("other", "p", 0, True),
        ),
        (("p", 0, True), ("p", 1, False)),
    )
    assert result.targets == (None, None, None, 0, 0, 0)
    assert result.duplicates == (False, False, False, False, True, False)
    assert result.complete_sections == ()  # Invalid primary never becomes covered.
    complete = t.link(("alt", "empty"), (("alt", "p", 0, True),), (("p", 0, True),))
    assert complete.complete_sections == ("alt",)
    assert t.link(("a", "b"), (), ()).complete_sections == ("a", "b")


def test_large_unmatched_locator_is_preserved_without_machine_integer_overflow() -> None:
    index = 10**100
    result = t.bind(("a",), (("a", 0),), ("a",), (("a", index),))
    assert result.rows == (None,) and result.extra_rows == (0,)
    assert t.unmatched((("a", index), ("a", 0)), (("a", 0),)) == (0,)
    assert t.link(("alt",), (("alt", "a", index, True),), (("a", 0, True),)).targets == (None,)


def test_identity_duplicate_diagnostics_and_selection_partition_do_not_coerce_nulls() -> None:
    assert not t.duplicate_ids(()) and not t.duplicate_ids(("a", None))
    assert t.duplicate_ids(("a", "a"))
    assert t.duplicate_ids((None, None))  # Existing blocked identity diagnostic, no join.
    assert t.included_ordinals(
        ("excluded", "included-equity", "unresolved", "included-equity")
    ) == (1, 3)
