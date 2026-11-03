# q017 blind Results M2 review

**H: fail. U: fail. M2: fail. C: insufficient.** Sparse-source exception: no.

## Source-grounded failures

1. “For an Aeroplan award, I’d investigate the Hong Kong connection first: it gives the earliest Bangkok arrival among these late-departure options, with a shorter elapsed trip than the Taiwan alternatives.” The selected `evidence.json` journey `28b5a832f590e31794a56935985a19ac2add1203a766c16aa9bb5edbcf8a1a82` has `departure.local_iso` January 15 at 23:15, `arrival.local_iso` January 17 at 10:35, and `elapsed_minutes` 1220. Another admitted HKG journey, `eba1b0800784ea3ca14afa1a89a4c140e5004a8b1e3b83831ef7e155c17f1669`, leaves at the **same 23:15**, arrives at **09:50**, and takes **1175** minutes. Both return 65,000 points and 10,740 CAD minor fee units; their award components report **2 versus 9 seats**. The lead is not the earliest late-departure arrival, and its stated schedule reason does not defend choosing it first. The selected HKG is indeed shorter than the Taiwan journeys; that clause is separately supported.
2. “This economy award via HKG arrives 35 minutes before the later Taiwan option and has a 105-minute award connection.” The HKG `arrival.instant` is **2027-01-17T03:35:00Z**; the only displayed Taiwan journey, `46ff88141207d0e57a27197f6ea281b2f5c2206a27151cbe79bc6f1764c48fd3`, arrives **2027-01-16T18:25:00Z**, **9 hours 10 minutes before HKG**. The 105-minute HKG connection is correct. An unreferenced Taiwan journey, `2df689e0ff0d8ad01708129eb8fb9ea5398c9accb14343c04ad99d2f6bc77dd6`, arrives at 11:10 local, 35 minutes after HKG. The phrase “later Taiwan option” may refer to that unshown record, but the answer does not identify it and later explicitly gives the displayed Taiwan journey's 9-hour-10-minute advantage.

The opening and the displayed Taiwan paragraph contradict each other on which shown journey reaches Bangkok first. This breaks the core traveler recommendation, even though the answer has embedded references, accurate observed points and fees, a separate USD 440 one-stop SIN cash baseline with unknown price scope, and consolidated limitations.

The displayed Taiwan journey also has a weak decision role: another admitted TPE journey, `c559213003ec943dd700f59c7813a457b52988433ba469978634ffb2a6a72954`, leaves SFO at the same noon time, arrives January 16 at 23:40 instead of January 17 at 01:25, takes 1240 instead of 1345 minutes, and reports two instead of one seat with the same returned points and fee amounts. This is evidence against the particular comparison, not an option quota or an exhaustive-frontier requirement. Current bookability and all-in cost remain unresolved.

No live calls were made; no escalation is recommended for this judgment.
