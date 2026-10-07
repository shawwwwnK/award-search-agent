from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import Literal

from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import (
    CheckFinding,
    DeclaredClaim,
    PreparedResultsInput,
    ResultsArtifact,
    ResultsConfig,
    ResultsDocument,
    ResultsPart,
    ResultsSelection,
    prepare_results,
    replay_results,
    run_results,
)

ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = ROOT / 'evidence/results-stage/m2'
RANKING = ROOT / 'evidence/ranking-stage/m2/solutions'
CONFIG_PATH = EVIDENCE_DIR / 'offline-config.json'
CASES = ('mixed_access', 'exact_business', 'sfo_to_bkk_positioning')
CANDIDATE = 'f7d024bb65a87fe25bd14e71dbbf51c35f0a1995e3e9cc22fa112e677ed7eab9'


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def dump_json(path: Path, payload: object) -> bytes:
    data = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode('utf-8')
    path.write_bytes(data)
    return data


def load_projection(path: Path) -> SolutionProjection:
    return SolutionProjection.model_validate_json(path.read_text(encoding='utf-8'))


def slot_rows(scope: str, values: dict[str, str]) -> str:
    rows = [f'| {key.replace("_", " ").capitalize()} | {{{{fact:{key}}}}} |' for key in sorted(values)]
    return f'### {scope.capitalize()} source facts\n\n| Field | Source-bound value |\n| --- | --- |\n' + '\n'.join(rows)


def clean_document(prepared: PreparedResultsInput) -> ResultsDocument:
    journey_id = CANDIDATE
    shared = prepared.slots['shared']
    journey = prepared.slots[f'journey:{journey_id}']
    return ResultsDocument(
        selection=ResultsSelection(journey_ids=(journey_id,)),
        parts=(
            ResultsPart(scope='shared', markdown='## Search context\n\n' + slot_rows('shared', shared)),
            ResultsPart(scope='journey', reference_id=journey_id,
                        markdown='## Selected journey\n\n' + slot_rows('journey', journey)),
        ),
    )


def claim_doc(prepared: PreparedResultsInput, *, correction: bool) -> ResultsDocument:
    journey_id = CANDIDATE
    journey = prepared.slots[f'journey:{journey_id}']
    claims = [DeclaredClaim(
        claim_id='protected-connection', kind='connection_protection',
        proposition='protected_connection', scope_ids=(journey_id,),
        text='This connection is protected.',
    )]
    prose = 'This connection is protected.'
    if correction:
        claims.append(DeclaredClaim(
            claim_id='journey-business', kind='cabin', proposition='journey_business',
            scope_ids=(journey_id,), text='This journey is in business class.',
        ))
        prose += '\n\nThis journey is in business class.'
    return ResultsDocument(
        selection=ResultsSelection(journey_ids=(journey_id,)),
        parts=(
            ResultsPart(scope='shared', markdown='## Search context\n\n' + slot_rows('shared', prepared.slots['shared'])),
            ResultsPart(scope='journey', reference_id=journey_id,
                        markdown='## Selected journey\n\n' + prose + '\n\n' + slot_rows('journey', journey),
                        claims=tuple(claims)),
        ),
    )


class FixtureWriter:
    def __init__(self, mode: Literal['clean', 'annotated']) -> None:
        self.mode = mode
        self.calls = 0

    def author(
        self,
        prepared: PreparedResultsInput,
        config: ResultsConfig,
        feedback: tuple[CheckFinding, ...] = (),
        previous_document: ResultsDocument | None = None,
    ) -> ResultsDocument:
        del config, feedback, previous_document
        self.calls += 1
        if self.mode == 'clean':
            return clean_document(prepared)
        return claim_doc(prepared, correction=self.calls > 1)


