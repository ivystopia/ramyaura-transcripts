# RamyAura transcripts

Searchable, timestamped transcripts of **158 regular YouTube uploads by RamyAura**, covering **70.98 hours** of Teemo gameplay and discussion. Shared free of charge with RamyAura's permission; his agreement to sharing is conditional on it being free.

**[Browse by matchup](MATCHUPS.md)** · **[Browse all videos](TRANSCRIPTS.md)** · **[Gameplay glossary](GLOSSARY.md)** · **[Download the complete repository](https://github.com/ivystopia/ramyaura-transcripts/archive/refs/heads/main.zip)**

Original creator: **RamyAura** — https://www.youtube.com/channel/UChk2Zu5h5yJ9BBD4VS-_chQ · https://www.twitch.tv/ramyaura

## Read the transcripts

Choose an opponent in [MATCHUPS.md](MATCHUPS.md), or a video in [TRANSCRIPTS.md](TRANSCRIPTS.md). Each transcript has its original title, publication date, recorded opponent and role where established, and links to the relevant moments on YouTube. For uploads containing multiple games, the matchup index links into the appropriate game.

The collection contains 157 videos with detected speech and one guide presented as on-screen text. The latter has a separately labelled OCR transcript. Livestreams and Shorts are outside this snapshot. Collection last updated on **19 September 2026**, including regular uploads published through **18 September 2026**; a daily update workflow is documented in [Automation](AUTOMATION.md).

The [gameplay glossary](GLOSSARY.md) explains **15 recurring terms**, starting with [level one cheese](GLOSSARY.md#level-one-cheese), then XP denial, wave control, cheater recalls, trading, priority and shroom setup. Each entry links to examples of Ramy using the concept. Editorial explanations stay separate from transcript wording, and patch-sensitive interactions such as the Dusk and Dawn trick are explicitly qualified.

## For search and future AI use

- [data/corpus.jsonl](data/corpus.jsonl): 8,191 passage records, including the explicit empty speech record for the visual guide. `text` is the corrected reading; `text_original` preserves the original machine transcript. Records also retain review flags, correction provenance, approximate timestamps and source hashes.
- [data/sources.jsonl](data/sources.jsonl): 158 video records with public source metadata, upload dates and 161 recorded matchup intervals across 64 opponents. Join it to the corpus using `video_id`.
- [data/visual-captions.jsonl](data/visual-captions.jsonl): 190 OCR caption groups from the on-screen guide, kept separate from speech.
- [data/visual-caption-checks.jsonl](data/visual-caption-checks.jsonl): six separately attributed assistant checks of visible wording and markers. These are not human review or verification of game mechanics.
- [SCHEMA.md](SCHEMA.md): field definitions and an example of reading the dataset with Python.
- [manifest.json](manifest.json): counts and SHA-256 hashes for the published files.

The large JSONL file is intended for downloading or cloning; GitHub's preview may truncate it. All reading, downloading and local search can use these saved files without model API calls. The repository contains text and metadata; original audio and video remain on the creator's channel.

## Accuracy and patch context

The spoken material is transcribed with OpenAI `gpt-transcribe`. Daily additions apply conservative spelling rules and carry an explicit automated-review flag; ambiguous names and matchups require further review. The reading layer includes **1,631 traceable terminology corrections across 1,183 passages**, including champion names, player names, items and the cheater recall concept. Original GPT wording and the exact correction spans are retained so readers can inspect those decisions. Seventeen detected terminology questions remain unresolved and are flagged; that count is not a claim that no other errors remain.

**These are machine transcripts, not a fully proofread or creator-approved script.** Speakers have not been reliably separated, so another speaker's dialogue should not automatically be attributed to RamyAura. A small, explicitly scoped human wording check is preserved separately from the surrounding machine text and from editorial gameplay interpretation.

**Recording patches are unknown. Upload dates do not establish the game patch.** Advice may depend on the version of Teemo, his opponent, items, runes, summoners, minions, vision and other systems. The dataset records historical commentary; it does not certify recommendations for the current patch. Retain the dates, uncertainty and applicability fields when using it in an AI system, and cite the original video for any claim.

Daily additions and some earlier uploads use **coarse source-audio chunk timestamps**, clearly marked on their transcript pages. These ranges can cover several minutes or a whole small audio file; they do not locate individual sentences. The mixed jungle/Shen transition chunk from 18 September remains outside the matchup intervals.

Passage times are approximate positions in the uploaded video, not the in-game clock or exact word timings. Matchup boundaries in multi-game uploads are conservative; transition passages remain in the full transcript. On-screen OCR and marker candidates must be checked against the video before drawing gameplay conclusions.

## Corrections and attribution

To report a correction, open an issue with the video URL, timestamp or passage ID, the existing wording and the proposed replacement. Please distinguish a transcription error from advice that became outdated after a patch. See [NOTICE.md](NOTICE.md) for the publication permission and attribution note.

This repository is maintained by `ivystopia`. It is a community transcript archive, not an official Riot Games project.

## Verify a downloaded copy

Python 3.10 or newer is sufficient; no third-party packages are needed.

```sh
python3 scripts/validate.py
```

The check verifies published file hashes, record counts, original/corrected text consistency, correction offsets, source joins, matchup links, quality metadata and the absence of known private archive fields or secret patterns. It does not measure transcription accuracy or validate gameplay advice.
