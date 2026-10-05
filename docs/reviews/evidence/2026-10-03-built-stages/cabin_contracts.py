"""Synthetic offline cabin-contract probes; run from repository root.

All provider responses are served by FakeHttp and all credentials are the
literal test-only value. Results demonstrate behavior for synthetic inputs;
they make no claim about normal-runtime failure frequency or live responses.
No network, model, provider, or credential calls are made.
"""

import json
from pathlib import Path
from datetime import date
from tempfile import TemporaryDirectory
from award_agent.providers.contracts import ProviderQuery
from award_agent.providers.seats_aero import SeatsAeroAdapter, _local_instant
from award_agent.providers.gfly import _local_time
from award_agent.providers.transport import HttpResponse
from award_agent.ranking.matching import _requirements, _build_candidate
from award_agent.ranking.contracts import MatchedJourneySet
from award_agent.domain import CabinClass

class FakeHttp:
    def __init__(self, payload): self.payload, self.params = payload, None
    def get(self, url, *, params, **kwargs):
        self.params = dict(params)
        return HttpResponse(200, json.dumps(self.payload).encode(), 0.01)

base = {'ID':'synthetic-trip','AvailabilityID':'availability-1','Source':'aeroplan',
        'Cabin':'premium','OriginAirport':'SFO','DestinationAirport':'BKK',
        'DepartsAt':'2026-10-05T10:00:00Z','ArrivesAt':'2026-10-06T12:00:00Z',
        'RemainingSeats':4,'MileageCost':70000,'TotalTaxes':10000,'TaxesCurrency':'USD',
        'Stops':0,'AvailabilitySegments':[{'OriginAirport':'SFO','DestinationAirport':'BKK',
        'DepartsAt':'2026-10-05T10:00:00Z','ArrivesAt':'2026-10-06T12:00:00Z'}]}
zones={'SFO':'America/Los_Angeles','BKK':'Asia/Bangkok'}
def run(cabins, provider_cabin, **fields):
    query=ProviderQuery(query_id='award-test',provider='seats_aero',role='award_detail',
        origins=('SFO',),destinations=('BKK',),start_date=date(2026,10,5),end_date=date(2026,10,5),
        travelers=2,cabins=cabins,detail_id='availability-1',activation_observation_ids=('summary-1',))
    row=dict(base,Cabin=provider_cabin,**fields)
    transport=FakeHttp({'data':[row]})
    with TemporaryDirectory(dir='/private/tmp') as tmp:
        adapter=SeatsAeroAdapter(api_key='test-only',evidence_root=Path(tmp),transport=transport)
        capture=adapter.fetch(query,cursor=None,timeout_seconds=1,max_bytes=10000)
        page=adapter.parse(query,capture,airport_timezones=zones)
    print(json.dumps({'requested':cabins,'returned':provider_cabin,'status':page.status,
        'observations':len(page.observations),'findings':[f.code for f in page.findings],
        'normalized_cabins':[o.cabin.value for o in page.observations]}))
    return page
for req, raw in [(('business',),'business'),(('premium_economy',),'premium'),(('premium_economy',),'premium_economy'),((),'premium')]:
    run(req,raw)
query=ProviderQuery(query_id='award-search',provider='seats_aero',role='mandatory_award',
        origins=('SFO',),destinations=('BKK',),start_date=date(2026,10,5),end_date=date(2026,10,5),
        travelers=2,cabins=('premium_economy',))
transport=FakeHttp({'data':[],'hasMore':False})
with TemporaryDirectory(dir='/private/tmp') as tmp:
    adapter=SeatsAeroAdapter(api_key='test-only',evidence_root=Path(tmp),transport=transport)
    adapter.fetch(query,cursor=None,timeout_seconds=1,max_bytes=10000)
print('outbound_cabins',transport.params['cabins'])

matched=MatchedJourneySet.model_validate_json(Path('evidence/ranking-stage/m1/mixed_access.json').read_text())
request=matched.request.model_copy(update={'cabins':(CabinClass.BUSINESS,)})
observation=run(('business',),'business',MixedCabinPct=25).observations[0]
print('mixed_cabin_raw',observation.raw_fields['MixedCabinPct'].value)
print('mixed_cabin_requirement_reasons',[(r.code,r.state) for r in _requirements(request,observation,None,None)])
candidate=_build_candidate(award=observation,cash=None,cash_query=None,topology='direct_award',
    request=request,timezones=zones,plan=matched.plan,
    airport={a.airport_id:a.airport_iata for a in matched.plan.airport_directory},
    original_origin='SFO',original_destination='BKK')
print('mixed_cabin_candidate_status',candidate.status)
for local in ['2026-11-01T01:30:00','2026-03-08T02:30:00','2026-10-05T10:00:00']:
    print('timezone_control',local,'seats',_local_instant(local,'SFO',zones)[1], 'gfly',_local_time(local,'SFO',zones)[1])
from award_agent.providers.contracts import RawField
from award_agent.ranking.styles import _features
from award_agent.ranking.style_contracts import RankingStylePolicy, CurrencyConversionSnapshot
from decimal import Decimal
snapshot=CurrencyConversionSnapshot(snapshot_id='synthetic',as_of=date(2026,10,3),
    source='synthetic USD identity',source_digest='a'*64,rates_to_usd={'USD':Decimal(1)})
for raw in ['premium','premium_economy']:
    award=run((),raw).observations[0]
    journey=_build_candidate(award=award,cash=None,cash_query=None,topology='direct_award',
        request=matched.request,timezones=zones,plan=matched.plan,
        airport={a.airport_id:a.airport_iata for a in matched.plan.airport_directory},
        original_origin='SFO',original_destination='BKK')
    f=_features(journey,{award.observation_id:award},RankingStylePolicy(),snapshot,matched.request.travelers,zones)
    print('premium_addon_control',raw,journey.status,f.premium_economy_addon)
for change in [
    {'hard_constraints':('No overnight connections',)},
    {'cabins':(CabinClass.ECONOMY,)},
]:
    req=request.model_copy(update=change)
    print('requirement_control',str(change),[(r.code,r.state) for r in _requirements(req,observation,None,None)])
