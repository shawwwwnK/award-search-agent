# Blind review: q076

- Rubric: `fast-default-M2-v1.2-calibrated`
- H: **fail**; U: **pass**; M2: **pass**; C: **decision-rich**
- Sparse-source exception: **no**

## H finding

> “I’d choose the later-departing Aeroplan award via Hong Kong if arriving sooner and keeping the connection short matter most.”

`evidence.json` journeys `eba1b080...` and `46ff8814...`, fields `arrival.local_iso`, show Hong Kong arriving at 09:50 and Taiwan at 01:25 on January 17 in Bangkok. `comparison-registry.json` T05 confirms Taiwan arrives 505 minutes earlier. The opening uses “arriving sooner” as a reason for Hong Kong despite this displayed earlier-arriving alternative. The next sentence acknowledges Taiwan's earlier arrival. The opening comparison target is unstated: Hong Kong does arrive before the later PEK choice. This is a material scope ambiguity for adjudication, not an unambiguous numeric error or a clean factual pass.

## Other judgments

The recommended journey's short 70-minute connection and later departure are supported, and the later arrival is disclosed, making the next action defensible. The answer gives individual explanations around three journey references, a separate cash benchmark, and consolidated limitations. Local gains and losses are decision-rich: Taiwan arrives earlier but departs earlier and takes longer; Hong Kong has shorter elapsed travel and connection; PEK has the lowest reported CAD tax quote among the three shown but a much longer trip and connection. Exact points, quoted taxes, seats, traveler support, journey cabins, absent leg cabins, times, durations, one-stop cash baseline, and unknown price scopes match the source. No strongest-representative or coverage quota is applied.

Uncertainty: the intended target of “arriving sooner” is not explicit. Recommend parent adjudication of H; no architecture escalation is needed.
