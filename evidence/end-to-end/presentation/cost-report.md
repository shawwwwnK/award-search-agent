# Results presentation API usage and estimated writer cost

Scope: live Results authoring in `iterations/` only. This excludes the original
end-to-end diagnostic, offline fixtures, other sessions, and any cost of the
input-token measurement endpoint. It is a rate-based estimate, not an invoice.

Rates: [OpenAI API pricing](https://developers.openai.com/api/docs/pricing),
Standard tier as recorded for October 9, 2026. Sixteen writer requests
exceeded 272,000 input tokens and use long-context rates for the entire request;
the final incomplete-case request used 253,293 input tokens and short-context rates.
Ordinary input is reported input minus cached-read and cache-write tokens;
output already includes reasoning tokens. Cache writes are billed separately.

| Iteration | Case | Attempt | Model | Input | Cached read | Cache write | Output | Estimated writer cost |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: |
| 001 | admitted | initial | gpt-6-luna | 785,660 | 0 | 785,657 | 8,317 | $0.20265260 |
| 001 | admitted | correction | gpt-6-luna | 791,039 | 1,607 | 789,429 | 6,398 | $0.20218849 |
| 002 | admitted | initial | gpt-6-luna | 785,756 | 0 | 785,753 | 6,540 | $0.20134385 |
| 002 | admitted | correction | gpt-6-luna | 789,701 | 1,697 | 788,001 | 6,869 | $0.20218654 |
| 003 | admitted | initial | gpt-6-luna | 820,736 | 0 | 820,733 | 10,240 | $0.21286385 |
| 003 | admitted | correction | gpt-6-luna | 823,742 | 2,118 | 821,621 | 3,565 | $0.20812196 |
| 004 | admitted | initial | gpt-6.1-sol | 820,898 | 0 | 820,895 | 2,514 | $4.14219700 |
| 004 | admitted | correction | gpt-6.1-sol | 822,617 | 2,273 | 820,341 | 1,906 | $4.13076160 |
| 005 | admitted | initial | gpt-6.1-sol | 821,208 | 0 | 821,205 | 2,322 | $4.14086700 |
| 005 | admitted | correction | gpt-6.1-sol | 823,008 | 2,574 | 820,431 | 1,638 | $4.12725180 |
| 005 | conditional | initial | gpt-6.1-sol | 731,461 | 2,574 | 728,884 | 2,729 | $3.68588180 |
| 005 | conditional | correction | gpt-6.1-sol | 733,611 | 2,574 | 731,034 | 2,236 | $3.68923680 |
| 006 | admitted | initial | gpt-6.1-sol | 822,377 | 0 | 822,374 | 2,186 | $4.14467200 |
| 006 | admitted | correction | gpt-6.1-sol | 824,274 | 2,790 | 821,481 | 1,879 | $4.13616000 |
| 006 | conditional | initial | gpt-6.1-sol | 732,878 | 2,790 | 730,085 | 4,245 | $3.71467000 |
| 006 | conditional | correction | gpt-6.1-sol | 736,664 | 2,790 | 733,871 | 3,857 | $3.72778000 |
| 006 | incomplete | initial | gpt-6.1-sol | 253,293 | 2,790 | 250,500 | 32,768 | $0.95421500 |

Writer calls: **17**. Input-token measurement calls: **17**. Estimated writer cost by model: gpt-6-luna $1.22935729; gpt-6.1-sol $40.59369300. Total: **$41.82305029**.

`cost-report.json` preserves each attempt's complete raw usage object, its
token categories, rate tier and unrounded calculated amount. It does not
estimate the cost of the separate measurement endpoint or reconcile an invoice.
