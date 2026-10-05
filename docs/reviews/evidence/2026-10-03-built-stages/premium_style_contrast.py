"""Synthetic offline premium-token contrast through M1 and M2.

The ProviderResultSet is locally seeded from a test fixture and only its
cabin token changes. This demonstrates behavior for synthetic inputs; it is
not a normal-runtime failure claim or live provider observation. No network,
model, provider, or credential calls are made. Run from repository root.
"""

from pathlib import Path
import importlib.util
from award_agent.providers.contracts import ProviderResultSet, RawField
from award_agent.ranking import assemble_matched_journeys, assign_journey_styles
from award_agent.ranking.style_contracts import RankingStylePolicy
spec=importlib.util.spec_from_file_location('review_m2_fixture',Path('tests/unit/test_ranking_m2.py'))
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
baseline, _=fixture._three_traveler_party_match()
for token in ['premium','premium_economy']:
    payload=baseline.provider_result.model_dump(mode='json')
    for obs in payload['observations']:
        obs['cabin']={'state':'value','value':token,'source_field':'Cabin'}
    result=ProviderResultSet.model_validate(payload)
    execution=result.execution_plan
    matched=assemble_matched_journeys(baseline.plan,result,
        current_session_id=baseline.current_session_id,current_revision=baseline.current_revision,
        current_effective_request=baseline.request,
        expected_compilation_binding_digest=baseline.compilation_binding_digest,
        policy=execution.policy,award_capability=execution.award_capability,
        cash_capability=execution.cash_capability)
    ranked=assign_journey_styles(matched,policy=RankingStylePolicy(),fx_snapshot=fixture._snapshot())
    print(token, 'admitted',matched.accounting.admitted,'comparison_pool',len(ranked.comparison_pool_ids),
          'premium_economy_addons',len(ranked.indexes.premium_economy_addons))
