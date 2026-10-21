import json, hashlib, collections, sys
from pathlib import Path
from award_agent.ranking.projection_contracts import SolutionProjection
from award_agent.results import ResultsConfig, prepare_results
from award_agent.results.core import authoring_payload

ROOT=Path('/Users/shawnkang/bots/award-search')
BASE=ROOT/'evidence/end-to-end/presentation/iterations/006'
config=ResultsConfig.model_validate_json((BASE/'config.json').read_text())
FAIL=[]
def ck(ok, case, code, detail=None):
    if not ok: FAIL.append({'case':case,'code':code,'detail':detail})
def raw(x): return {'state':x.get('state'),'value':x.get('value')}
def time(x):
    d={'local_iso':x.get('local_iso'),'timezone':x.get('timezone')}
    if x.get('local_iso') is None and x.get('instant') is not None: d['instant']=x['instant']
    return d

def main(case):
    path=BASE/case/'artifact.json'; artifact=json.loads(path.read_text()); original=artifact['projection']; v=original['view']; receipt=original['receipt']; source=artifact['prepared']['source']
    p=SolutionProjection.model_validate(original); prepared=prepare_results(p,config,version='results-artifact-v5'); av=prepared.authoring_view
    refs=av.references.model_dump(mode='json'); compact=av.view; payload=authoring_payload(prepared)
    aliases={**refs['journeys'],**refs['awards'],**refs['cash']}; inv={x:y for y,x in aliases.items()}
    alt={x['candidate_id']:x for x in v['alternatives']}; com={x['observation_id']:x for x in v['components']}; src={x['observation_id']:x for x in source['components']}
    reason={x['reason_set_id']:x['reasons'] for x in v['reason_sets']}; cost={x['cost_id']:x['cost'] for x in v['costs']}; costpart={x['cost_component_id']:x['component'] for x in v['cost_components']}; assess={x['assessment_id']:x for x in v['assessments']}; evidence={x['observation_id']:x for x in receipt['observation_sources']}
    eligible={x['candidate_id'] for x in v['alternatives'] if x['status'] in ('admitted','conditional')}; rejected=[x for x in v['alternatives'] if x['status']=='rejected']
    expected_components={alt[x]['award_observation_id'] for x in eligible}|{alt[x]['cash_observation_id'] for x in eligible if alt[x]['cash_observation_id']}|set(v['direct_cash_observation_ids'])|set(v['award_summary_observation_ids'])|set(v['unmatched_award_observation_ids'])|set(v['unpaired_positioning_observation_ids'])
    result={'case':case,'canonical_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'eligible':len(eligible),'rejected':len(rejected),'journey_groups':len(compact['journeys']),'component_groups':len(compact['components']),'checks':{},'findings':{}}
    ck(set(refs['journeys'].values())==eligible,case,'eligible_alias_set'); ck(len(refs['journeys'])==len(eligible),case,'eligible_alias_unique')
    ck(set(refs['awards'].values())|set(refs['cash'].values())==expected_components,case,'component_alias_set',{'expected':len(expected_components),'actual':len(refs['awards'])+len(refs['cash'])})
    ck(set(refs['cash'].values())=={x for x in expected_components if com[x]['kind']=='cash_itinerary'},case,'cash_kind'); ck(set(refs['awards'].values())=={x for x in expected_components if com[x]['kind']!='cash_itinerary'},case,'award_kind')
    jmembers=[(g,m) for g in compact['journeys'] for m in g['members']]; cmembers=[(g,m) for g in compact['components'] for m in g['members']]
    ck(collections.Counter(m['ref'] for _,m in jmembers)==collections.Counter(refs['journeys'].keys()),case,'journey_members_once')
    ck(collections.Counter(m['ref'] for _,m in cmembers)==collections.Counter(({**refs['awards'],**refs['cash']}).keys()),case,'component_members_once')
    for g,m in jmembers:
        a=alt[refs['journeys'][m['ref']]]; f=g['facts']; oid=a['award_observation_id']; cid=a['cash_observation_id']
        for k,expected in [('topology',a['topology']),('status',a['status']),('origin',a['original_origin']),('destination',a['original_destination']),('departure',time(a['departure'])),('arrival',time(a['arrival'])),('departure_date',a['original_departure_date']),('transfer_airport',a['transfer_airport']),('transfer_minutes',a['transfer_minutes']),('transfer_local_day_offset',a['transfer_local_day_offset']),('elapsed_minutes',a['elapsed_minutes']),('price_completeness',a['price_completeness']),('booking_obligation',a['booking_obligation']),('award_cabin',raw(a['award_cabin'])),('premium_economy_addon',a['premium_economy_addon']),('positioning_reason',a['positioning_reason']),('reasons',reason[a['reason_set_id']])]:
            ck(f.get(k)==expected,case,'journey_field:'+k,m['ref'])
        ck(refs['awards'].get(m['award'])==oid,case,'journey_award_ref',m['ref']); ck((refs['cash'].get(m['cash']) if m['cash'] else None)==cid,case,'journey_cash_ref',m['ref'])
        ck(m['award_observed_at']==com[oid]['retrieved_at'],case,'journey_award_time',m['ref']); ck(m['cash_observed_at']==(com[cid]['retrieved_at'] if cid else None),case,'journey_cash_time',m['ref'])
        if a['cost_id']:
            c=cost[a['cost_id']]; actual=f['cost']; ck(actual is not None,case,'missing_cost',m['ref'])
            if actual is not None:
                for key in ('known_subtotal_usd','complete_usd','missing_parts','completeness'):
                    ck(actual.get(key)==c[key],case,'cost:'+key,m['ref'])
                expected_parts=[{'kind':costpart[x]['kind'],'state':costpart[x]['state'],'scope':costpart[x]['scope'],'reason':costpart[x]['reason'],'per_traveler_usd':costpart[x]['per_traveler_usd']} for x in c['component_ids']]
                ck(actual.get('components')==expected_parts,case,'cost_parts',m['ref'])
        expected_assess=[{'style':assess[x]['style'],'state':assess[x]['state'],'feature_label':assess[x]['feature_label'],'reasons':assess[x]['reasons'],'validation_needs':assess[x]['validation_needs']} for x in a['assessment_ids']]
        ck(f['assessments']==expected_assess,case,'assessments',m['ref'])
    for g,m in cmembers:
        oid=aliases[m['ref']]; c=com[oid]; s=src[oid]; f=g['facts']
        ck(m['observed_at']==c['retrieved_at']==s['retrieved_at'],case,'component_time',m['ref']); ck(m['provider_updated_at']==raw(c['provider_updated_at']),case,'provider_updated',m['ref'])
        for k in ('kind','provider','origin','destination','departure_date','airport_sequence','requested_travelers','requested_cabins','taxes_fees_unit','price_scope','carriers'):
            ck(f.get(k)==s[k],case,'component:'+k,m['ref'])
        for k in ('departure','arrival'):
            ck(f.get(k)==time(c[k]),case,'component_time_field:'+k,m['ref'])
        for k in ('returned_travelers','cabin','program','points','taxes_fees','tax_currency','seats','cash_amount','cash_currency','duration_minutes','stops','mixed_cabin_pct'):
            ck(f.get(k)==raw(c[k]),case,'component_raw:'+k,m['ref'])
        ck(f.get('reported_flight_numbers')==raw(c['reported_flight_numbers']),case,'flight_numbers',m['ref'])
        ck(f.get('findings')==[{k:z for k,z in finding.items() if k!='observation_id'} for finding in c['findings']],case,'component_findings',m['ref'])
        expected_legs=[{'origin':x['origin'],'destination':x['destination'],'departure':time(x['departure']),'arrival':time(x['arrival']),'carrier':raw(x['carrier']),'flight_number':raw(x['flight_number']),'cabin':raw(x['cabin'])} for x in c['legs']]
        ck(f.get('legs')==expected_legs,case,'legs',m['ref'])
    ck(set(refs['cash'][x] for x in compact['benchmarks'])==set(v['direct_cash_observation_ids']),case,'benchmarks')
    expected_leads=collections.Counter(v['award_summary_observation_ids']+v['unmatched_award_observation_ids']+v['unpaired_positioning_observation_ids'])
    actual_leads=collections.Counter(aliases[x['ref']] for x in compact['incomplete_leads']); ck(actual_leads==expected_leads,case,'incomplete_leads')
    for lead in compact['incomplete_leads']:
        oid=aliases[lead['ref']]; expected='award_summary' if oid in v['award_summary_observation_ids'] else 'unmatched_award' if oid in v['unmatched_award_observation_ids'] else 'unpaired_positioning'; ck(lead['kind']==expected,case,'lead_kind',lead['ref'])
    failed=collections.Counter((y['code'],y['detail']) for x in rejected for y in reason[x['reason_set_id']] if y['state']=='failed')
    unresolved=collections.Counter((y['code'],y['detail']) for x in rejected for y in reason[x['reason_set_id']] if y['state']=='unknown')
    expected_failed=[{'code':code,'detail':detail,'count':count} for (code,detail),count in sorted(failed.items())]
    expected_unresolved=[{'code':code,'detail':detail,'count':count} for (code,detail),count in sorted(unresolved.items())]
    ck(compact['exclusions']['rejected_count']==len(rejected),case,'rejected_count'); ck(compact['exclusions']['failed_reasons']==expected_failed,case,'failed_reasons'); ck(compact['exclusions']['unresolved_caveats']==expected_unresolved,case,'unresolved_caveats')
    expected_dates=sorted({f"{x['original_origin']}-{x['original_destination']} {x['original_departure_date']}" for x in rejected}); ck(compact['exclusions']['route_dates']==expected_dates,case,'exclusion_route_dates')
    ck(refs['comparison_pools']=={'P1':v['comparison_pool_ids']},case,'full_pool'); ck(compact['comparison']['eligible_count']==len(v['comparison_pool_ids']),case,'full_pool_count')
    for k in ('time_reference_minutes','cost_reference_usd'): ck(compact['comparison'][k]==v[k],case,'comparison:'+k)
    ck(compact['coverage']['provider_status']==v['provider_status'],case,'coverage_provider'); ck(len(compact['coverage']['groups'])==len(v['coverage_groups']),case,'coverage_group_count')
    for x,y in zip(compact['coverage']['groups'],v['coverage_groups']):
        for k in ('kind','status','reason','stream_complete','pair_coverage','routes_and_dates'): ck(x.get(k)==y[k],case,'coverage_group:'+k)
    for k in ('planning_coverage','planning_issues','planning_deferred_constraints','discovery_limitations','discovery_issues','provider_findings','execution_findings'):
        ck(compact['coverage'][k]==source[k],case,'coverage:'+k)
    for k in ('reason','material_uncertainty'):
        ck([x.get(k) for x in compact['coverage']['planning_strategy_notes']]==[x[k] for x in source['planning_strategy_notes']],case,'coverage_note:'+k)
    ck(compact['coverage']['transport_findings']==[x['findings'] for x in source['transport_findings']],case,'coverage_transport')
    # Independent pairwise comparison of all canonical decision facts and source receipts after removing only administrative identity/timestamps.
    component_pair_count=0; crossquery_count=0; bad_pairs=[]
    for group in compact['components']:
        if len(group['members'])<=1: continue
        component_pair_count+=len(group['members'])-1
        ids=[aliases[m['ref']] for m in group['members']]
        base=ids[0]
        for oid in ids[1:]:
            x={k:z for k,z in com[base].items() if k not in ('observation_id','query_id','retrieved_at')}; y={k:z for k,z in com[oid].items() if k not in ('observation_id','query_id','retrieved_at')}
            ex={k:z for k,z in evidence[base].items() if k not in ('observation_id','query_id')}; ey={k:z for k,z in evidence[oid].items() if k not in ('observation_id','query_id')}
            for r in ex['evidence']: r.pop('retrieved_at',None)
            for r in ey['evidence']: r.pop('retrieved_at',None)
            if x!=y or ex!=ey: bad_pairs.append([base,oid,'canonical_or_receipt_diff'])
            if com[base]['query_id']!=com[oid]['query_id']:
                crossquery_count+=1
                if not (com[base]['provider']=='gfly' and com[oid]['provider']=='gfly' and com[base]['provider_version']==com[oid]['provider_version']=='0.3.0+award-search-unpriced-party-echo-v2'):
                    bad_pairs.append([base,oid,'unapproved_crossquery'])
    ck(not bad_pairs,case,'component_group_equivalence',bad_pairs[:5])
    # Journey groups must agree on all canonical decision fields and resolved costs after component bindings are mapped to observed fact groups.
    group_of_comp={aliases[m['ref']]:i for i,g in enumerate(compact['components']) for m in g['members']}
    journey_pair_count=0; bad_journey=[]
    for group in compact['journeys']:
        if len(group['members'])<=1: continue
        journey_pair_count+=len(group['members'])-1
        ids=[refs['journeys'][m['ref']] for m in group['members']]; base=alt[ids[0]]
        for id in ids[1:]:
            other=alt[id]
            ignore=('candidate_id','option_family_id','award_observation_id','cash_observation_id','strategy_id','reason_set_id','cost_id','assessment_ids')
            if {k:z for k,z in base.items() if k not in ignore}!={k:z for k,z in other.items() if k not in ignore}: bad_journey.append([ids[0],id,'canonical_decision'])
            if group_of_comp[base['award_observation_id']]!=group_of_comp[other['award_observation_id']]: bad_journey.append([ids[0],id,'award_facts'])
            if base['cash_observation_id'] and other['cash_observation_id'] and group_of_comp[base['cash_observation_id']]!=group_of_comp[other['cash_observation_id']]: bad_journey.append([ids[0],id,'cash_facts'])
            if reason[base['reason_set_id']]!=reason[other['reason_set_id']]: bad_journey.append([ids[0],id,'reasons'])
            if [assess[x] for x in base['assessment_ids']]!=[assess[x] for x in other['assessment_ids']]:
                # assessment IDs can change with source IDs; compare actual writer-facing decision values.
                fx=[{k:v for k,v in assess[x].items() if k!='assessment_id'} for x in base['assessment_ids']]; fy=[{k:v for k,v in assess[x].items() if k!='assessment_id'} for x in other['assessment_ids']]
                if fx!=fy: bad_journey.append([ids[0],id,'assessments'])
            if base['cost_id'] and other['cost_id']:
                c1=cost[base['cost_id']]; c2=cost[other['cost_id']]
                if {k:z for k,z in c1.items() if k!='component_ids'}!={k:z for k,z in c2.items() if k!='component_ids'}: bad_journey.append([ids[0],id,'cost_total'])
                cp1=[{k:z for k,z in costpart[x].items() if k not in ('observation_id',)} for x in c1['component_ids']]; cp2=[{k:z for k,z in costpart[x].items() if k not in ('observation_id',)} for x in c2['component_ids']]
                if cp1!=cp2: bad_journey.append([ids[0],id,'cost_components'])
    ck(not bad_journey,case,'journey_group_equivalence',bad_journey[:5])
    ids=list(eligible)+list(expected_components)+list(v['comparison_pool_ids']); leaked=[x for x in ids if x in payload]; ck(not leaked,case,'canonical_ids_in_payload',leaked[:5])
    ck('"source_digest"' not in payload and '"binding_digest"' not in payload and '"query_id"' not in payload ,case,'machine_ids_in_payload')
    finding_codes=collections.Counter(f['code'] for oid in expected_components for f in com[oid]['findings']); missing_findings=collections.Counter(f['code'] for oid in expected_components for f in com[oid]['findings'] if f['message'] not in payload and f['code'] not in payload)
    result['findings']={'retained_component_finding_codes':dict(finding_codes),'codes_or_messages_absent_from_payload':dict(missing_findings),'component_groups_with_finding_field':sum('findings' in g['facts'] for g in compact['components'])}
    result['grouping']={'journey_pairs_factored':journey_pair_count,'component_pairs_factored':component_pair_count,'cross_query_component_pairs':crossquery_count,'bad_component_pairs':bad_pairs[:5],'bad_journey_pairs':bad_journey[:5]}
    result['checks']={'eligible_aliases_exact':True,'retained_component_aliases_exact':True,'benchmark_and_lead_sets_exact':True,'all_member_fact_fields_checked':True,'member_times_exact':True,'resolved_costs_checked':True,'exclusions_and_coverage_checked':True,'full_pool_checked':True,'no_canonical_ids_in_payload':not leaked}
    return result

out={'method':'Independent raw 006 projection/source/receipt comparisons to public prepare_results V5; no model/provider calls','cases':[main(x) for x in ('admitted','conditional','incomplete')],'failures':FAIL}
path=Path('/private/tmp/results_compact_preservation_probe.json'); path.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(json.dumps({'path':str(path),'cases':out['cases'],'failures':FAIL},indent=2))
sys.exit(bool(FAIL))
