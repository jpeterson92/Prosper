"""Polars-specific matching regressions; financial expectations stay in domain tests."""

import runpy
from collections.abc import Callable
from pathlib import Path
from typing import cast

import pytest

from prosper import benchmark_reconciliation as r
from prosper import benchmark_tables as t
from prosper import equity_benchmark as e
from prosper import vanguard as v


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


@pytest.mark.parametrize("field", ["RUNTIME_VERSION", "IMPLEMENTATION_SHA256"])
def test_matching_runtime_and_implementation_are_bound_without_changing_canonical_facts(
    monkeypatch: pytest.MonkeyPatch, field: str
) -> None:
    root = Path(__file__).resolve().parents[1]
    original_scenario = cast(
        Callable[..., tuple[v.Acquisition, r.Stipulation, r.PortfolioContext]],
        runpy.run_path(str(root / "scripts/qualify_benchmark_reconciliation.py"))["scenario"],
    )
    equity_scenario = cast(
        Callable[..., tuple[v.Acquisition, r.Stipulation, e.Policy, r.PortfolioContext]],
        runpy.run_path(str(root / "scripts/qualify_equity_benchmark.py"))["scenario"],
    )
    acq, stip, portfolio = original_scenario(
        (root / "examples/synthetic/benchmark/full-response.json").read_bytes()
    )
    old_full = r.reconcile(acq, stip)
    other, rules, policy, context = equity_scenario()
    old_equity = e.select(other, rules, policy)
    monkeypatch.setattr(t, field, "changed-qualified-runtime-or-code")
    new_full, new_equity = r.reconcile(acq, stip), e.select(other, rules, policy)
    assert new_full.input_sha256 == old_full.input_sha256
    assert new_equity.input_sha256 == old_equity.input_sha256
    assert new_full.canonical_sha256 == old_full.canonical_sha256
    assert new_equity.canonical_sha256 == old_equity.canonical_sha256
    assert new_full.identity_sha256 != old_full.identity_sha256
    assert new_equity.identity_sha256 != old_equity.identity_sha256
    with pytest.raises(r.ReconciliationUnavailable):
        r.bridge(old_full, portfolio)
    with pytest.raises(r.ReconciliationUnavailable):
        e.bridge(old_equity, context)
    assert r.bridge(new_full, portfolio).basket.weights is not None
    assert e.bridge(new_equity, context).basket.weights is not None
