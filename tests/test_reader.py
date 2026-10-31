"""Keep the published reader linked to the correct game and transcript passage."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_pages


class ReaderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = tempfile.TemporaryDirectory()
        cls.addClassCleanup(folder.cleanup)
        cls.site = Path(folder.name)
        build_pages.build(cls.site)
        cls.catalog = json.loads((cls.site / 'catalog.json').read_text())
        cls.passages = {p['key']: p for p in json.loads((cls.site / 'passages.json').read_text())}

    def test_second_game_in_the_linked_recording(self):
        video = next(v for v in self.catalog if v['id'] == '-QCM7ZLOu1Q')
        self.assertEqual([(e['name'], e['start']) for e in video['encounters']],
                         [('Jayce', 0), ('Darius', 1164)])
        reader = (self.site / 'transcripts' / (video['id'] + '.html')).read_text()
        self.assertIn('watch?v=-QCM7ZLOu1Q&amp;t=1164s', reader)
        self.assertIn('Game 2 · Darius · Top', reader)

    def test_each_catalog_game_opens_a_passage_inside_that_game(self):
        sources = {s['video_id']: s for s in build_pages.records('sources.jsonl')}
        self.assertCountEqual([v['id'] for v in self.catalog], list(sources))
        for video in self.catalog:
            with self.subTest(video=video['id']):
                source = sources[video['id']]
                reader = (self.site / 'transcripts' / (video['id'] + '.html')).read_text()
                games = video['encounters']
                self.assertEqual([(g['name'], g['start'], g['end']) for g in games],
                                 [(e['name'], e['start'], e['end']) for e in source['encounters']])
                if not games:
                    self.assertEqual(video['title'], source['title'])
                for game in games:
                    self.assertIn(game['name'], video['title'])
                    self.assertNotEqual(game['role'], 'Lane unspecified')
                    passage = self.passages[game['first']]
                    self.assertEqual(passage['id'], video['id'])
                    self.assertGreaterEqual(passage['start'], game['start'])
                    self.assertLessEqual(passage['end'], game['end'] + .001)
                    self.assertIn(f'id="p-{game["first"]}"', reader)

    def test_recordings_without_an_opponent_keep_their_title(self):
        source = {'title': 'Playing the opening wave', 'kind': 'unclassified', 'encounters': []}
        self.assertEqual(build_pages.recording_label(source), source['title'])
