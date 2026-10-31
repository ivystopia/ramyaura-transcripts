"""Keep the published reader linked to the correct game and transcript passage."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import build_pages


class ReaderTests(unittest.TestCase):
    def test_second_game_in_the_linked_recording(self):
        with tempfile.TemporaryDirectory() as folder:
            site = Path(folder)
            build_pages.build(site)
            catalog = json.loads((site / 'catalog.json').read_text())
            video = next(v for v in catalog if v['id'] == '-QCM7ZLOu1Q')
            self.assertEqual([(e['name'], e['start']) for e in video['encounters']],
                             [('Jayce', 0), ('Darius', 1164)])
            reader = (site / 'transcripts' / (video['id'] + '.html')).read_text()
            second = video['encounters'][1]
            self.assertIn('watch?v=-QCM7ZLOu1Q&amp;t=1164s', reader)
            self.assertIn(f'id="p-{second["first"]}"', reader)
            passages = json.loads((site / 'passages.json').read_text())
            first_full = next(p for p in passages if p['key'] == second['first'])
            self.assertGreaterEqual(first_full['start'], second['start'])
            self.assertIn('Game 2 · Darius · Top', reader)

    def test_recordings_without_an_opponent_keep_their_title(self):
        source = {'title': 'Playing the opening wave', 'kind': 'unclassified', 'encounters': []}
        self.assertEqual(build_pages.recording_label(source), source['title'])
