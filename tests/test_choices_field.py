"""choices — the first-class field for questions an agent could not decide alone.

Covers the write-side normalizer. The loose input shapes are deliberate (the
field has no schema and agents improvise), so the normalizer is what keeps the
stored documents readable by Inventorium's src/utils/todoChoices.js, which
tolerates the same forms.
"""
import unittest

from Omnispindle.tools import _normalize_choices


class TestNormalizeChoices(unittest.TestCase):

    def test_returns_none_for_nothing_to_store(self):
        self.assertIsNone(_normalize_choices(None))
        self.assertIsNone(_normalize_choices([]))
        self.assertIsNone(_normalize_choices({"q": "not a list"}))
        self.assertIsNone(_normalize_choices(42))

    def test_accepts_a_json_string(self):
        out = _normalize_choices('[{"q": "A?", "options": ["Yes", "No"]}]')
        self.assertEqual(len(out), 1)
        self.assertEqual([o["label"] for o in out[0]["options"]], ["Yes", "No"])

    def test_malformed_json_string_stores_nothing(self):
        self.assertIsNone(_normalize_choices("{not json"))

    def test_question_aliases(self):
        out = _normalize_choices([{"q": "A?"}, {"question": "B?"}, {"prompt": "C?"}])
        self.assertEqual([c["q"] for c in out], ["A?", "B?", "C?"])

    def test_entries_without_a_question_are_dropped(self):
        self.assertIsNone(_normalize_choices([{"options": ["a"]}, {"q": "   "}, "nope"]))

    def test_ids_are_assigned_positionally_when_missing(self):
        out = _normalize_choices([{"q": "A?"}, {"q": "B?", "id": "custom"}])
        self.assertEqual([c["id"] for c in out], ["q1", "custom"])

    def test_bare_string_options_become_labelled_options(self):
        out = _normalize_choices([{"q": "A?", "options": ["Yes", "No"]}])
        self.assertEqual(out[0]["options"], [
            {"id": "a", "label": "Yes"},
            {"id": "b", "label": "No"},
        ])

    def test_option_label_and_detail_aliases(self):
        out = _normalize_choices([{"q": "A?", "options": [
            {"id": "x", "label": "Labelled", "detail": "why"},
            {"text": "Texted", "description": "because"},
            {"value": "Valued"},
            {"label": "   "},
            "  ",
        ]}])
        self.assertEqual(out[0]["options"], [
            {"id": "x", "label": "Labelled", "detail": "why"},
            {"id": "b", "label": "Texted", "detail": "because"},
            {"id": "c", "label": "Valued"},
        ])

    def test_optional_keys_are_omitted_rather_than_stored_empty(self):
        # Mongo strips nulls on write, so an absent key is how "unanswered" is
        # spelled — writing answer=None would only look different, never read
        # different, and the readers would have to handle two spellings.
        out = _normalize_choices([{"q": "A?", "answer": None, "recommended": "b"}])
        self.assertEqual(sorted(out[0].keys()), ["id", "options", "q", "recommended"])

    def test_answers_and_credits_survive(self):
        out = _normalize_choices([{
            "q": "A?",
            "options": ["Yes"],
            "answer": "free text answer",
            "answered_by": "dan@example.com",
            "answered_at": "2026-09-23T21:07:00.732Z",
        }])
        self.assertEqual(out[0]["answer"], "free text answer")
        self.assertEqual(out[0]["answered_by"], "dan@example.com")
        self.assertEqual(out[0]["answered_at"], "2026-09-23T21:07:00.732Z")

    def test_option_ids_wrap_past_the_alphabet(self):
        out = _normalize_choices([{"q": "A?", "options": [f"opt{i}" for i in range(27)]}])
        self.assertEqual(out[0]["options"][26]["id"], "a")


if __name__ == "__main__":
    unittest.main()
