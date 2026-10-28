"""Phase 1 Batch 1 tests. Run: python3 -m unittest discover -s tests -v

Written before the implementations. Synthetic data only. No network,
no sending, no real records. A passing suite proves only that the
prototypes behave as specified on these fixtures.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fixtures import CONVENTIONS_V1, INBOX_MESSAGES, PROMPTS_SEED


class TestConventions(unittest.TestCase):
    def test_valid_output_passes(self):
        import conventions
        result = conventions.check(
            CONVENTIONS_V1,
            "Build synthetic dashboard",
            "- Context: one synthetic requirement.\n- Owner: synthetic.",
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])

    def test_title_without_allowed_verb_fails(self):
        import conventions
        result = conventions.check(CONVENTIONS_V1, "Maybe later", "- Context: x.")
        self.assertFalse(result["passed"])
        self.assertIn("title_verb", result["violations"])

    def test_missing_bullet_fails(self):
        import conventions
        result = conventions.check(CONVENTIONS_V1, "Review synthetic draft", "No bullets here.")
        self.assertFalse(result["passed"])
        self.assertIn("context_bullets", result["violations"])

    def test_secret_word_rejected(self):
        import conventions
        result = conventions.check(
            CONVENTIONS_V1, "Check synthetic record", "- api_key: hunter2"
        )
        self.assertFalse(result["passed"])
        self.assertIn("no_secrets", result["violations"])

    def test_frozen_hash_detects_tampering(self):
        import conventions
        import copy
        import hashlib
        import json

        frozen = conventions.freeze(CONVENTIONS_V1)
        tampered = copy.deepcopy(CONVENTIONS_V1)
        tampered["allowed_verbs"].append("Delete")
        self.assertFalse(conventions.verify_frozen(tampered, frozen["sha256"]))

    def test_no_network_imports(self):
        import pathlib

        src = pathlib.Path(__file__).parent.parent.joinpath("conventions.py").read_text()
        for banned in ("requests", "urllib", "socket", "smtplib"):
            self.assertNotIn(banned, src)


class TestPromptsDb(unittest.TestCase):
    def test_add_and_search(self):
        import prompts_db

        db = prompts_db.PromptsDb()
        for entry in PROMPTS_SEED:
            self.assertEqual(db.add(entry)["outcome"], "admitted")
        found = db.search(use_case="weekly_review")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["id"], "syn-001")

    def test_exact_duplicate_is_not_a_new_version(self):
        import prompts_db

        db = prompts_db.PromptsDb()
        db.add(PROMPTS_SEED[0])
        result = db.add(PROMPTS_SEED[0])
        self.assertEqual(result["outcome"], "duplicate")
        self.assertEqual(len(db.all_versions("syn-001")), 1)

    def test_supersede_keeps_old_record_sealed(self):
        import prompts_db

        db = prompts_db.PromptsDb()
        db.add(PROMPTS_SEED[0])
        updated = dict(PROMPTS_SEED[0])
        updated["text"] = "Summarise this week's synthetic notes into two actions."
        result = db.supersede("syn-001", updated)
        self.assertEqual(result["outcome"], "admitted")
        versions = db.all_versions("syn-001")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["text"], PROMPTS_SEED[0]["text"])
        self.assertTrue(versions[0]["superseded"])

    def test_secret_content_rejected(self):
        import prompts_db

        db = prompts_db.PromptsDb()
        bad = dict(PROMPTS_SEED[0])
        bad["id"] = "syn-003"
        bad["text"] = "Use this api_key: hunter2"
        self.assertEqual(db.add(bad)["outcome"], "rejected")

    def test_missing_required_field_rejected(self):
        import prompts_db

        db = prompts_db.PromptsDb()
        bad = dict(PROMPTS_SEED[0])
        del bad["use_case"]
        self.assertEqual(db.add(bad)["outcome"], "rejected")


class TestInboxClassifier(unittest.TestCase):
    def test_fixture_labels(self):
        import inbox_classifier

        correct = 0
        for msg in INBOX_MESSAGES:
            result = inbox_classifier.classify(msg["subject"], msg["body"])
            if result["label"] == msg["expected"]:
                correct += 1
        # Report the count honestly: 8/8 on these hand-built fixtures.
        self.assertEqual(correct, 8, f"correct={correct}/8")

    def test_uncertain_goes_to_review_not_auto_label(self):
        import inbox_classifier

        result = inbox_classifier.classify(
            "Mixed synthetic message",
            "Hello, I need help and also a quote, and here is a newsletter link.",
        )
        self.assertEqual(result["label"], "review")
        self.assertEqual(result["action"], "draft_for_review")

    def test_output_is_never_a_send(self):
        import inbox_classifier

        for msg in INBOX_MESSAGES:
            result = inbox_classifier.classify(msg["subject"], msg["body"])
            self.assertNotIn("send", (result["action"], result["label"]))
            self.assertIn(result["action"], ("label_only", "draft_for_review"))


if __name__ == "__main__":
    unittest.main()
