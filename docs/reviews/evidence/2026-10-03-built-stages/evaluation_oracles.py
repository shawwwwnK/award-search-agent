"""Offline seeded evaluator faults; run from repository root.

Faults are synthetic or seeded and make no normal-runtime failure claim. The
probe uses local files, in-memory mutations, and temporary directories only;
it makes no network, model, provider, or credential calls. JSON is written to
stdout so the caller can capture a durable evidence copy.
"""
from pathlib import Path
import copy
import importlib.util
import json
import tempfile

from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.ranking.style_contracts import CurrencyConversionSnapshot, RankingStylePolicy, RankedJourneySet
from award_agent.ranking import styles
from award_agent.evaluation.search_planning import preflight_search_planning_golden_corpus, run_search_planning_golden_eval

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

corpus = load("ranking_corpus", "scripts/ranking_style_corpus.py")
provider = load("provider_corpus", "scripts/provider_plan_corpus.py")
fx = CurrencyConversionSnapshot.model_validate_json(Path("data/ranking/m2/fx-2026-09-29.json").read_bytes())
policy = RankingStylePolicy()
results = {}

# Simulate a producer regression that drops its two unknown requirement reasons.
raw = json.loads(Path("evidence/ranking-stage/m1/sfo_to_bkk_positioning.json").read_text())
original = copy.deepcopy(raw)
journey = next(j for j in raw["journeys"] if j["status"] == "conditional")
removed = [r["code"] for r in journey["reasons"] if r["state"] == "unknown" and r["dimension"] in {"requirement", "evidence"}]
journey["reasons"] = [r for r in journey["reasons"] if not (r["state"] == "unknown" and r["dimension"] in {"requirement", "evidence"})]
journey["status"] = "admitted"
raw["accounting"]["conditional"] -= 1
raw["accounting"]["admitted"] += 1
matched = MatchedJourneySet.model_validate(raw)
ranked = styles.assign_journey_styles(matched, policy=policy, fx_snapshot=fx)
corpus._assert_case_integrity(matched, raw, ranked)
results["missing_m1_reasons"] = {
    "candidate_id": journey["candidate_id"], "removed_reasons": removed,
    "source_provider_unchanged": raw["provider_result"] == original["provider_result"],
    "source_plan_unchanged": raw["plan"] == original["plan"],
    "matched_schema_accepts": True, "ranking_assignment_accepts": True,
    "independent_corpus_integrity_accepts": True,
    "before": "conditional", "after": next(f.status for f in ranked.features if f.candidate_id == journey["candidate_id"]),
}

# Simulate omission of assessment-level cost validation needs in production derivation.
raw = original
matched = MatchedJourneySet.model_validate(raw)
baseline = styles.assign_journey_styles(matched, policy=policy, fx_snapshot=fx)
old_derive = styles._derive_style_data
def omit_cost_needs(*args, **kwargs):
    data = old_derive(*args, **kwargs)
    data["assessments"] = tuple(a.model_copy(update={"validation_needs": ()}) for a in data["assessments"])
    return data
styles._derive_style_data = omit_cost_needs
mutant = styles.assign_journey_styles(matched, policy=policy, fx_snapshot=fx)
RankedJourneySet.model_validate_json(mutant.model_dump_json())
corpus._assert_case_integrity(matched, raw, mutant)
tests = load("ranking_m2_corpus_tests", "tests/unit/test_ranking_m2_corpus.py")
for case in ("mixed_access", "exact_business", "sfo_to_bkk_positioning"):
    tests.test_saved_matching_corpus_retained_and_stably_styled(case)
results["missing_cost_needs"] = {
    "before_assessments_with_needs": sum(bool(a.validation_needs) for a in baseline.assessments),
    "after_assessments_with_needs": sum(bool(a.validation_needs) for a in mutant.assessments),
    "schema_roundtrip_accepts": True, "independent_corpus_integrity_accepts": True,
    "all_three_corpus_test_functions_pass": True,
    "frozen_bytes_would_detect_change": baseline.model_dump_json() != mutant.model_dump_json(),
    "cost_features_still_retain_missing_parts": baseline.features == mutant.features,
}
styles._derive_style_data = old_derive

with tempfile.TemporaryDirectory(prefix="eval-adversary-", dir="/private/tmp") as root:
    root = Path(root)
    book = json.loads(Path("evals/search_planning/cases_v2.json").read_text())
    book["cases"] = [book["cases"][0]]
    book["coverage_matrix"] = {key: [book["cases"][0]["case_id"]] for key in book["coverage_matrix"]}
    path = root / "mislabelled-planning-corpus.json"
    path.write_text(json.dumps(book))
    preflight_search_planning_golden_corpus(path)
    report = run_search_planning_golden_eval(path)
    results["vacuous_coverage_labels"] = {"preflight_accepts": True, "summary": report["summary"], "scenarios_present": [c["gateway_scenario"] for c in book["cases"]], "coverage_labels_claimed": list(book["coverage_matrix"])}
    empty = root / "empty-provider-corpus"
    empty.mkdir()
    (empty / "index.json").write_text(json.dumps({"schema_version": 1, "runs": []}))
    results["empty_provider_corpus"] = {"verification_accepts": True, "returned_counts": provider.verify(empty)}

print(json.dumps(results, indent=2))
