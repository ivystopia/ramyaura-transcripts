"""Build the public reader from the published corpus using only the standard library."""
import argparse
import json
import re
import shutil
from collections import defaultdict
from datetime import date
from html import escape
from math import ceil
from pathlib import Path
from string import Template

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
        return 'Teemo vs. ' + ', '.join(opponents[:-1]) + ', then ' + opponents[-1]
    return source['title']


def in_encounter(passage, encounter):
    return passage['start_seconds'] >= encounter['start'] and passage['end_seconds'] <= encounter['end'] + .001


def clock(seconds):
    return f'{int(seconds)//60}:{int(seconds)%60:02}'


def paragraphs(text):
    """Break long audio chunks for reading without changing the transcript wording."""
    for line in text.strip().splitlines():
        buffer = []
        length = 0
        for sentence in re.split(r'(?<=[.!?])\s+', line.strip()):
            if not sentence:
                continue
            buffer.append(sentence)
            length += len(sentence)
            if length >= 420:
                yield ' '.join(buffer)
                buffer, length = [], 0
        if buffer:
            yield ' '.join(buffer)


def render_transcript(template, source, item, passages, captions, frame_notes):
    video_url = escape(source['url'])
    chapter_list = []
    game_headings = {}
    for number, e in enumerate(item['encounters'], 1):
        role = ' · ' + escape(e['role']) if e['role'] else ''
        if len(item['encounters']) > 1:
            game_headings[e['first']] = f'<h3>Game {number} · {escape(e["name"])}{role}</h3>'
        chapter_list.append(
            f'<li><strong>{escape(e["name"])}{role}</strong> · '
            f'<a href="{video_url}&amp;t={ceil(e["start"])}s">Watch from {clock(ceil(e["start"]))}</a> · '
            f'<a href="#p-{e["first"]}">Read from the first full passage</a></li>')
    chapters = '<nav class="chapters" aria-label="Games in this video"><h2>Games in this video</h2><ol>' + ''.join(chapter_list) + '</ol></nav>' if len(chapter_list) > 1 else ''
    blocks = []
    for r in passages:
        start = ceil(r['start_seconds'])
        body = ''.join(f'<p>{escape(p)}</p>' for p in paragraphs(r['text']))
        key = r['chunk_key']
        blocks.append(
            f'<div class="passage" id="p-{key}"><div class="passage-links">'
            f'<a href="{video_url}&amp;t={start}s" aria-label="Watch from {clock(start)}">{clock(start)}</a> '
            f'<a class="permalink" href="#p-{key}" aria-label="Link to passage at {clock(start)}">Link</a></div>'
            f'<div>{game_headings.get(key, "")}{body}</div></div>')
    kind, section_name = 'Recording', 'Transcript'
    note = 'Machine transcript of the commentary. Select a time to hear the passage in the original video.'
    if any('coarse_api_chunk_timing' in r['quality_flags'] for r in passages):
        note += ' Each timestamp can cover several minutes of speech.'
    if source['kind'] == 'visual_guide':
        kind, section_name = 'Visual guide', 'On-screen captions'
        note = 'This guide uses on-screen text. Select a time to watch that part of the demonstration.'
        for frame in frame_notes:
            start = frame['source_time_seconds']
            blocks.append(f'<div class="passage"><a href="{video_url}&amp;t={start}s">{clock(start)}</a><p>{escape(frame["text"])}</p></div>')
        blocks.append('<details><summary>All captions from the video</summary><p>These captions were read automatically from the screen. Some words may repeat or be misread.</p>')
        for c in captions:
            start = int(c['start_seconds'])
            blocks.append(f'<div class="passage"><a href="{video_url}&amp;t={start}s" aria-label="Watch from {clock(start)}">{clock(start)}</a><p>{escape(c["text"])}</p></div>')
        blocks.append('</details>')
    elif source['kind'] == 'guide':
        kind = 'Video guide'
    published = date.fromisoformat(source['upload_date'])
    title = escape(source['title'])
    label = escape(item['title'])
    return template.substitute(
        label=label, description=f'{section_name} of RamyAura’s video, {title}.', kind=kind,
        date=source['upload_date'], display_date=f'{published.day} {published:%B %Y}',
        original_title=f'<p>{title}</p>' if title != label else '', video_url=video_url,
        duration=clock(source['decoded_duration_seconds']), source_url=escape(REPO + source['transcript_path']),
        chapters=chapters, section_name=section_name, note=note, passages='\n'.join(blocks))


def build(destination):
    sources = records('sources.jsonl')
    passages = records('corpus.jsonl')
    by_key = {row['chunk_key']: row for row in passages}
    by_id = {row['video_id']: row for row in sources}
    grouped = defaultdict(list)
    for row in passages:
        if row['text'].strip():
            grouped[row['video_id']].append(row)

    captions = defaultdict(list)
    for row in records('visual-captions.jsonl'):
        captions[row['video_id']].append(row)
    frame_notes = defaultdict(list)
    for row in records('visual-caption-checks.jsonl'):
        frame_notes[row['video_id']].append(row)
    template = Template((ROOT / 'site/transcript.html').read_text())
    reader = destination / 'transcripts'
    reader.mkdir(parents=True, exist_ok=True)
    catalog = []
    search = []
    for source in sources:
        video = source['video_id']
        encounters = []
        for encounter in source['encounters']:
            first = next(row for row in grouped[video] if in_encounter(row, encounter))
            role = '' if encounter['role'] == 'Lane unspecified' else encounter['role']
            encounters.append(dict(name=encounter['name'], role=role, start=encounter['start'],
                                   end=encounter['end'], first=first['chunk_key']))
        item = dict(id=video, title=recording_label(source), date=source['upload_date'],
                    encounters=encounters)
        if source['kind'] == 'visual_guide':
            item['visual'] = True
        catalog.append(item)
        (reader / f'{video}.html').write_text(render_transcript(template, source, item, grouped[video], captions[video], frame_notes[video]))
        for row in grouped[video]:
            search.append(dict(id=video, key=row['chunk_key'], start=row['start_seconds'],
                               end=row['end_seconds'], text=row['text']))

    def reference(match):
        row = by_key[match[1]]
        source = by_id[row['video_id']]
        seconds = ceil(row['start_seconds'])
        encounter = next((e for e in source['encounters'] if in_encounter(row, e)), None)
        if encounter:
            label = 'Teemo vs. ' + encounter['name']
            if encounter['role'] != 'Lane unspecified':
                label += ' · ' + encounter['role']
        else:
            label = recording_label(source)
        transcript = f'./transcripts/{source["video_id"]}.html#p-{row["chunk_key"]}'
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
