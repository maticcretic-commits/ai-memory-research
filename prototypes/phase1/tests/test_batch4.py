"""Batch 4 tests. Run: python3 -m unittest discover -s tests -v

Written before the implementations. Synthetic data only. No network,
no accounts, no credentials, no sending, no image or video generation,
no real records. A passing suite proves only that the prototypes behave
as specified on these fixtures. Character consistency is a check, not
a solved problem: the spec says so.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BRAND_RULES_V1 = {
    "version": 1,
    "name": "prototype-brand-rulebook-v1",
    "palette": ["#1A1A2E", "#E8B54D", "#FFFFFF"],
    "voice": "plain, direct, Hinglish",
    "forbidden_claims": ["guaranteed", "official partner", "number one"],
    "credit_rule": "credits in description only, never in frames",
}

SHEET = {
    "name": "Synthetic Aspirant",
    "description": "young student with glasses and a blue backpack",
    "reference_id": "ref-syn-001",
}


class TestWorkspaceAdapters(unittest.TestCase):
    def test_fetch_returns_synthetic_items_only(self):
        import workspace_adapters

        adapter = workspace_adapters.SyntheticAdapter(
            "synthetic-workspace",
            [{"id": "syn-1", "text": "synthetic meeting note"}],
        )
        items = adapter.fetch()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["text"], "synthetic meeting note")

    def test_to_draft_is_draft_only_never_sent(self):
        import workspace_adapters

        adapter = workspace_adapters.SyntheticAdapter(
            "synthetic-notion", [{"id": "syn-1", "text": "synthetic note"}]
        )
        draft = adapter.to_draft(adapter.fetch()[0])
        self.assertEqual(draft["kind"], "draft_only")
        self.assertFalse(draft["sent"])
        self.assertNotIn("send", draft)

    def test_fetch_does_not_mutate_stored_items(self):
        import workspace_adapters

        adapter = workspace_adapters.SyntheticAdapter(
            "synthetic-workspace", [{"id": "syn-1", "text": "synthetic note"}]
        )
        items = adapter.fetch()
        items[0]["text"] = "tampered"
        self.assertEqual(adapter.fetch()[0]["text"], "synthetic note")

    def test_unknown_adapter_rejected(self):
        import workspace_adapters

        registry = workspace_adapters.AdapterRegistry()
        with self.assertRaises(workspace_adapters.AdapterError):
            registry.get("no_such_adapter")

    def test_registry_lists_only_registered_names(self):
        import workspace_adapters

        registry = workspace_adapters.AdapterRegistry()
        registry.register(
            workspace_adapters.SyntheticAdapter("synthetic-workspace", [])
        )
        self.assertEqual(registry.list_adapters(), ["synthetic-workspace"])


class TestBrandRulebook(unittest.TestCase):
    def test_valid_asset_passes(self):
        import brand_rulebook

        result = brand_rulebook.check(
            BRAND_RULES_V1,
            {
                "text": "A plain synthetic caption.",
                "colours": ["#1A1A2E", "#E8B54D"],
                "credits_in_frame": False,
            },
        )
        self.assertTrue(result["passed"])
        self.assertEqual(result["violations"], [])

    def test_credits_in_frame_fails(self):
        import brand_rulebook

        result = brand_rulebook.check(
            BRAND_RULES_V1,
            {
                "text": "A synthetic caption.",
                "colours": ["#1A1A2E"],
                "credits_in_frame": True,
            },
        )
        self.assertFalse(result["passed"])
        self.assertIn("credits_in_frame", result["violations"])

    def test_forbidden_claim_fails(self):
        import brand_rulebook

        result = brand_rulebook.check(
            BRAND_RULES_V1,
            {
                "text": "This is guaranteed synthetic success.",
                "colours": ["#1A1A2E"],
                "credits_in_frame": False,
            },
        )
        self.assertFalse(result["passed"])
        self.assertIn("forbidden_claim", result["violations"])

    def test_off_palette_colour_fails(self):
        import brand_rulebook

        result = brand_rulebook.check(
            BRAND_RULES_V1,
            {
                "text": "A synthetic caption.",
                "colours": ["#FF00FF"],
                "credits_in_frame": False,
            },
        )
        self.assertFalse(result["passed"])
        self.assertIn("off_palette", result["violations"])

    def test_frozen_hash_detects_tampering(self):
        import brand_rulebook
        import copy

        frozen = brand_rulebook.freeze(BRAND_RULES_V1)
        tampered = copy.deepcopy(BRAND_RULES_V1)
        tampered["palette"].append("#FF00FF")
        self.assertFalse(brand_rulebook.verify_frozen(tampered, frozen["sha256"]))


class TestCharacterConsistency(unittest.TestCase):
    def test_matching_reference_and_description_passes(self):
        import character_consistency

        result = character_consistency.check_consistency(
            SHEET,
            {
                "description": "young student with glasses and a blue backpack, smiling",
                "reference_id": "ref-syn-001",
            },
        )
        self.assertTrue(result["consistent"])
        self.assertGreaterEqual(result["overlap"], 0.5)

    def test_different_reference_fails_even_with_similar_text(self):
        import character_consistency

        result = character_consistency.check_consistency(
            SHEET,
            {
                "description": "young student with glasses and a blue backpack",
                "reference_id": "ref-other-999",
            },
        )
        self.assertFalse(result["consistent"])
        self.assertIn("reference_mismatch", result["reasons"])

    def test_low_overlap_fails(self):
        import character_consistency

        result = character_consistency.check_consistency(
            SHEET,
            {
                "description": "elderly sailor with a red hat on a boat",
                "reference_id": "ref-syn-001",
            },
        )
        self.assertFalse(result["consistent"])
        self.assertIn("low_description_overlap", result["reasons"])

    def test_missing_reference_fails_closed(self):
        import character_consistency

        result = character_consistency.check_consistency(
            SHEET, {"description": "young student with glasses and a blue backpack"}
        )
        self.assertFalse(result["consistent"])

    def test_check_is_not_a_generation_claim(self):
        import character_consistency

        result = character_consistency.check_consistency(
            SHEET,
            {
                "description": "young student with glasses and a blue backpack",
                "reference_id": "ref-syn-001",
            },
        )
        self.assertIn("character consistency is not solved", result["note"])
        self.assertNotIn("generated", result)


if __name__ == "__main__":
    unittest.main()
