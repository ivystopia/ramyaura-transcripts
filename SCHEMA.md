# Dataset schema

The public edition uses schema version 2. Files ending in `.jsonl` contain one UTF-8 JSON object per line. Join passage and source records by `video_id`; use `chunk_key` as the stable passage identifier. Times are seconds in the source video. Upload dates use `YYYY-MM-DD`.

## Passage records: `data/corpus.jsonl`

- `video_id`, `source_url`: source identity and a timestamped YouTube link. Integer YouTube timestamps round fractional starts upwards; use the exact numeric fields for alignment or joins.
- `chunk_key`, `source_chunk_key`: identifiers retained from the source archive. These are identities, not hashes of the corrected text.
- `start_seconds`, `end_seconds`: approximate passage bounds. `timing_method` describes alignment limits. A `coarse_api_chunk_timing` quality flag means the interval is the complete submitted audio chunk (up to about ten minutes), not a sentence-level estimate.
- `text`: corrected reading text, copied without changing its characters or whitespace. A single record has empty text because no speech was detected in the on-screen guide.
- `text_original`: original `gpt-transcribe` wording, before terminology corrections. `text_sha256` and `text_original_sha256` hash their respective UTF-8 strings.
- `text_char_range`: character bounds in the original parent API chunk, not in the full video or corrected text. Parent source files are retained privately and identified by hashes.
- `model`, `text_status`, `review_status`, `quality_flags`: origin and review state. A terminology correction does not imply full audio verification.
- `terminology_corrections`: edits with `start`, `end`, `original`, `replacement`, entity identity, rule ID, public evidence URL, basis and review status. Offsets are Unicode code-point positions in `text_original`, with an exclusive end. Apply edits in descending start order to reproduce `text`.
- Gameplay terms can use `entity_kind: concept`; for example, `entity_id: cheater-recall` identifies the [cheater recall concept](GLOSSARY.md#cheater-recall). This is a terminology classification, not validation of the associated strategy for the current patch. Glossary explanations are editorial and are not inserted into the spoken text.
- `terminology_uncertainties`: unresolved candidates. Their `start` and `end` refer to the original reading used during the terminology audit; `target` is a candidate entity, not a confirmed correction.
- `review_notes`: scoped editorial wording notes. A resolved sentence does not resolve all other issues in its passage.
- `annotations`: scoped human wording checks, separately labelled assistant visual observations and gameplay interpretations. Private reviewer correspondence and identity are omitted. Frame and parent transcript hashes identify evidence retained in the private archive; those media files are not included here.
- `source_audio_sha256`, `provenance`: hashes identifying the underlying audio and transcription artifacts. Local filesystem paths and API request identifiers are excluded.
- `recording_patch`: currently `null`; `current_patch_applicability`: currently `unvalidated` for every passage. A null patch is unknown, not permission to treat a claim as timeless.
- `visual_reference`: present on the empty speech record; points to the separate public OCR file.

The human-readable Markdown escapes formatting characters for safe presentation and omits leading/trailing whitespace. JSONL preserves the source reading exactly. A passage heading's whole-second label is for display; exact fractional times remain in the JSON.

## Video records: `data/sources.jsonl`

Each record contains the public video ID, URL, title, description, channel name and ID, upload date, unknown recording date and patch, listed and decoded duration, audio hash, passage count, content kind, context and relative transcript path.

`encounters` identifies the actual opponent and role in a recorded interval, not every champion mentioned in the commentary. Each encounter retains its name and Riot ID, `start`/`end` bounds, classification basis, evidence passage keys, review status and source hash. A video's title can describe a different game in the same upload: filter using the encounter interval. Include only passages whose entire interval falls inside the encounter; transition passages remain available through the full transcript.

The champion reference version used during the archive's terminology and matchup work was Riot Data Dragon **16.18.1**. Canonical names do not establish recording patches or current strategic validity. `review: not_human_verified` remains attached where applicable.

## On-screen text

`data/visual-captions.jsonl` contains OCR caption groups with source identity, approximate times, recognised text, frame hash, sampled-frame count, quality flags, and a `result_marker_candidate`. A marker candidate is an image-processing observation, not confirmation of a game interaction. OCR text is not subjected to the spoken-transcript terminology corrections.

`data/visual-caption-checks.jsonl` contains separate assistant observations with `reviewer`, `review_scope` and `human_reviewed: false`. They do not silently replace the OCR text and do not certify the gameplay claims.

## Example: search corrected passages

Run this from the repository root after downloading or cloning it:

```python
import json
from pathlib import Path

sources = {
    row["video_id"]: row
    for row in map(json.loads, Path("data/sources.jsonl").open())
}
for row in map(json.loads, Path("data/corpus.jsonl").open()):
    if "sweeper" in row["text"].casefold():
        source = sources[row["video_id"]]
        print(source["title"], source["upload_date"])
        print(row["source_url"])
        print(row["text"])
        print("Patch:", row["recording_patch"], row["current_patch_applicability"])
        print("Uncertainty:", row["terminology_uncertainties"])
```

<a id="concept-annotations"></a>

## Editorial concept index

The optional search layer is described in [CONCEPTS.md](CONCEPTS.md). Its files use their own format version 1 and do not change the schema or text of `data/corpus.jsonl`.

`data/concepts.json` contains `schema_version`, `editorial_author`, `editorial_basis`, `review_scope` and `concepts`. Each concept has a stable `id`, label, aliases, a `glossary_anchor`, a definition and related concept IDs. Aliases are lookup conveniences and do not establish that a particular phrase occurs in the speech. Map tempo and the Lethal Tempo rune have separate IDs; recall action and recall window also remain separate.

Each line of `data/concept-annotations.jsonl` contains:

- `id`, `concept_id`, `chunk_key`: annotation identity, concept and the existing source passage. No new video or transcript is embedded.
- `text_sha256`, `span`: the hash of the existing corrected `text` and its `[start, end]` Unicode code-point offsets, with an exclusive end. These offsets refer to corrected passage text, unlike terminology-correction offsets into `text_original`.
- `classification`: `supports`, `exclude` or `unresolved`. A passage discussing a mistaken action can still support a concept; `exclude` means the text has a different sense, such as a rune name instead of map tempo. Default concept search returns only `supports`.
- `interpretation`, `conditions`: newly written editorial explanation and the circumstances that constrain it. These are separate from Ramy’s speech.
- `context_keys`, `context_text_sha256`: additional passages from the same video needed to retain the reasoning or qualification, with hashes of their corrected text. Search returns their text as context rather than silently collapsing the argument to one sentence. Changes to a continuation invalidate its dependent interpretation too.
- `decision`: optional `situation`, `goal`, `considered_action`, `chosen_action`, `reason` and `qualification`. A choice may be explicitly unresolved; this is not a ground-truth action label reconstructed from the game video.
- `confidence`, `review_status`, `human_reviewed`: scoped confidence in the interpretation. Current entries use `assistant_context_review_not_audio_verification` and `human_reviewed: false`; they do not upgrade the underlying machine transcript’s review status.
- `recording_patch`, `current_patch_applicability`: currently `null` and `unvalidated`, matching the source uncertainty.

Join annotations to passages by `chunk_key`, then to sources by `video_id`. Obtain dates, timing limits, source URLs and encounter/role information from those existing records. Multiple annotations can point at a passage or at different spans within it. Do not discard an entire passage merely because one occurrence has an unrelated meaning. New corpus records do not acquire annotations automatically, so a missing annotation is not evidence of a missing concept.

## Manifest and maintenance

`manifest.json` records the initial source snapshot hashes, counts, publication transform and hashes of every published file except itself. Run `python3 scripts/validate.py` to check a copy. After intentional, reviewed edits, maintainers can run `python3 scripts/validate.py --update-manifest`; all content checks must pass before new hashes are written. Hash consistency shows that files have not changed relative to that manifest; it does not establish factual accuracy or authorisation independently.
