import json,re
from pathlib import Path
from copy import deepcopy
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig,prepare_results
from award_agent.results.authoring import build_authoring_view
from award_agent.results.core import authoring_payload

ROOT=Path('/Users/shawnkang/bots/award-search'); BASE=ROOT/'evidence/end-to-end/presentation/iterations/006'
cfg=ResultsConfig.model_validate_json((BASE/'config.json').read_text())
art=json.loads((BASE/'admitted/artifact.json').read_text()); p=SolutionProjection.model_validate(art['projection']); source=art['prepared']['source']; original=prepare_results(p,cfg,version='results-artifact-v5').authoring_view
refs=original.references.model_dump(mode='json'); alias={**refs['awards'],**refs['cash']}
paired=next(g for g in original.view['components'] if len(g['members'])==2)
ids=[alias[m['ref']] for m in paired['members']]
obs=list(p.receipt.observation_sources); target=next(x for x in obs if x.observation_id==ids[1]); ev=target.evidence[0].model_copy(update={'sha256':'0'*64}); changed=target.model_copy(update={'evidence':(ev,*target.evidence[1:])}); changed_obs=tuple(changed if x.observation_id==ids[1] else x for x in obs)
p2=p.model_copy(update={'receipt':p.receipt.model_copy(update={'observation_sources':changed_obs})}); split=build_authoring_view(p2,source)
sg=[i for i,g in enumerate(split.view['components']) if any(alias[m['ref']] in ids for m in g['members'])]
assert len(set(sg))==2,(ids,sg)
# A missing local string must retain the known instant in the writer view.
base=p.view.alternatives[0]; assert base.departure.instant is not None
changed_time=base.departure.model_copy(update={'local_iso':None}); changed_alt=base.model_copy(update={'departure':changed_time}); changed_view=p.view.model_copy(update={'alternatives':(changed_alt,*p.view.alternatives[1:])}); changed_p=p.model_copy(update={'view':changed_view})
changed_source=deepcopy(source); changed_source['alternatives'][0]['departure']['local_iso']=None
missing_local=build_authoring_view(changed_p,changed_source)
first=next(g for g in missing_local.view['journeys'] if any(m['ref']=='J1' for m in g['members']))
assert first['facts']['departure']['instant']==base.departure.instant.isoformat().replace('+00:00','Z')
# Two same-schedule cash observations have different carrier and amount and must remain separate.
look=[x for x in p.view.components if x.kind=='cash_itinerary' and x.origin=='SFO' and x.destination=='LAX' and x.departure.local_iso=='2027-01-15T07:00:00-08:00' and x.arrival.local_iso=='2027-01-15T08:40:00-08:00']
assert len(look)==4,len(look)
lookids={x.observation_id for x in look}; groups=[g for g in original.view['components'] if any(refs['cash'].get(m['ref']) in lookids for m in g['members'])]
assert len(groups)==2,len(groups)
assert {g['facts']['cash_amount']['value'] for g in groups}=={135,176}
assert {tuple(g['facts']['carriers']) for g in groups}=={('United',),('American',)}
opaque=[]
for case in ('admitted','conditional','incomplete'):
    a=json.loads((BASE/case/'artifact.json').read_text()); cp=prepare_results(SolutionProjection.model_validate(a['projection']),cfg,version='results-artifact-v5'); payload=authoring_payload(cp); hits=set(re.findall(r'(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])',payload)); opaque.append({'case':case,'opaque_hash_count':len(hits),'examples':sorted(hits)[:5]})
result={'sha256_mutation_splits_component_pair':True,'source_hash_pair_ids':ids,'missing_local_retains_instant':True,'same_schedule_135_vs_176_separate':True,'opaque_hash_scan':opaque}
path=Path('/private/tmp/results_compact_preservation_negative_controls.json');path.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
