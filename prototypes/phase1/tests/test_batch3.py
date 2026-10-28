"""Batch 3 tests. Run: python3 -m unittest discover -s tests -v

Written before the implementations. Synthetic data only. No network,
no accounts, no sending, no image or video generation, no real records.
A passing suite proves only that the prototypes behave as specified
on these fixtures.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

CORPUS = [
    {"id": "syn-a", "text": "synthetic dashboard for farm finance and crop sales"},
    {"id": "syn-b", "text": "synthetic recipe for lentil soup with spices"},
    {"id": "syn-c", "text": "synthetic farm finance report and dashboard summary"},
]


def _scene(title, caption, duration, source, licence):
    return {
        "title": title,
        "visual": "synthetic still image description",
        "caption": caption,
        "duration_s": duration,
        "source": source,
        "licence": licence,
    }


class TestRetrieval(unittest.TestCase):
    def test_exact_match_ranks_first_with_score(self):
        import retrieval

        results = retrieval.retrieve(CORPUS, "farm finance dashboard")
        self.assertEqual(results[0]["id"], "syn-c")
        self.assertGreater(results[0]["score"], 0)
        self.assertLessEqual(results[0]["score"], 1.0)

    def test_no_match_returns_zero_scores_in_order(self):
        import retrieval

        results = retrieval.retrieve(CORPUS, "quantum saxophone")
        self.assertTrue(all(r["score"] == 0 for r in results))
        self.assertEqual([r["id"] for r in results], ["syn-a", "syn-b", "syn-c"])

    def test_empty_query_rejected(self):
        import retrieval

        with self.assertRaises(retrieval.RetrievalError):
            retrieval.retrieve(CORPUS, "  ")

    def test_scores_are_surfaced_not_used_as_permission(self):
        import retrieval

        results = retrieval.retrieve(CORPUS, "lentil soup")
        self.assertEqual(len(results), 3)
        self.assertIn("score", results[0])
        self.assertEqual(results[0]["id"], "syn-b")

    def test_corpus_not_mutated(self):
        import copy
        import retrieval

        before = copy.deepcopy(CORPUS)
        retrieval.retrieve(CORPUS, "farm")
        self.assertEqual(CORPUS, before)


class TestClarifyingLoop(unittest.TestCase):
    def test_high_confidence_no_missing_proceeds(self):
        import clarifying_loop

        loop = clarifying_loop.ClarifyingLoop("synthetic task", 0.97, [])
        decision = loop.decide()
        self.assertEqual(decision["decision"], "proceed")

    def test_missing_field_asks_one_question(self):
        import clarifying_loop

        loop = clarifying_loop.ClarifyingLoop("synthetic task", 0.97, ["budget", "deadline"])
        decision = loop.decide()
        self.assertEqual(decision["decision"], "ask")
        self.assertIn("budget", decision["question"])

    def test_answer_fills_field_then_proceeds(self):
        import clarifying_loop

        loop = clarifying_loop.ClarifyingLoop("synthetic task", 0.97, ["budget"])
        decision = loop.answer("fictional budget")
        self.assertEqual(decision["decision"], "proceed")
        self.assertEqual(loop.fields["budget"], "fictional budget")

    def test_three_questions_then_escalate_never_proceed(self):
        import clarifying_loop

        loop = clarifying_loop.ClarifyingLoop(
            "synthetic task", 0.5, ["a", "b", "c"]
        )
        for value in ("1", "2", "3"):
            decision = loop.answer(value)
        self.assertEqual(decision["decision"], "escalate")
        self.assertNotEqual(decision["decision"], "proceed")

    def test_low_confidence_asks_before_proceeding(self):
        import clarifying_loop

        loop = clarifying_loop.ClarifyingLoop("synthetic task", 0.5, [])
        decision = loop.decide()
        self.assertEqual(decision["decision"], "ask")


class TestStoryboard(unittest.TestCase):
    def test_valid_spec_builds_with_credits(self):
        import storyboard

        spec = storyboard.build(
            [
                _scene("Open", "A synthetic morning.", 8, "synthetic-source-1", "CC0"),
                _scene("Close", "A synthetic evening.", 6, "synthetic-source-2", "CC-BY"),
            ]
        )
        self.assertEqual(spec["scene_count"], 2)
        self.assertEqual(spec["total_duration_s"], 14)
        self.assertEqual(len(spec["credits"]), 2)
        self.assertIn("synthetic-source-1", spec["credits"][0]["source"])

    def test_missing_licence_rejected(self):
        import storyboard

        with self.assertRaises(storyboard.StoryboardError):
            storyboard.build([_scene("Open", "A synthetic morning.", 8, "synthetic-source-1", "")])

    def test_overlong_caption_rejected(self):
        import storyboard

        with self.assertRaises(storyboard.StoryboardError):
            storyboard.build(
                [_scene("Open", "x" * 121, 8, "synthetic-source-1", "CC0")]
            )

    def test_total_duration_over_sixty_rejected(self):
        import storyboard

        with self.assertRaises(storyboard.StoryboardError):
            storyboard.build(
                [
                    _scene("A", "Synthetic one.", 15, "s1", "CC0"),
                    _scene("B", "Synthetic two.", 15, "s1", "CC0"),
                    _scene("C", "Synthetic three.", 15, "s1", "CC0"),
                    _scene("D", "Synthetic four.", 15, "s1", "CC0"),
                    _scene("E", "Synthetic five.", 15, "s1", "CC0"),
                ]
            )

    def test_spec_is_text_only_no_media(self):
        import storyboard

        spec = storyboard.build(
            [_scene("Open", "A synthetic morning.", 8, "synthetic-source-1", "CC0")]
        )
        self.assertNotIn("image", spec)
        self.assertNotIn("video", spec)
        self.assertEqual(spec["render_plan"][0]["kind"], "text_description")


class TestCoreWorkflow(unittest.TestCase):
    def test_item_flows_through_four_stages(self):
        import core_workflow

        pipe = core_workflow.CorePipeline()
        record = pipe.capture("synthetic dashboard request")
        record = pipe.organise(record)
        record = pipe.review(record, confidence=0.9)
        record = pipe.engage(record)
        self.assertEqual(
            [s["stage"] for s in record["audit"]],
            ["capture", "organise", "review", "engage"],
        )
        self.assertEqual(record["provenance"]["source"], "synthetic")

    def test_low_confidence_goes_to_review_queue_not_engage(self):
        import core_workflow

        pipe = core_workflow.CorePipeline()
        record = pipe.capture("synthetic vague request")
        record = pipe.organise(record)
        record = pipe.review(record, confidence=0.4)
        self.assertEqual(record["status"], "in_review_queue")
        with self.assertRaises(core_workflow.CoreError):
            pipe.engage(record)

    def test_engage_output_is_draft_only(self):
        import core_workflow

        pipe = core_workflow.CorePipeline()
        record = pipe.capture("synthetic dashboard request")
        record = pipe.organise(record)
        record = pipe.review(record, confidence=0.9)
        record = pipe.engage(record)
        self.assertEqual(record["action"]["kind"], "draft_only")
        self.assertFalse(record["action"]["sent"])

    def test_organise_assigns_category_from_keywords(self):
        import core_workflow

        pipe = core_workflow.CorePipeline()
        record = pipe.organise(pipe.capture("synthetic farm finance dashboard"))
        self.assertEqual(record["category"], "finance")


class TestMasterPrompt(unittest.TestCase):
    def _conventions(self):
        import conventions
        from fixtures import CONVENTIONS_V1

        frozen = conventions.freeze(CONVENTIONS_V1)
        return CONVENTIONS_V1, frozen["sha256"]

    def test_valid_prompt_builds(self):
        import master_prompt

        _doc, sha = self._conventions()
        prompt = master_prompt.build(
            role="synthetic assistant",
            task="synthetic summary",
            conventions_sha256=sha,
            style_guide_version="v1",
        )
        self.assertIn("synthetic summary", prompt["text"])
        self.assertIn(sha, prompt["text"])

    def test_missing_slot_rejected(self):
        import master_prompt

        _doc, sha = self._conventions()
        with self.assertRaises(master_prompt.MasterPromptError):
            master_prompt.build(
                role="",
                task="synthetic summary",
                conventions_sha256=sha,
                style_guide_version="v1",
            )

    def test_hash_mismatch_rejected(self):
        import master_prompt

        with self.assertRaises(master_prompt.MasterPromptError):
            master_prompt.build(
                role="synthetic assistant",
                task="synthetic summary",
                conventions_sha256="0" * 64,
                style_guide_version="v1",
            )

    def test_no_unfilled_placeholders_remain(self):
        import master_prompt

        _doc, sha = self._conventions()
        prompt = master_prompt.build(
            role="synthetic assistant",
            task="synthetic summary",
            conventions_sha256=sha,
            style_guide_version="v1",
        )
        self.assertNotIn("{role}", prompt["text"])
        self.assertNotIn("{task}", prompt["text"])
        self.assertNotIn("{conventions_sha256}", prompt["text"])


if __name__ == "__main__":
    unittest.main()
