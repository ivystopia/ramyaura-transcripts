"""Offline regression checks for curated meanings and source provenance."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import concept_search as cs


class ConceptSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dataset = cs.load()

    def results(self, query, all_classifications=False):
        return cs.search(self.dataset, query, all_classifications)["results"]

    def test_tempo_excludes_rune_and_unclear_all_in_sentence(self):
        results = self.results("tempo")
        self.assertEqual(len(results), 10)
        self.assertTrue(any(r["annotation"]["chunk_key"].startswith("d2442134") for r in results))
        self.assertFalse(any("lethal tempo" in r["evidence"]["excerpt"].casefold() for r in results))
        self.assertFalse(any(r["annotation"]["chunk_key"].startswith("93e917f7") for r in results))
        self.assertEqual({r["annotation"]["classification"] for r in self.results("tempo", True)}, {"supports", "exclude", "unresolved"})

    def test_rune_occurrences_have_distinct_spans(self):
        matches = [r for r in self.results("lethal tempo") if r["evidence"]["video_id"] == "VmGVaa-kf1s"]
        self.assertEqual(len(matches), 2)
        self.assertNotEqual(matches[0]["annotation"]["span"], matches[1]["annotation"]["span"])
        self.assertTrue(all(r["evidence"]["excerpt"].casefold() == "lethal tempo" for r in matches))

    def test_weakside_aliases_and_jungle_context(self):
        expected = self.results("weakside")
        self.assertEqual(len(expected), 5)
        for alias in ["weak side", "weak-side", " WEAK SIDE "]:
            self.assertEqual(self.results(alias), expected)
        jungle = next(r for r in expected if r["evidence"]["video_id"] == "RP0IuAQqdrE")
        self.assertEqual(jungle["evidence"]["encounters"], [{"opponent": "Fizz", "role": "Jungle"}])

    def test_shadowing_excludes_tooltips_lane_side_and_item_passive(self):
        matches = self.results("hover")
        self.assertEqual({r["evidence"]["video_id"] for r in matches}, {"bJvJnIzkc-8", "x9i6jBai9D8"})
        excluded = [r for r in self.results("shadow", True) if r["annotation"]["classification"] == "exclude"]
        self.assertTrue(any(r["evidence"]["video_id"] == "rCccxk2PyLs" for r in excluded))
        self.assertTrue(any(r["evidence"]["video_id"] == "SULBrVIR3XQ" for r in excluded))
        self.assertTrue(any(r["evidence"]["video_id"] == "h1vlNhOBIjs" for r in excluded))

    def test_related_passage_keeps_item_qualification(self):
        match = next(r for r in self.results("recall") if r["annotation"]["chunk_key"].startswith("f85ab67a"))
        self.assertEqual(len(match["context"]), 1)
        self.assertTrue(match["context"][0]["chunk_key"].startswith("2499e4f7"))
        self.assertIn("off tempo", match["context"][0]["excerpt"])
        self.assertIn("Not resolved", match["annotation"]["decision"]["chosen_action"])

    def test_aliases_do_not_create_unreviewed_matches(self):
        self.assertEqual(self.results("prio"), self.results("priority"))
        self.assertEqual(cs.resolve(self.dataset[0], "shove")["id"], "fast-push")
        self.assertEqual(cs.resolve(self.dataset[0], "crash")["id"], "crash")
        self.assertNotEqual(self.results("shove"), self.results("crash"))
        with self.assertRaisesRegex(ValueError, "Unknown concept"):
            self.results("100-0 trade")

    def validate_modified(self, annotations=None, passages=None, sources=None):
        c, a, p, s = self.dataset
        cs.validate(c, a if annotations is None else annotations, p if passages is None else passages,
                    s if sources is None else sources, (cs.ROOT / "GLOSSARY.md").read_text())

    def test_changed_text_invalidates_old_annotations(self):
        passages = dict(self.dataset[2])
        key = self.dataset[1][0]["chunk_key"]
        passages[key] = dict(passages[key], text=passages[key]["text"] + " changed")
        with self.assertRaisesRegex(ValueError, "Stale"):
            self.validate_modified(passages=passages)

    def test_span_cannot_point_outside_the_passage(self):
        annotations = copy.deepcopy(self.dataset[1])
        annotations[0]["span"] = [0, 10**9]
        with self.assertRaisesRegex(ValueError, "span outside"):
            self.validate_modified(annotations=annotations)

    def test_external_channel_cannot_supply_evidence(self):
        sources = copy.deepcopy(self.dataset[3])
        key = self.dataset[1][0]["chunk_key"]
        video = self.dataset[2][key]["video_id"]
        sources[video]["channel_id"] = "unapproved-channel"
        with self.assertRaisesRegex(ValueError, "published RamyAura channel"):
            self.validate_modified(sources=sources)

    def test_context_cannot_come_from_another_video(self):
        annotations = copy.deepcopy(self.dataset[1])
        video = self.dataset[2][annotations[0]["chunk_key"]]["video_id"]
        other = next(k for k, p in self.dataset[2].items() if p["video_id"] != video)
        annotations[0]["context_keys"] = [other]
        annotations[0]["context_text_sha256"] = {other: self.dataset[2][other]["text_sha256"]}
        with self.assertRaisesRegex(ValueError, "continuation"):
            self.validate_modified(annotations=annotations)

    def test_changed_continuation_invalidates_its_interpretation(self):
        annotations = copy.deepcopy(self.dataset[1])
        item = next(a for a in annotations if a["concept_id"] == "shadowing" and a["context_keys"])
        passages = dict(self.dataset[2])
        key = item["context_keys"][0]
        passages[key] = dict(passages[key], text=passages[key]["text"] + " changed")
        with self.assertRaisesRegex(ValueError, "Stale continuation"):
            self.validate_modified(annotations=annotations, passages=passages)

    def test_annotation_cannot_embed_an_extra_transcript_field(self):
        annotations = copy.deepcopy(self.dataset[1])
        annotations[0]["transcript"] = "Unexpected source material"
        with self.assertRaisesRegex(ValueError, "Unexpected editorial annotation fields"):
            self.validate_modified(annotations=annotations)


if __name__ == "__main__":
    unittest.main()
