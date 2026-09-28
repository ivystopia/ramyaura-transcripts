# Search gameplay concepts

The [glossary](GLOSSARY.md) explains gameplay decisions using Ramy’s published passages. The concept index adds aliases, distinguishes different meanings of the same word, and preserves conditions and nearby qualifications. It is a separate editorial layer: neither the corrected transcripts nor their original machine wording is changed.

This first curated set contains **21 concepts and 79 annotations across 54 passages**. It is incomplete across the full archive. An absent annotation does not mean Ramy never discusses the concept. Daily uploads retain these files but do not automatically receive new concept annotations.

## The most useful distinctions

1. **Tempo, a recall and a recall window are different concepts.** Readiness relative to an opponent and readiness alongside allies are separate checks. Priority still depends on who can actually act. See [tempo](GLOSSARY.md#tempo), [recall action](GLOSSARY.md#recall-action), [recall window](GLOSSARY.md#recall-window) and [priority](GLOSSARY.md#priority).
2. **The immediate HP exchange does not settle the value of a trade.** Recovery, potions and an impending enemy reset can change the result. See [sustain](GLOSSARY.md#sustain).
3. **Duration, return damage and kill commitment are different questions.** A short trade can be expensive, a one-sided trade need not kill, and an all-in depends on available tools. See [trading](GLOSSARY.md#trade-and-all-in).
4. **Shadowing an ally differs from other uses of hover or shadow.** Tooltip actions, champion selection, lane-side positioning and item-passive names must not become positive ally-support examples. See [shadowing](GLOSSARY.md#shadowing).
5. **Lane control does not mean always pushing.** A freeze can deny options; pushing can create a movement window or mistakenly return access to the opponent. See [lane control](GLOSSARY.md#lane-control).

The glossary also connects [spacing](GLOSSARY.md#spacing) to available threats, [weakside](GLOSSARY.md#weakside) to support and pathing, and [team timing](GLOSSARY.md#team-timing) to the cost of another camp or wave. These are conditional explanations, not current-patch build instructions.

## Run a local search

Python 3.10 or newer is sufficient. No network access, model API or API key is used.

```sh
python3 scripts/concept_search.py --list
python3 scripts/concept_search.py tempo
python3 scripts/concept_search.py "weak side"
python3 scripts/concept_search.py prio
python3 scripts/concept_search.py shadowing --json
```

The default search returns only curated supporting annotations. It resolves aliases rather than performing an unrestricted keyword search. For example, `tempo` returns ten reviewed gameplay-timing matches; `lethal tempo` retrieves the separately classified rune-name occurrences. `weakside`, `weak side` and `weak-side` resolve to the same concept and currently return five examples, including one explicitly identified as Ramy playing jungle.

Use `--all-classifications` to inspect excluded and unresolved matches, and `--limit` to change the displayed maximum:

```sh
python3 scripts/concept_search.py hover --all-classifications --limit 30
python3 scripts/concept_search.py tempo --json --limit 100
```

`total` counts annotations, not distinct videos or passages. Multiple occurrences in one passage can have different spans. For broader discovery outside this curated set, use the ordinary text-search example in [SCHEMA.md](SCHEMA.md); a word match alone does not establish the intended gameplay meaning.

## Reading the evidence

Each result provides the source URL, approximate interval, upload date, recorded encounter/role where established, editorial interpretation and relevant transcript excerpt. Linked context is included when needed to preserve the reasoning. For example, a proposed recall with Tristana remains linked to the next passage considering a timing offset for an item. That pair must not become an unconditional instruction to recall with an ally.

Decision annotations record the situation, goal, considered action, chosen action, reason and qualification. They can describe a mistake or a reconsidered plan. A chosen action can remain unresolved rather than guessing from an incomplete passage. A role is taken from a recorded encounter only when the entire passage fits inside that encounter; transitions remain unassigned.

These annotations are **assistant interpretations of machine transcripts, not human audio verification**. Existing source review flags remain in place. Source wording has not been corrected as part of this concept work. Unclear meanings are marked `unresolved`; excluded rune, item or interface meanings are marked `exclude`. Neither is returned as positive evidence by default.

Recording patches remain unknown. Upload dates are publication dates, not game patches. Ability ranges, item effects, summoner interactions and exact timing assumptions require separate patch-specific verification. Video timestamps are approximate positions in the upload, not the in-game clock.

## Files and maintenance

- [data/concepts.json](data/concepts.json) holds definitions, lookup aliases, glossary anchors and related concepts. Some aliases are editorial terminology for discovery, not words established as spoken by Ramy.
- [data/concept-annotations.jsonl](data/concept-annotations.jsonl) holds references and character spans into existing Ramy passages, interpretations, conditions and optional decision records. It contains no copied full transcripts or additional source videos.
- [SCHEMA.md](SCHEMA.md#concept-annotations) defines this separate versioned format. The corpus itself remains at schema version 2.
- [scripts/concept_search.py](scripts/concept_search.py) validates references before returning results. Changed source text invalidates the old annotation rather than silently moving its span.

All concept evidence must resolve to existing published passages from RamyAura’s channel. The publication validator checks that restriction, source hashes, text spans, continuation references, aliases and glossary links, together with the usual file manifest and privacy checks. It does not prove the editorial interpretation correct.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/validate.py
```

When extending the index, inspect the original context, preserve self-corrections and uncertainty, and add a focused positive/negative search check where a word has competing meanings. Review these annotations separately from transcript corrections. New daily uploads remain ordinary corpus records until their concepts are explicitly reviewed.
