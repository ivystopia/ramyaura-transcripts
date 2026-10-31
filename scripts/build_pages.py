"""Build the public reader from the published corpus using only the standard library."""
import argparse
import json
import re
import shutil
from collections import defaultdict
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = 'https://github.com/ivystopia/ramyaura-transcripts/blob/main/'


def records(name):
    with (ROOT / 'data' / name).open() as stream:
        return [json.loads(line) for line in stream if line.strip()]


def recording_label(source):
    opponents = [encounter['name'] for encounter in source['encounters']]
    if len(opponents) == 1:
        return 'Teemo vs. ' + opponents[0]
    if opponents:
        return 'Games against ' + ' / '.join(opponents)
    return {'guide': 'Teemo strategy guide', 'visual_guide': 'Teemo visual guide',
            'unclassified': 'Matchup awaiting review'}.get(source['kind'], 'Teemo recording')


def in_encounter(passage, encounter):
    return passage['start_seconds'] >= encounter['start'] and passage['end_seconds'] <= encounter['end'] + .001


def build(destination):
    sources = records('sources.jsonl')
    passages = records('corpus.jsonl')
    by_key = {row['chunk_key']: row for row in passages}
    by_id = {row['video_id']: row for row in sources}
    grouped = defaultdict(list)
    for row in passages:
        if row['text'].strip():
            grouped[row['video_id']].append(row)

    catalog = []
    search = []
    for source in sources:
        video = source['video_id']
        encounters = []
        for encounter in source['encounters']:
            first = next(row for row in grouped[video] if in_encounter(row, encounter))
            encounters.append(dict(name=encounter['name'], role=encounter['role'], start=encounter['start'],
                                   end=encounter['end'], first=first['chunk_key']))
        item = dict(id=video, title=recording_label(source), date=source['upload_date'],
                    kind=source['kind'], encounters=encounters)
        if source['kind'] in {'guide', 'visual_guide'}:
            item['note'] = source['context']
        catalog.append(item)
        for row in grouped[video]:
            search.append(dict(id=video, key=row['chunk_key'], start=row['start_seconds'],
                               end=row['end_seconds'], text=row['text']))

    def reference(match):
        row = by_key[match[1]]
        source = by_id[row['video_id']]
        seconds = int(row['start_seconds'])
        encounter = next((e for e in source['encounters'] if in_encounter(row, e)), None)
        if encounter:
            label = 'Teemo vs. ' + encounter['name']
            if encounter['role'] != 'Lane unspecified':
                label += ' · ' + encounter['role']
        else:
            label = 'Matchup unassigned' if source['encounters'] else recording_label(source)
        transcript = REPO + source['transcript_path'] + '#p-' + row['chunk_key']
        return (f'<p class="ref">{escape(label)} · {source["upload_date"]}<br>'
                f'<a href="{source["url"]}&amp;t={seconds}s">Watch from {seconds//60}:{seconds%60:02d}</a>'
                f' · <a href="{transcript}">Read passage</a></p>')

    destination.mkdir(parents=True, exist_ok=True)
    for filename in ('style.css', 'library.js'):
        shutil.copyfile(ROOT / 'site' / filename, destination / filename)
    home = (ROOT / 'site/index.html').read_text()
    opponents = {e['name'] for s in catalog for e in s['encounters']}
    home = home.replace('{{videos}}', str(len(catalog))).replace('{{opponents}}', str(len(opponents)))
    (destination / 'index.html').write_text(home)
    study = re.sub(r'\{\{ref:([a-f0-9]{64})\}\}', reference, (ROOT / 'site/study.html').read_text())
    if '{{' in study:
        raise ValueError('Unresolved study reference')
    (destination / 'study.html').write_text(study)
    for name, value in [('catalog', catalog), ('passages', search)]:
        (destination / (name + '.json')).write_text(json.dumps(value, ensure_ascii=False, separators=(',', ':')))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination', type=Path)
    build(parser.parse_args().destination)