def save_artifact(out: Path, name: str, artifact: ResultsArtifact) -> dict[str, object]:
    json_path = out / f'{name}.artifact.json'
    raw = artifact.model_dump_json(indent=2).encode('utf-8') + b'\n'
    json_path.write_bytes(raw)
    validated = ResultsArtifact.model_validate_json(raw)
    replayed = replay_results(validated)
    replay_path = out / f'{name}.md'
    replay_path.write_bytes(replayed.encode('utf-8'))
    if replay_path.read_bytes() != artifact.rendered_markdown.encode('utf-8'):
        raise AssertionError(f'{name}: replay output differs byte-for-byte')
    selected_slots = artifact.prepared.slots[f'journey:{CANDIDATE}']
    shared_slots = artifact.prepared.slots['shared']
    expected_facts = ({('shared', None, key) for key in shared_slots} |
                      {('journey', CANDIDATE, key) for key in selected_slots})
    rendered_facts = {(fact.scope, fact.reference_id, fact.key) for fact in artifact.inserted_facts}
    if rendered_facts != expected_facts:
        raise AssertionError(f'{name}: fixture did not render every prepared shared and journey slot')
    return {
        'artifact_file': json_path.name,
        'artifact_sha256': sha256(raw),
        'artifact_bytes': len(raw),
        'replay_file': replay_path.name,
        'replay_sha256': sha256(replay_path.read_bytes()),
        'replay_bytes': len(replay_path.read_bytes()),
        'validation_outcome': artifact.validation_outcome,
        'generation_outcome': artifact.generation_outcome,
        'delivery_outcome': artifact.delivery_outcome,
        'selected_attempt': artifact.selected_attempt,
        'selection_reason': artifact.selection_reason,
        'attempts': [
            {
                'phase': item.phase,
                'outcome': item.outcome,
                'finding_count': len(item.findings),
                'failed_findings': sum(f.outcome == 'failed' for f in item.findings),
                'input_bytes': item.input_bytes,
                'estimated_total_tokens': item.estimated_total_tokens,
                'prompt_digest': item.prompt_digest,
                'schema_digest': item.schema_digest,
            }
            for item in artifact.attempts
        ],
        'notice_count': len(artifact.notices),
        'inserted_fact_count': len(artifact.inserted_facts),
        'complete_prepared_slot_coverage': True,
        'prepared_shared_slot_count': len(shared_slots),
        'prepared_selected_journey_slot_count': len(selected_slots),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description='Regenerate offline Results M2 evidence.')
    parser.add_argument('--output-dir', type=Path, default=EVIDENCE_DIR,
                        help='directory for generated artifacts (default: evidence/results-stage/m2)')
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if out != EVIDENCE_DIR.resolve():
        shutil.copyfile(CONFIG_PATH, out / CONFIG_PATH.name)
    config_path = out / CONFIG_PATH.name
    config_data = json.loads(config_path.read_text(encoding='utf-8'))
    config = ResultsConfig.model_validate(config_data)
    measurements: dict[str, dict[str, object]] = {}
    projections: dict[str, SolutionProjection] = {}
    for case in CASES:
        path = RANKING / f'{case}.json'
        projection = load_projection(path)
        projections[case] = projection
        prepared = prepare_results(projection, config)
        view = projection.view
        measurements[case] = {
            'source_file': f'../../ranking-stage/m2/solutions/{case}.json',
            'source_sha256': sha256(path.read_bytes()),
            'projection_view_digest': projection.receipt.view_digest,
            'prepared_source_digest': prepared.source_digest,
            'alternatives': len(view.alternatives),
            'eligible_alternatives': sum(a.status in {'admitted', 'conditional'} for a in view.alternatives),
            'components': len(view.components),
            'prepared_slot_scopes': len(prepared.slots),
            'prepared_slot_values': sum(len(v) for v in prepared.slots.values()),
            'input_bytes': prepared.input_bytes,
            'estimated_input_tokens': prepared.estimated_input_tokens,
            'max_output_tokens': config.max_output_tokens,
            'estimated_total_tokens': prepared.estimated_total_tokens,
            'context_limit_tokens': config.context_limit_tokens,
            'token_measurement': 'conservative_utf8_upper_bound',
            'protocol_overhead_tokens': config.prompt_overhead_tokens,
            'within_configured_conservative_bound': prepared.estimated_total_tokens <= config.context_limit_tokens,
            'qualification': 'Offline measurement only; the configured bound does not establish model-specific tokenization or practical context fit.',
        }
        dump_json(out / f'{case}.measurement.json', measurements[case])

    positioning = projections['sfo_to_bkk_positioning']
    candidate = next((a for a in positioning.view.alternatives if a.candidate_id == CANDIDATE), None)
    if candidate is None or candidate.status not in {'admitted', 'conditional'}:
        raise AssertionError('requested fixture candidate is absent or ineligible')
    if candidate.award_cabin.state != 'value' or 'business' in str(candidate.award_cabin.value).lower():
        raise AssertionError('requested fixture candidate no longer has non-business cabin evidence')

    prepared = prepare_results(positioning, config)
    clean_writer = FixtureWriter('clean')
    clean_artifact = run_results(positioning, config, clean_writer)
    if clean_writer.calls != 1 or clean_artifact.validation_outcome != 'clean':
        raise AssertionError('clean fixture controls did not produce one clean attempt')
    clean_meta = save_artifact(out, 'sfo_to_bkk_positioning.clean', clean_artifact)

    annotated_writer = FixtureWriter('annotated')
    annotated_artifact = run_results(positioning, config, annotated_writer)
    if annotated_writer.calls != 2 or annotated_artifact.validation_outcome != 'annotated':
        raise AssertionError('annotated fixture did not exercise initial plus correction')
    if annotated_artifact.selected_attempt != 0 or annotated_artifact.selection_reason != 'initial_fewer_failures':
        raise AssertionError('worse correction did not preserve the initial draft')
    if [sum(f.outcome == 'failed' for f in a.findings) for a in annotated_artifact.attempts] != [1, 2]:
        raise AssertionError('fixture failed-claim counts changed from expected 1 then 2')
    annotated_meta = save_artifact(out, 'sfo_to_bkk_positioning.annotated', annotated_artifact)
    for attempt in annotated_artifact.attempts:
        if attempt.document is None:
            raise AssertionError(f'{attempt.phase} fixture attempt has no recoverable document')
        draft_path = out / f'sfo_to_bkk_positioning.annotated.{attempt.phase}.draft.json'
        draft_path.write_bytes((attempt.document.model_dump_json(indent=2) + '\n').encode('utf-8'))

    measurement_all = {
        'evidence_kind': 'offline_preparation_measurements',
        'generated_by': 'prepare_results public API',
        'config_file': CONFIG_PATH.name,
        'config_sha256': sha256(config_path.read_bytes()),
        'cases': measurements,
    }
    dump_json(out / 'measurements.index.json', measurement_all)
    index = {
        'evidence_kind': 'offline_results_m2_fixtures_and_measurements',
        'generated_by': 'public Results API with deterministic fixture writer; zero live calls',
        'generated_at': '2026-10-07',
        'offline_config_file': CONFIG_PATH.name,
        'offline_config_sha256': sha256(config_path.read_bytes()),
        'source_files': [
            {'file': f'../../ranking-stage/m2/solutions/{case}.json',
             'sha256': measurements[case]['source_sha256'],
             'alternatives': measurements[case]['alternatives'],
             'eligible_alternatives': measurements[case]['eligible_alternatives'],
             'input_bytes': measurements[case]['input_bytes'],
             'estimated_total_tokens': measurements[case]['estimated_total_tokens']}
            for case in CASES
        ],
        'fixture_candidate_id': CANDIDATE,
        'fixture_writer_calls': {'clean': clean_writer.calls, 'annotated': annotated_writer.calls},
        'clean_fixture': clean_meta,
        'annotated_fixture': annotated_meta,
        'artifact_files': [
            {'file': 'sfo_to_bkk_positioning.annotated.initial.draft.json',
             'sha256': sha256((out / 'sfo_to_bkk_positioning.annotated.initial.draft.json').read_bytes())},
            {'file': 'sfo_to_bkk_positioning.annotated.correction.draft.json',
             'sha256': sha256((out / 'sfo_to_bkk_positioning.annotated.correction.draft.json').read_bytes())},
        ],
        'limitations': [
            'Fixtures are deterministic code-authored documents, not model-authored quality evidence.',
            'No semantic, M3, model-selection, live-budget, or practical-context-fit qualification.',
            'No live model, network, or travel-provider calls.',
        ],
    }
    dump_json(out / 'index.json', index)


if __name__ == '__main__':
    main()
