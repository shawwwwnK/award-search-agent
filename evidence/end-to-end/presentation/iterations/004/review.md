# Iteration 004 review

Status: admitted answer is mechanically clean and notably more readable;
agent presentation review still rejects it for factual-language and layout
problems. Owner review pending. The conditional and incomplete cases were held.

The stronger run-specific writer chose two award itineraries, gave local travel
times and readable prices, used traveler-facing headings, and completed the
required bindings after one correction. The final artifact has no notices and
replays exactly. These are useful improvements over iterations 001–003.

Option B is described as a choice for “a morning arrival” against Option A's
evening arrival, but B arrives on January 17 and A on January 16. The text
should state that next-day tradeoff directly. The answer begins with Option A
without a trip-level opening, shows the benchmark-status value `available` on
its own line, repeats coverage limitations, says award details were “checked”
on an observation date, and says the provider's last update is “Date not
reported.” Those details are confusing in a final traveler answer. Search
coverage language is also too prominent for the result. The wording is not
yet ready for a traveler even though the mechanical checker is clean.

This run changed both the run-specific model (to `gpt-6.1-sol`) and the prompt;
it does not isolate which change caused the improvement. It used the same saved
admitted Ranking export and two live Results authoring calls. The initial
draft had one claim-scope failure; the correction had none. Exact writer usage
was 820,898 input / 2,514 output tokens, then 822,617 input / 1,906 output
tokens. The source and code hashes stayed unchanged during the call, and the
Results package plus dependency versions are archived for replay.

Next iteration should make the benchmark-status slot a complete sentence or
place it grammatically, treat observation dates as observed dates, show a
missing provider-update date without awkward framing, and require every option
comparison to name both dates when arrivals fall on different days. Then run
the admitted, conditional and incomplete cases against one frozen revision.
