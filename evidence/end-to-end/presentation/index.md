# Live Results presentation evidence

Each row uses a saved Ranking export and a live Results writer. Earlier iterations
remain immutable. Offline authored examples are under `offline/` and are excluded here.

| Iteration | Case | Model | Final check | Writer calls | Answer | Review |
| --- | --- | --- | --- | ---: | --- | --- |
| 001 | admitted | gpt-6-luna | annotated; 6 notices | 2 | [answer](iterations/001/admitted/answer.md) | [review](iterations/001/review.md) |
| 002 | admitted | gpt-6-luna | annotated; 10 notices | 2 | [answer](iterations/002/admitted/answer.md) | [review](iterations/002/review.md) |
| 003 | admitted | gpt-6-luna | clean; 0 notices | 2 | [answer](iterations/003/admitted/answer.md) | [review](iterations/003/review.md) |
| 004 | admitted | gpt-6.1-sol | clean; 0 notices | 2 | [answer](iterations/004/admitted/answer.md) | [review](iterations/004/review.md) |
| 005 | admitted | gpt-6.1-sol | clean; 0 notices | 2 | [answer](iterations/005/admitted/answer.md) | [review](iterations/005/review.md) |
| 005 | conditional | gpt-6.1-sol | clean; 0 notices | 2 | [answer](iterations/005/conditional/answer.md) | [review](iterations/005/review.md) |
| 006 | admitted | gpt-6.1-sol | clean; 0 notices | 2 | [answer](iterations/006/admitted/answer.md) | [review](iterations/006/review.md) |
| 006 | conditional | gpt-6.1-sol | clean; 0 notices | 2 | [answer](iterations/006/conditional/answer.md) | [review](iterations/006/review.md) |
| 006 | incomplete | gpt-6.1-sol | generation error; no answer | 1 | [failure receipt](iterations/006/incomplete/receipt.json) | [review](iterations/006/review.md) |

`index.json` contains each attempt's exact writer usage, measured input
tokens, failed-finding count, source/config hashes, and current review status.
A clean checker outcome alone does not qualify traveler-facing prose.
