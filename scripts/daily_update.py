"""Maintain this transcript edition from the maintainer's existing processing archive.

No language-model agent runs here. Paid work is restricted to the archive's
explicit GPT transcription client and its persistent cumulative cost ledger.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import fcntl
import hashlib
import html
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

REMOTE = 'git@github.com:ivystopia/ramyaura-transcripts.git'
SAFE_RULES = {
    'champion-Naafiri-000', 'champion-Xerath-003', 'champion-Skarner-004',
    'champion-Cassiopeia-007', 'champion-Kassadin-008', 'champion-KSante-009',
    'champion-Sejuani-011', 'champion-XinZhao-012', 'champion-Tryndamere-016',
    'champion-Illaoi-019', 'champion-Wukong-022', 'champion-Veigar-024',
    'item-3041-040', 'item-2504-041', 'item-3137-042', 'item-4645-043',
    'item-3155-044', 'item-1052-045', 'player-Crownie-046', 'player-SkewMond-048',
    'player-BrokenBlade-049', 'expanded-Naafiri', 'expanded-RekSai',
    'expanded-MonkeyKing', 'expanded-Gangplank', 'expanded-Lissandra',
    'expanded-3157', 'expanded-4645', 'expanded-3077', 'expanded-1082',
    'item-leandry', 'item-nashers', 'rune-electricute', 'concept-cheater-recall',
}


def utc():
    return datetime.now(timezone.utc).isoformat()


def read(path):
    return json.loads(Path(path).read_text())


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + '.')
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        Path(tmp).unlink(missing_ok=True)


def jsonl(path, records):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records))


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def require(value, message):
    if not value:
        raise RuntimeError(message)


def require_complete_batch(result):
    if result['state'] == 'complete':
        return
    errors = [item.get('errors', {}).get('api', {}).get('message', '')
              for item in result.get('items', [])]
    for message in errors:
        if re.search(r'\b(?:insufficient_quota|insufficient_credits|billing_hard_limit_reached|billing_limit_reached)\b', message, re.I):
            raise RuntimeError('OpenAI credits or API quota exhausted. Paid transcription stopped; check your API credit balance and project spending limit. No top-up was made. Saved progress is retained.')
        if 'Local spending cap reached' in message:
            raise RuntimeError('The approved cumulative transcription spending cap has been reached. Paid transcription stopped; no top-up or budget increase was made. Saved progress is retained.')
    raise RuntimeError('Batch incomplete; checkpoints retained for the next attempt')


def command(args, cwd=None, timeout=180):
    env = dict(os.environ, GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        # Never print signed download URLs, request bodies or credential values.
        raise RuntimeError(f'{Path(str(args[0])).name} failed (exit {result.returncode}); inspect local state. No force push or credential prompt was attempted.')
    return result.stdout.strip()


def git(repo, *args):
    return command(['git', '-c', 'commit.gpgsign=false', '-c', 'core.sshCommand=ssh -o BatchMode=yes -o ConnectTimeout=20', '-C', repo, *args])


def load_script(archive, name):
    spec = importlib.util.spec_from_file_location('ramyaura_job_' + name, archive / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def select_new(inventory, published, channel):
    seen = set()
    result = []
    for item in inventory:
        identifier = item['video_id']
        require(re.fullmatch(r'[A-Za-z0-9_-]{11}', identifier), 'Invalid inventory video ID')
        require(identifier not in seen, 'Duplicate inventory video ID')
        seen.add(identifier)
        require(item['channel_id'] == channel and item['source_tab'] == 'videos', 'Wrong channel or source tab')
        if identifier in published:
            continue
        require(isinstance(item.get('duration_seconds'), (int, float)) and math.isfinite(item['duration_seconds']) and item['duration_seconds'] > 0, 'New upload duration unavailable; retry after publication completes')
        result.append(item)
    return result


def classify_safely(source, passages, reference):
    from ramyaura.library import classify
    first = (source.get('description') or '').split('\n')[0]
    names = [name for name in reference.mentions(first) if name != 'Teemo']
    multi = len(names) != 1 or len(re.findall(r'\bvs\.?\b', first, re.I)) != 1
    if not multi:
        result = classify(source, passages, reference, {})
        if len(result['encounters']) == 1 and result['encounters'][0]['role'] != 'Lane unspecified':
            result['context'] = 'Automated classification from the saved description; not independently verified against gameplay.'
            return result
    return {'kind': 'unclassified', 'context': 'Matchup or multi-game boundaries require review. No opponent has been guessed.', 'encounters': []}


def prepare_reading(archive, batch):
    from ramyaura.library import ASSETS
    from ramyaura.riot_reference import RiotReference
    from ramyaura.terminology import Terminology, apply_corrections, text_hash
    export = archive / 'data/exports' / batch
    manifest = read(export / 'manifest.json')
    for name, entry in manifest['files'].items():
        require(sha(export / name) == entry['sha256'], 'Audited export changed')
    reference = RiotReference(archive / 'data/library/champions', ASSETS / 'champion-aliases.json')
    lexicon = Terminology(ASSETS, reference, archive / 'data/exports/regular-uploads/manifest.json')
    processed = []
    grouped = defaultdict(list)
    for row in rows(export / 'corpus.jsonl'):
        require(row['text'].strip(), 'An empty speech response needs source review before automatic publication')
        proposed = lexicon.corrections(row)
        edits = [edit for edit in proposed if edit['rule_id'] in SAFE_RULES]
        uncertain = [dict(api=e['original'], start=e['start'], end=e['end'], target='Possible ' + e['replacement'] + '; needs contextual review before correction.') for e in proposed if e['rule_id'] not in SAFE_RULES]
        text = apply_corrections(row['text'], edits)
        row = dict(row, text=text, text_original=row['text'], text_sha256=text_hash(text),
                   terminology_corrections=edits, terminology_uncertainties=uncertain,
                   text_status='terminology_normalized_machine_transcript', source_chunk_key=row['chunk_key'],
                   quality_flags=list(dict.fromkeys(row['quality_flags'] + ['automated_ingestion_not_editorially_reviewed'])))
        processed.append(row)
        grouped[row['source']['video_id']].append(row)
    index = []
    for entry in rows(export / 'sources.jsonl'):
        source = entry['source']
        index.append(dict(video_id=source['video_id'], **classify_safely(source, grouped[source['video_id']], reference)))
    destination = archive / 'data/reading' / batch
    destination.mkdir(parents=True, exist_ok=True)
    jsonl(destination / 'corpus.jsonl', processed)
    write(destination / 'matchup-index.json', {'videos': index})
    write(destination / 'manifest.json', {
        'batch': batch, 'created_at': utc(), 'corpus_sha256': sha(destination / 'corpus.jsonl'),
        'matchup_index_sha256': sha(destination / 'matchup-index.json'),
        'source_export_manifest_sha256': sha(export / 'manifest.json'),
        'correction_count': sum(len(r['terminology_corrections']) for r in processed),
        'corrected_passages': sum(bool(r['terminology_corrections']) for r in processed),
        'unresolved_terminology_candidates': sum(len(r['terminology_uncertainties']) for r in processed),
        'scope': 'Automatic spelling rules only; no per-passage editorial or audio review.',
    })
    return destination


def render_indexes(repo, sources, passages):
    def md(value):
        return re.sub(r'([\\`*\[\]_])', r'\\\1', html.escape(str(value), quote=False))
    def tc(value):
        n = int(value)
        return f'{n//3600}:{n//60%60:02}:{n%60:02}' if n >= 3600 else f'{n//60:02}:{n%60:02}'
    grouped = defaultdict(list)
    for row in passages:
        grouped[row['video_id']].append(row)
    listing = ['# All transcripts', '', f'{len(sources)} regular uploads, newest publication first. Dates are upload dates; recording patches remain unknown. [Browse by matchup](MATCHUPS.md).', '']
    matchups = defaultdict(list)
    others = []
    for source in sources:
        names = '; '.join(e['name'] + ' (' + e['role'] + ')' for e in source['encounters'])
        label = names or ('Matchup awaiting review' if source['kind'] == 'unclassified' else 'General guide')
        listing.append(f"- {source['upload_date']} — [{md(source['title'])}]({source['transcript_path']}) — {md(label)}.")
        if not source['encounters']:
            others.append(source)
        for e in source['encounters']:
            candidates = [r for r in grouped[source['video_id']] if r['start_seconds'] >= e['start'] and r['end_seconds'] <= e['end'] + .001 and r['text'].strip()]
            require(candidates, 'Matchup has no wholly contained source passage')
            matchups[e['name']].append((source, e, candidates[0]['chunk_key']))
    (repo / 'TRANSCRIPTS.md').write_text('\n'.join(listing) + '\n')
    anchor = lambda name: 'matchup-' + re.sub('[^a-z0-9]+', '-', name.lower()).strip('-')
    out = ['# Browse by matchup', '', 'Recorded opponents and roles, with links into the relevant transcript. These are source classifications, not matchup difficulty rankings or current-patch recommendations. Multi-game uploads use conservative passage boundaries; transition passages remain in the full transcript.', '', '[All transcripts](TRANSCRIPTS.md) · [Dataset notes](README.md)', '', ' · '.join(f'[{md(name)}](#{anchor(name)})' for name in sorted(matchups)), '']
    for name in sorted(matchups):
        out += ['', f'<a id="{anchor(name)}"></a>', '', '## ' + md(name), '']
        for source, e, key in matchups[name]:
            out.append(f"- {source['upload_date']} · **{md(e['role'])}** · [{md(source['title'])}]({source['transcript_path']}#p-{key}) · video {tc(e['start'])}–{tc(e['end'])}.")
    out += ['', '## General guides and matchups awaiting review', '']
    out += [f"- {s['upload_date']} — [{md(s['title'])}]({s['transcript_path']})" + (' — matchup awaiting review.' if s['kind'] == 'unclassified' else '.') for s in others]
    (repo / 'MATCHUPS.md').write_text('\n'.join(out) + '\n')


def counts(sources, passages, captions, checks):
    return dict(videos=len(sources), passage_records=len(passages), nonempty_spoken_passages=sum(bool(r['text'].strip()) for r in passages),
                videos_with_spoken_text=len({r['video_id'] for r in passages if r['text'].strip()}), audio_hours=round(sum(s['decoded_duration_seconds'] for s in sources) / 3600, 8),
                terminology_corrections=sum(len(r['terminology_corrections']) for r in passages), corrected_passages=sum(bool(r['terminology_corrections']) for r in passages),
                known_unresolved_terminology_candidates=sum(len(r['terminology_uncertainties']) for r in passages), visual_caption_groups=len(captions), assistant_visual_checks=len(checks),
                matchup_encounters=sum(len(s['encounters']) for s in sources), opponents=len({e['champion_id'] for s in sources for e in s['encounters']}))


def update_readme(text, c, latest, today):
    substitutions = [
        (r'\*\*[\d,]+ regular YouTube uploads', f"**{c['videos']} regular YouTube uploads"),
        (r'\*\*[\d.]+ hours\*\*', f"**{c['audio_hours']:.2f} hours**"),
        (r'contains \d+ videos with detected speech', f"contains {c['videos_with_spoken_text']} videos with detected speech"),
        (r'Collection last updated on \*\*.*?\*\*, including regular uploads published through \*\*.*?\*\*[;.][^\n]+', f'Collection last updated on **{today}**, including regular uploads published through **{latest}**. New regular uploads are checked daily at 06:00 Europe/London; see [Automation](AUTOMATION.md).'),
        (r'[\d,]+ passage records, including', f"{c['passage_records']:,} passage records, including"),
        (r'\d+ video records with public source metadata, upload dates and \d+ recorded matchup intervals across \d+ opponents', f"{c['videos']} video records with public source metadata, upload dates and {c['matchup_encounters']} recorded matchup intervals across {c['opponents']} opponents"),
        (r'\*\*[\d,]+ traceable terminology corrections across [\d,]+ passages\*\*', f"**{c['terminology_corrections']:,} traceable terminology corrections across {c['corrected_passages']:,} passages**"),
        (r'(?:Seventeen|Eight|\d+) detected terminology questions', f"{c['known_unresolved_terminology_candidates']} detected terminology questions"),
    ]
    for pattern, replacement in substitutions:
        text, n = re.subn(pattern, replacement, text)
        require(n == 1, 'README format changed; publication stopped to preserve editorial content')
    return text


def merge_publication(repo, fresh, batch, archive):
    old_sources, old_rows = rows(repo / 'data/sources.jsonl'), rows(repo / 'data/corpus.jsonl')
    new_sources, new_rows = rows(fresh / 'data/sources.jsonl'), rows(fresh / 'data/corpus.jsonl')
    require(not ({r['video_id'] for r in old_sources} & {r['video_id'] for r in new_sources}), 'Overlapping publication batches')
    require(not ({r['chunk_key'] for r in old_rows} & {r['chunk_key'] for r in new_rows}), 'Repeated publication passage')
    sources = sorted(old_sources + new_sources, key=lambda r: (r['upload_date'], r['video_id']), reverse=True)
    order = {s['video_id']: i for i, s in enumerate(sources)}
    passages = sorted(old_rows + new_rows, key=lambda r: (order[r['video_id']], r['start_seconds'], r['chunk_key']))
    # Existing records and transcript pages are not regenerated.
    jsonl(repo / 'data/sources.jsonl', sources)
    jsonl(repo / 'data/corpus.jsonl', passages)
    for source in new_sources:
        shutil.copyfile(fresh / source['transcript_path'], repo / source['transcript_path'])
    render_indexes(repo, sources, passages)
    c = counts(sources, passages, rows(repo / 'data/visual-captions.jsonl'), rows(repo / 'data/visual-caption-checks.jsonl'))
    latest = max(s['upload_date'] for s in sources)
    today = utc()[:10]
    p = repo / 'README.md'
    p.write_text(update_readme(p.read_text(), c, latest, today))
    manifest = read(repo / 'manifest.json')
    manifest.update(counts=c, publication_updated_at=utc(), upload_date_range=[min(s['upload_date'] for s in sources), latest],
                    source_snapshot=f'Regular uploads checked {today}; automated daily additions, excluding livestreams and Shorts.')
    manifest.setdefault('input_batches', {})[batch] = {
        'export_manifest_sha256': sha(archive / 'data/exports' / batch / 'manifest.json'),
        'reading_manifest_sha256': sha(archive / 'data/reading' / batch / 'manifest.json'),
    }
    if 'input_sha256' in manifest:
        manifest['baseline_input_sha256'] = manifest.pop('input_sha256')
    manifest['input_provenance_note'] = 'Baseline input hashes describe the previously published edition; input_batches records the baseline and subsequent additions. Existing public text and editorial decisions are preserved.'
    write(repo / 'manifest.json', manifest)
    return c


def resume_push(repo, state, journal):
    commit = state['commit']
    require(not git(repo, 'status', '--porcelain'), 'Managed checkout has unexpected changes')
    require(git(repo, 'rev-parse', 'HEAD') == commit, 'Managed HEAD differs from pending publication')
    git(repo, 'fetch', 'origin', 'main')
    remote = git(repo, 'rev-parse', 'origin/main')
    if remote != commit:
        require(remote == state['base'], 'Remote changed during publication; preserve both changes and inspect before retrying')
        git(repo, 'push', 'origin', 'HEAD:main')
    require(git(repo, 'ls-remote', 'origin', 'refs/heads/main').split()[0] == commit, 'Remote publication verification failed')
    state.update(phase='complete', completed_at=utc())
    write(journal, state)
    return {'state': 'published', 'commit': commit, 'new_videos': state['videos']}


def run(archive, execute=False):
    sys.path.insert(0, str(archive / 'src'))
    from ramyaura import audit, batch as batch_module, bundle, media
    from ramyaura.common import Config, digest
    from ramyaura.state import Ledger
    config = Config.load(archive / 'ramyaura-batch.toml')
    config = Config(config.root, dict(config.values, local_comparison=False))
    directory = config.data / 'automation'
    directory.mkdir(parents=True, exist_ok=True)
    journal = directory / 'active.json'
    with (directory / 'daily.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return {'state': 'already_running'}
        repo = directory / 'repository'
        if not repo.exists():
            command(['git', '-c', 'core.sshCommand=ssh -o BatchMode=yes -o ConnectTimeout=20', 'clone', '--branch', 'main', REMOTE, repo])
        require(git(repo, 'remote', 'get-url', 'origin') == REMOTE, 'Unexpected publication remote')
        state = read(journal) if journal.exists() else None
        if state and state['phase'] == 'push_pending':
            return resume_push(repo, state, journal) if execute else {'state': 'push_pending', 'commit': state['commit']}
        if state and state['phase'] == 'installing':
            # Only a clean, exact old tree or our exact staged snapshot is recoverable.
            head = git(repo, 'rev-parse', 'HEAD')
            if head != state['base']:
                require(git(repo, 'log', '-1', '--format=%B').endswith('Batch: ' + state['batch']), 'Unexpected commit during publication recovery')
                require(git(repo, 'rev-parse', 'HEAD^') == state['base'], 'Unexpected publication parent')
                require(set(git(repo, 'diff', '--name-only', state['base'], 'HEAD').splitlines()) == set(state['files']), 'Unexpected committed publication files')
                require(all(sha(repo / name) == expected for name, expected in state['files'].items()), 'Committed publication differs from staged snapshot')
                state.update(phase='push_pending', commit=head)
                write(journal, state)
                return resume_push(repo, state, journal) if execute else {'state': 'push_pending', 'commit': head}
            require(execute, 'Publication installation is pending; execute to resume')
            return install_and_push(repo, state, journal)
        require(not git(repo, 'status', '--porcelain'), 'Managed checkout has unexpected changes; refusing to overwrite them')
        git(repo, 'fetch', 'origin', 'main')
        git(repo, 'merge', '--ff-only', 'origin/main')
        require(git(repo, 'rev-parse', 'HEAD') == git(repo, 'rev-parse', 'origin/main'), 'Unexpected unpublished commits in managed checkout')
        command([sys.executable, repo / 'scripts/validate.py'])
        published = {s['video_id'] for s in rows(repo / 'data/sources.jsonl')}
        if state and state['phase'] == 'processing':
            plan_path = config.data / 'batches' / state['batch'] / 'plan.json'
            plan = read(plan_path)
            ids = {r['video_id'] for r in plan['selection']}
            require(not (ids & published), 'Pending batch overlaps published sources; inspect reconciliation')
            require(state['config_sha256'] == sha(archive / 'ramyaura-batch.toml'), 'Configuration changed during a pending paid batch')
        else:
            inventory = media.inventory(config)
            selection = select_new(rows(inventory['path']), published, config['channel_id'])
            if not selection:
                return {'state': 'no_new_videos', 'published_videos': len(published), 'checked_at': utc()}
            name = 'uploads-' + utc()[:10] + '-' + digest(sorted(r['video_id'] for r in selection))[:8]
            seconds = sum(r['duration_seconds'] for r in selection)
            plan = dict(schema_version=1, name=name, created_at=utc(), channel_id=config['channel_id'], source_tab='videos',
                        selection=selection, selection_sha256=digest(selection), videos=len(selection), known_audio_hours=seconds/3600,
                        estimated_api_cost=config.prices(config.cost(seconds)), cumulative_api_cap_usd=float(config['max_total_spend_usd']),
                        scope_note='Only previously unpublished regular uploads; no streams or Shorts.')
            plan_path = config.data / 'batches' / name / 'plan.json'
            state = dict(phase='processing', batch=name, videos=len(selection), config_sha256=sha(archive / 'ramyaura-batch.toml'), started_at=utc())
        ledger = Ledger(config.data / 'ledger.sqlite')
        try:
            before = ledger.total()
        finally:
            ledger.close()
        # The ledger enforces the cap before every paid request. Do not block
        # publication of already cached responses when the budget is exhausted.
        require(shutil.disk_usage(archive).free >= float(config['min_free_disk_gib'])*2**30, 'Free disk reserve reached')
        print(json.dumps({'batch': plan['name'], 'new_videos': plan['videos'], 'estimated_api_cost': plan['estimated_api_cost'], 'cumulative_reserved_usd': before/1e6}), flush=True)
        if not execute:
            return {'state': 'planned', 'new_videos': plan['videos'], 'batch': plan['name']}
        if not plan_path.exists():
            write(plan_path, plan)
        write(journal, state)
        result = batch_module.run_batch(config, plan_path, max_cost='30', limit=plan['videos'], progress=lambda s: print(s, flush=True))
        require_complete_batch(result)
        report = audit.audit_batch(config, batch_name=plan['name'], progress=lambda s: print(s, flush=True))
        write(plan_path.parent / 'audit.json', report)
        require(report['status'] == 'passed', 'Archive audit failed; nothing published')
        bundle.export_bundle(config, batch_name=plan['name'])
        reading = prepare_reading(archive, plan['name'])
        stage = Path(tempfile.mkdtemp(prefix=plan['name'] + '-', dir=directory))
        inputs = stage / 'inputs'
        for folder in ['data/reading/regular-uploads', 'data/exports/regular-uploads', 'data/library']:
            (inputs / folder).mkdir(parents=True, exist_ok=True)
        for name in ['corpus.jsonl', 'manifest.json']:
            shutil.copyfile(reading / name, inputs / 'data/reading/regular-uploads' / name)
        for name in ['sources.jsonl', 'visual-captions.jsonl', 'visual-caption-checks.jsonl']:
            shutil.copyfile(config.data / 'exports' / plan['name'] / name, inputs / 'data/exports/regular-uploads' / name)
        shutil.copyfile(reading / 'matchup-index.json', inputs / 'data/library/matchup-index.json')
        fresh = stage / 'fresh'
        load_script(archive, 'export_public_transcripts').export(inputs, fresh)
        # Refresh the remote before composing the addition, preserving concurrent edits.
        git(repo, 'fetch', 'origin', 'main')
        git(repo, 'merge', '--ff-only', 'origin/main')
        require(not git(repo, 'status', '--porcelain'), 'Managed checkout changed during transcription')
        base = git(repo, 'rev-parse', 'HEAD')
        staged = stage / 'publication'
        shutil.copytree(repo, staged, ignore=shutil.ignore_patterns('.git', '__pycache__'))
        c = merge_publication(staged, fresh, plan['name'], archive)
        command([sys.executable, staged / 'scripts/validate.py', '--update-manifest'])
        command([sys.executable, staged / 'scripts/validate.py'])
        files = {str(p.relative_to(staged)): sha(p) for p in staged.rglob('*') if p.is_file() and '__pycache__' not in p.parts and (not (repo/p.relative_to(staged)).exists() or sha(repo/p.relative_to(staged)) != sha(p))}
        allowed = {'README.md', 'TRANSCRIPTS.md', 'MATCHUPS.md', 'manifest.json', 'data/corpus.jsonl', 'data/sources.jsonl'} | {s['transcript_path'] for s in rows(fresh/'data/sources.jsonl')}
        require(set(files) <= allowed, 'Publication attempted to change an unrelated file')
        state.update(phase='installing', base=base, staged=str(staged), files=files, counts=c,
                     previous_files={name: sha(repo/name) if (repo/name).exists() else None for name in files})
        write(journal, state)  # Write before touching the managed checkout.
        return install_and_push(repo, state, journal)


def install_and_push(repo, state, journal):
    require(git(repo, 'rev-parse', 'HEAD') == state['base'], 'Publication base changed')
    changed = set(git(repo, 'diff', '--name-only', 'HEAD').splitlines()) | set(git(repo, 'ls-files', '--others', '--exclude-standard').splitlines())
    require(changed <= set(state['files']), 'Concurrent changes outside the publication snapshot')
    for name, expected in state['files'].items():
        target, source = repo / name, Path(state['staged']) / name
        require(sha(source) == expected, 'Staged publication changed')
        actual = sha(target) if target.exists() else None
        require(actual in {expected, state['previous_files'][name]}, 'Concurrent change to a publication file')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    command([sys.executable, repo / 'scripts/validate.py'])
    git(repo, 'add', '--', *sorted(state['files']))
    git(repo, 'diff', '--cached', '--check')
    require(set(git(repo, 'diff', '--cached', '--name-only').splitlines()) == set(state['files']), 'Staged changes differ from reviewed publication')
    print('Reviewed staged publication:\n' + git(repo, 'diff', '--cached', '--stat'), flush=True)
    git(repo, 'commit', '-m', f"Add {state['videos']} new RamyAura uploads\n\nBatch: {state['batch']}")
    state.update(phase='push_pending', commit=git(repo, 'rev-parse', 'HEAD'))
    write(journal, state)
    return resume_push(repo, state, journal)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--execute', action='store_true', help='Permit budgeted transcription and publication; otherwise discovery only')
    args = parser.parse_args()
    archive = args.archive.expanduser().resolve()
    sys.path.insert(0, str(archive / 'src'))
    from ramyaura.batch import notify_phone, safe_error
    started = utc()
    try:
        result = run(archive, args.execute)
        if result['state'] != 'already_running':
            write(archive / 'data/automation/last-run.json', dict(started_at=started, finished_at=utc(), **result))
        print(json.dumps(result, indent=2), flush=True)
        if result['state'] == 'published':
            notify_phone(f"RamyAura: published {result['new_videos']} new videos. https://github.com/ivystopia/ramyaura-transcripts")
    except Exception as exc:
        message = safe_error(exc)
        failure = dict(started_at=started, finished_at=utc(), state='failed', error=message)
        write(archive / 'data/automation/last-run.json', failure)
        print('RamyAura daily update failed: ' + message, file=sys.stderr, flush=True)
        if args.execute:
            failure['phone_notification_sent'] = notify_phone('RamyAura daily update needs attention: ' + message[:250])
            write(archive / 'data/automation/last-run.json', failure)
            if not failure['phone_notification_sent']:
                print('KDE Connect could not send the phone alert; failure details remain in last-run.json.', file=sys.stderr, flush=True)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
