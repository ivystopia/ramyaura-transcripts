# Daily updates

The maintainer’s PC checks RamyAura’s regular YouTube uploads at **06:00 Europe/London**. The schedule follows UK daylight-saving changes. If the PC is off or suspended, a missed run is caught up when the user service becomes available; the job does not wake or power on the PC. Livestreams and Shorts are excluded.

## What happens

1. Acquire a single-run lock, refresh a dedicated Git checkout and validate the published edition.
2. Compare channel video IDs with the published source catalogue. With no new uploads, finish without a transcription request or commit.
3. Freeze a resumable batch, archive its original audio and playable video, and transcribe with `gpt-transcribe`. Successful responses are reused. Requests with an uncertain outcome require inspection before another paid attempt.
4. Apply a conservative subset of the existing spelling rules. Context-dependent alternatives are flagged instead of silently substituted. Automatic additions are labelled `automated_ingestion_not_editorially_reviewed`; original GPT text remains available.
5. Add a matchup only when the saved description names one opponent and a lane. Ambiguous or multiple-game uploads remain available under **matchup awaiting review** until their intervals can be reviewed. Upload dates do not establish recording patches.
6. Build the addition in a staging directory, preserving existing transcripts, glossary entries and editorial decisions. Validate text hashes, correction offsets, source joins, links, counts and publication privacy checks.
7. Inspect the staged file set and diff, make an **unsigned commit**, push without force, and verify the remote revision. A failed push can resume without transcribing again. Concurrent changes stop publication for inspection rather than being overwritten.

The workflow keeps the original **$30 cumulative transcription ceiling**, including earlier runs, and a **20 GiB free-space reserve**. It does not buy credit or enable top-ups. Exhaustion stops paid work and triggers a notification; continuing requires an explicit budget decision. Local search, validation and publication do not make model calls.

New transcript timestamps identify the submitted audio chunks, which may cover several minutes or an entire small audio file. They are not sentence-level timings. The process does not automatically revise the gameplay glossary or turn historical advice into current-patch recommendations.

## Operation

This public repository is the text edition. The scheduled runner also requires the maintainer’s existing processing archive, installed Python environment, saved source/reference data and cost ledger. Credentials stay in that archive’s ignored configuration and the local Git credential setup; they are not published here. The archive is passed explicitly with `--archive`.

```sh
# Discover and estimate only; no paid requests or publication.
python scripts/daily_update.py --archive /path/to/processing-archive

# Execute a resumable update within the existing cumulative budget.
python scripts/daily_update.py --archive /path/to/processing-archive --execute

# Inspect the installed schedule and recent output.
systemctl --user status ramyaura-daily.timer ramyaura-daily.service
journalctl --user -u ramyaura-daily.service -n 80 --no-pager

# Run manually or pause the schedule.
systemctl --user start ramyaura-daily.service
systemctl --user disable --now ramyaura-daily.timer
```

The timer uses `OnCalendar=*-*-* 06:00:00 Europe/London`, `Persistent=true` and no randomized delay. The processing archive’s `data/automation/last-run.json` records the last outcome, `active.json` records unfinished work, and `repository/` is the dedicated publication checkout. A separate lock prevents overlapping invocations. Successful additions and errors are reported through KDE Connect; no-change runs are quiet. Inspect the journal and saved state if the phone is unreachable.

A separate personal checkout is not modified by the scheduled job. Pull from GitHub there when you want the newly published files. Do not remove the cost ledger or source checkpoints to resolve an error; that would lose the information needed for safe cache reuse and spending enforcement.
