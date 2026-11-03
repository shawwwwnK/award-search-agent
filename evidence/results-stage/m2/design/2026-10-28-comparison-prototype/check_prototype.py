"""Run deterministic, offline controls for the comparison-clause prototype.

Run from this directory with the project .venv Python, or invoke by absolute path.
Only the adjacent audited source-facts.json is read; no model/provider access.
"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

from prototype_clauses import ClauseError, render_clause


HERE = Path(__file__).resolve().parent


def _spec(clause_id: str, left: str, right: str, metric: str, relation: str) -> dict:
    return {
        "id": clause_id, "left_ref": left, "right_ref": right,
        "metric": metric, "relation": relation,
        "scope": "schedule" if metric in {"arrival", "departure", "elapsed"} else "reported_quote",
    }


def _control(name: str, spec: dict, records: dict, visible: list[str], should_pass: bool) -> dict:
    try:
        result = render_clause(spec, records, visible)
    except ClauseError as exc:
        outcome, detail = "rejected", str(exc)
    else:
        outcome, detail = "rendered", result["text"]
    expected = "rendered" if should_pass else "rejected"
    assert outcome == expected, f"{name}: expected {expected}, got {outcome}: {detail}"
    return {"name": name, "input_kind": "synthetic_control", "expected": expected,
            "actual": outcome, "detail": detail}


def synthetic_controls() -> list[dict]:
    base = {
        "x": {"id": "x", "label": "Alaska January 1", "role": "journey",
              "program": "Alaska", "points": "0", "native_fee": "0.00",
              "fee_currency": "USD", "price_scope": "unknown",
              "arrival": "2026-01-01T12:00:00-08:00", "departure": "2026-01-01T08:00:00-08:00",
              "elapsed_minutes": 240},
        "y": {"id": "y", "label": "Alaska January 12", "role": "journey",
              "program": "Alaska", "points": "7500", "native_fee": "50.90",
              "fee_currency": "USD", "price_scope": "unknown",
              "arrival": "2026-01-01T13:00:00-08:00", "departure": "2026-01-01T07:00:00-08:00",
              "elapsed_minutes": 360},
    }
    controls: list[dict] = []

    def run(name: str, spec: dict, *, change: tuple[str, str, object] | None = None,
            visible: list[str] | None = None, pass_expected: bool = False) -> None:
        records = deepcopy(base)
        if change:
            ref, field, value = change
            records[ref][field] = value
        controls.append(_control(name, spec, records, ["x", "y"] if visible is None else visible,
                                 pass_expected))

    run("zero_quote_is_valid", _spec("zero", "x", "y", "points", "fewer"), pass_expected=True)
    run("zero_fee_is_valid", _spec("zero_fee", "x", "y", "native_fee", "lower"), pass_expected=True)
    run("correct_arrival_direction", _spec("arrive", "x", "y", "arrival", "earlier"), pass_expected=True)
    run("wrong_arrival_direction", _spec("bad", "x", "y", "arrival", "later"))
    run("swapped_endpoints_unchanged_relation", _spec("swap", "y", "x", "arrival", "earlier"))
    run("wrong_expected_currency", {**_spec("currency", "x", "y", "native_fee", "lower"),
                                    "expected_currency": "CAD"})
    run("different_points_program", _spec("program", "x", "y", "points", "fewer"),
        change=("y", "program", "United"))
    run("different_fee_currency", _spec("currency", "x", "y", "native_fee", "lower"),
        change=("y", "fee_currency", "CAD"))
    run("fee_claimed_total", {**_spec("total", "x", "y", "native_fee", "lower"), "scope": "total_trip"})
    run("fee_claimed_per_person", {**_spec("person", "x", "y", "native_fee", "lower"), "scope": "per_person"})
    run("hidden_reference", _spec("hidden", "x", "y", "arrival", "earlier"), visible=["x"])
    run("unknown_reference", _spec("missing", "x", "z", "arrival", "earlier"))
    run("date_only_clock", _spec("date", "x", "y", "arrival", "earlier"),
        change=("x", "arrival", "2026-01-01"))
    run("unknown_metric_field", _spec("field", "x", "y", "seats", "fewer"))
    run("missing_value", _spec("missingval", "x", "y", "points", "fewer"),
        change=("x", "points", None))
    run("nonfinite_amount", _spec("nan", "x", "y", "points", "fewer"),
        change=("x", "points", "NaN"))
    run("boolean_elapsed", _spec("bool", "x", "y", "elapsed", "shorter"),
        change=("x", "elapsed_minutes", True))
    run("negative_elapsed", _spec("negative", "x", "y", "elapsed", "shorter"),
        change=("x", "elapsed_minutes", -1))
    run("negative_amount", _spec("negativeamount", "x", "y", "native_fee", "lower"),
        change=("x", "native_fee", "-1"))
    run("award_fee_vs_cash_fare", _spec("crossrole", "x", "y", "native_fee", "lower"),
        change=("y", "role", "benchmark"))
    return controls


def build_clauses(facts: dict) -> dict[str, list[dict]]:
    """Build the nine audited example specs; every ID comes from source-facts.json."""
    records = facts["records"]

    def one(case: str, **fields: object) -> str:
        matches = [ref for ref in facts["cases"][case]["records"]
                   if all(records[ref].get(field) == value for field, value in fields.items())]
        assert len(matches) == 1, f"expected one {case} record matching {fields}; got {len(matches)}"
        return matches[0]

    hkg = one("A", role="journey", route="SFO–HKG–BKK")
    early_tpe = one("A", role="journey", route="SFO–TPE–BKK",
                    departure="2027-01-15T12:00:00-08:00")
    late_tpe = one("A", role="journey", route="SFO–TPE–BKK",
                   departure="2027-01-15T23:30:00-08:00")
    united = one("B", role="lead", program="united")
    alaska_jan1 = one("B", role="lead", program="alaska", departure_date="2027-01-01")
    alaska_jan12 = one("B", role="lead", program="alaska", departure_date="2027-01-12")
    alaska_jan7 = one("D", role="lead", program="alaska", departure_date="2027-01-07")
    assert alaska_jan1 in facts["cases"]["D"]["records"]
    return {
        "A": [
            _spec("A_arrival_early_vs_hkg", early_tpe, hkg, "arrival", "earlier"),
            _spec("A_elapsed_hkg_vs_early", hkg, early_tpe, "elapsed", "shorter"),
            _spec("A_arrival_hkg_vs_late", hkg, late_tpe, "arrival", "earlier"),
            {**_spec("A_fee_hkg_vs_taipei", hkg, early_tpe, "native_fee", "lower"),
             "expected_currency": "CAD"},
        ],
        "B": [
            _spec("B_points_premium_vs_economy", alaska_jan12, alaska_jan1, "points", "more"),
            {**_spec("B_fees_alaska_equal", alaska_jan12, alaska_jan1, "native_fee", "equal"),
             "expected_currency": "USD"},
            {**_spec("B_fee_united_vs_alaska", united, alaska_jan1, "native_fee", "lower"),
             "expected_currency": "USD"},
        ],
        "C": [],
        "D": [
            _spec("D_points_jan7_vs_jan1", alaska_jan7, alaska_jan1, "points", "more"),
            {**_spec("D_fees_equal", alaska_jan7, alaska_jan1, "native_fee", "equal"),
             "expected_currency": "USD"},
        ],
    }


def main() -> None:
    facts = json.loads((HERE / "source-facts.json").read_text())
    specs_by_case = build_clauses(facts)
    rendered = {}
    for case, specs in specs_by_case.items():
        visible = facts["cases"][case]["records"]
        rendered[case] = [render_clause(spec, facts["records"], visible) for spec in specs]
    controls = synthetic_controls()
    # Natural saved records exercise two important cross-unit limits. Case C has
    # no permissible cross-program point or cross-currency fee comparison.
    c_refs = facts["cases"]["C"]["records"]
    c_awards = [ref for ref in c_refs if facts["records"][ref]["role"] == "lead"]
    assert len(c_awards) == 2
    controls.append({**_control("C_cross_program_points",
                                 _spec("c_points", *c_awards, "points", "more"),
                                 facts["records"], c_refs, False), "input_kind": "saved_source_control"})
    controls.append({**_control("C_cross_currency_fee",
                                 _spec("c_fee", *c_awards, "native_fee", "higher"),
                                 facts["records"], c_refs, False), "input_kind": "saved_source_control"})
    expected_deltas = {
        "A_arrival_early_vs_hkg": "550", "A_elapsed_hkg_vs_early": "125",
        "A_arrival_hkg_vs_late": "375", "A_fee_hkg_vs_taipei": "9.10",
        "B_points_premium_vs_economy": "97500", "B_fees_alaska_equal": "0.00",
        "B_fee_united_vs_alaska": "22.70", "D_points_jan7_vs_jan1": "7500",
        "D_fees_equal": "0.00",
    }
    for clauses in rendered.values():
        for clause in clauses:
            assert clause["delta"]["value"] == expected_deltas[clause["clause_id"]], clause
    assert sum(map(len, rendered.values())) == len(expected_deltas)
    by_id = {clause["clause_id"]: clause for clauses in rendered.values() for clause in clauses}
    # These are deliberate free-text defects. The renderer sees only the named
    # clauses; it neither parses nor validates the surrounding answer.
    expected_limitations = [
        {"case": "correct_clause_plus_contradictory_opening",
         "free_text": "Hong Kong is the earliest arriving award journey.",
         "bound_clause_ids": ["A_arrival_early_vs_hkg"],
         "whole_answer_result": "Opening contradicts the valid bound clause; manual semantic review required."},
        {"case": "two_valid_clauses_plus_misleading_but_or_switched_endpoints",
         "free_text": "The January 12 Alaska lead costs more points but has the lower award fee.",
         "bound_clause_ids": ["B_points_premium_vs_economy", "B_fee_united_vs_alaska"],
         "whole_answer_result": "The fee clause is about United versus Alaska, not January 12 versus January 1 Alaska; manual semantic review required."},
        {"case": "higher_quote_plus_unestablished_schedule_benefit",
         "free_text": "The January 7 Alaska lead has a faster schedule, making its extra points worthwhile.",
         "bound_clause_ids": ["D_points_jan7_vs_jan1", "D_fees_equal"],
         "whole_answer_result": "Both leads are date-only; no schedule benefit is established. Manual semantic review required."},
        {"case": "lower_quote_with_conditional_date_alternative",
         "free_text": "The January 1 Alaska lead uses fewer points at the same reported fee; January 7 remains a date choice only if that departure suits you.",
         "bound_clause_ids": ["D_points_jan7_vs_jan1", "D_fees_equal"],
         "whole_answer_result": "Mechanics pass; whether this is decision-rich enough is an unsettled manual usefulness judgment."},
    ]
    for example in expected_limitations:
        assert all(clause_id in by_id for clause_id in example["bound_clause_ids"])
        example["mechanical_result"] = "all named clauses rendered; free text was not checked"
    (HERE / "clauses.json").write_text(json.dumps(rendered, indent=2) + "\n")
    report = {
        "kind": "offline_clause_mechanics_only",
        "source": "audited_saved_facts_plus_seeded_synthetic_controls",
        "positive_clause_count": sum(map(len, rendered.values())),
        "synthetic_control_count": sum(c["input_kind"] == "synthetic_control" for c in controls),
        "saved_source_control_count": sum(c["input_kind"] == "saved_source_control" for c in controls),
        "controls": controls,
        "expected_limitations": expected_limitations,
        "evidence_limit": "Local functional controls only; no LLM, latency, whole-answer correctness, or quality proof.",
    }
    (HERE / "offline-checks.json").write_text(json.dumps(report, indent=2) + "\n")
    print(f"rendered {report['positive_clause_count']} source clauses; "
          f"{report['synthetic_control_count']} synthetic and "
          f"{report['saved_source_control_count']} saved-source controls passed")


if __name__ == "__main__":
    main()
