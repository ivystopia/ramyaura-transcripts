"""Regression checks using the chapter formats found in RamyAura's uploads."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from daily_update import game_chapter_claims


class GameChapterTests(unittest.TestCase):
    roster = {name: {'name': name} for name in ('Jayce', 'Darius', 'Sylas')}
    passages = [
        {'text': 'first game', 'start_seconds': 0, 'end_seconds': 599},
        {'text': 'both games', 'start_seconds': 599, 'end_seconds': 1200},
        {'text': 'second game', 'start_seconds': 1200, 'end_seconds': 2244},
    ]

    def claims(self, chapters):
        return game_chapter_claims(chapters, 2244, self.passages, self.roster)

    def test_creator_chapter_sets_the_game_start_inside_a_mixed_passage(self):
        chapters = ['0:00 Game 1 vs Jayce', '19:24 Game 2 vs Darius top']
        claims = self.claims(chapters)
        self.assertEqual([(c['champion'], c['role'], c['start'], c['end']) for c in claims],
                         [('Jayce', 'Lane unspecified', 0, 1164), ('Darius', 'Top', 1164, 2244)])
        self.assertEqual([c['metadata_text'] for c in claims], chapters)

    def test_incomplete_or_unusable_chapters_need_an_editor(self):
        for last in ('19:44 Game 2 Teemo Jungle', '19:44 Game 3 vs Sylas',
                     '0:00 Game 2 vs Sylas', '49:44 Game 2 vs Sylas', '1:00 Game 2 vs Sylas'):
            with self.subTest(chapter=last):
                self.assertEqual(self.claims(['0:00 Game 1 vs Darius top', last]), [])
        self.assertEqual(self.claims(['0:00 Game 1 vs Darius top']), [])
