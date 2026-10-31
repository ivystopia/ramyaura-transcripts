'use strict';

const opponent = document.getElementById('opponent');
const query = document.getElementById('query');
const results = document.getElementById('results');
const label = document.getElementById('results-label');
const more = document.getElementById('more');
const clear = document.getElementById('clear');
const repo = 'https://github.com/ivystopia/ramyaura-transcripts/blob/main/transcripts/';
const pageSize = 12;
let catalog = [];
let videos = new Map();
let passageLoad;
let revision = 0;
let limit = pageSize;

function element(tag, content, className) {
  const node = document.createElement(tag);
  if (content !== undefined) node.textContent = content;
  if (className) node.className = className;
  return node;
}

function link(text, href) {
  const node = element('a', text);
  node.href = href;
  return node;
}

function timestamp(seconds) {
  const start = Math.floor(seconds);
  return Math.floor(start / 60) + ':' + String(start % 60).padStart(2, '0');
}

function encounterFor(video, passage) {
  return video.encounters.find(e => passage.start >= e.start && passage.end <= e.end + 0.001);
}

function excerpt(text, at, length) {
  const p = element('p');
  const start = Math.max(0, at - 85);
  const end = Math.min(text.length, at + length + 120);
  p.append((start ? '…' : '') + text.slice(start, at), element('mark', text.slice(at, at + length)),
           text.slice(at + length, end) + (end < text.length ? '…' : ''));
  return p;
}

function entry(video, encounter, passage, at, length) {
  const node = element('article', undefined, 'entry');
  let matchup = encounter ? [encounter.name, encounter.role].join(' · ') : '';
  if (!matchup && !passage) matchup = video.encounters.map(e => e.name).join(' / ');
  if (!matchup) matchup = video.kind === 'unclassified' ? 'Matchup awaiting review' : 'Full recording';
  const time = passage ? passage.start : (encounter?.start ?? 0);
  const key = passage?.key ?? encounter?.first;
  const transcript = repo + video.id + '.md' + (key ? '#p-' + key : '');
  const meta = element('div', video.date + '  /  ' + matchup, 'meta');
  if (passage) meta.append(' · Passage ' + timestamp(passage.start) + '–' + timestamp(passage.end));
  const title = element('h3');
  title.append(link(video.title, transcript));
  node.append(meta, title);
  if (passage) node.append(excerpt(passage.text, at, length));
  const links = element('div', undefined, 'links');
  links.append(link('Watch from ' + timestamp(time), 'https://www.youtube.com/watch?v=' + video.id + '&t=' + Math.floor(time) + 's'),
               link(passage ? 'Read full passage' : 'Read transcript', transcript));
  node.append(links);
  return node;
}

async function loadJSON(name) {
  const response = await fetch('./' + name + '.json');
  if (!response.ok) throw new Error('Could not load ' + name);
  return response.json();
}

function updateURL() {
  const url = new URL(location.href);
  for (const [key, value] of [['opponent', opponent.value], ['q', query.value.trim()]]) {
    if (value) url.searchParams.set(key, value);
    else url.searchParams.delete(key);
  }
  history.replaceState(null, '', url);
}

async function render() {
  const current = ++revision;
  const needle = query.value.trim().toLowerCase();
  const selected = opponent.value;
  clear.hidden = !needle && !selected;
  more.hidden = true;
  const fragment = document.createDocumentFragment();
  let count = 0;
  if (needle) {
    if (!passageLoad) {
      results.replaceChildren();
      label.textContent = 'Loading transcript text…';
      passageLoad = loadJSON('passages').catch(error => { passageLoad = undefined; throw error; });
    }
    let passages;
    try { passages = await passageLoad; }
    catch {
      if (current === revision) showError();
      return;
    }
    if (current !== revision) return;
    for (const passage of passages) {
      const video = videos.get(passage.id);
      const encounter = encounterFor(video, passage);
      if (selected && encounter?.name !== selected) continue;
      const at = passage.text.toLowerCase().indexOf(needle);
      if (at < 0) continue;
      if (++count <= limit) fragment.append(entry(video, encounter, passage, at, needle.length));
    }
  } else {
    for (const video of catalog) {
      const games = selected ? video.encounters.filter(e => e.name === selected) : [video.encounters.length === 1 ? video.encounters[0] : null];
      for (const encounter of games) {
        if (++count <= limit) fragment.append(entry(video, encounter));
      }
    }
  }
  const noun = needle ? 'passage' : (selected ? 'game' : 'recording');
  label.textContent = count.toLocaleString() + ' ' + noun + (count === 1 ? '' : 's') + (selected ? ' · ' + selected : '');
  if (!count) fragment.append(element('p', 'No matches. Try a shorter phrase or choose another opponent.'));
  results.replaceChildren(fragment);
  more.hidden = count <= limit;
  if (!more.hidden) more.textContent = 'Show ' + Math.min(pageSize, count - limit) + ' more';
}

function showError() {
  label.textContent = 'The archive could not be loaded.';
  const p = element('p');
  p.append('Reload this page or ', link('browse transcripts on GitHub', 'https://github.com/ivystopia/ramyaura-transcripts/blob/main/TRANSCRIPTS.md'), '.');
  results.replaceChildren(p);
}

function filter() {
  limit = pageSize;
  updateURL();
  render();
}

async function start() {
  try { catalog = await loadJSON('catalog'); }
  catch { showError(); return; }
  videos = new Map(catalog.map(v => [v.id, v]));
  const names = [...new Set(catalog.flatMap(v => v.encounters.map(e => e.name)))].sort((a, b) => a.localeCompare(b));
  names.forEach(name => opponent.add(new Option(name, name)));
  const params = new URLSearchParams(location.search);
  opponent.value = names.includes(params.get('opponent')) ? params.get('opponent') : '';
  query.value = params.get('q') ?? query.value;
  opponent.addEventListener('change', filter);
  query.addEventListener('input', filter);
  clear.addEventListener('click', () => { opponent.value = ''; query.value = ''; filter(); query.focus(); });
  more.addEventListener('click', () => { limit += pageSize; render(); });
  document.getElementById('filters').addEventListener('submit', event => { event.preventDefault(); filter(); });
  render();
}
start();
