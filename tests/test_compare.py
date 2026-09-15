import json
import tempfile
import unittest
from pathlib import Path

from musicreader.compare import (
    compare_text,
    normalize_for_compare,
    reference_from_hymns_json,
    section_order,
)


class CompareTests(unittest.TestCase):
    def test_normalization_removes_ccli_noise_and_engraving_hyphens(self) -> None:
        self.assertEqual(
            normalize_for_compare(
                "Worthy Of Worship (Judson)\nVerse 1\n"
                "Worthy of the off'rings we bring.\nCCLI Song # 12345"
            ),
            "worthy of the offerings we bring",
        )

    def test_compare_accepts_formatting_only_differences(self) -> None:
        result = compare_text(
            "1. Worthy of worship, worthy of praise.\nChorus: You are worthy!",
            "WORTHY OF WORSHIP worthy of praise\n\nChorus\nYou are worthy!",
        )
        self.assertTrue(result.matches)
        self.assertGreaterEqual(result.score, 0.92)

    def test_compare_uses_fuzzy_order_independent_word_score(self) -> None:
        extracted = (
            "1. Worthy of worship, worthy of praise, Worthy of honor and glo ry; "
            "Worthy of all the glad songs we can sing, Worthy of all jo the off-'rings we bring. "
            "2. Worthy y of e nnn ar, Worthy of love and devo tion; "
            "Worthy of bowing and bending of knees, Worthy of all this and added to these... "
            "3. Almighty Father, Master a and Lord, King of all kings and Redeem er, "
            "Wonderful Counselor, Comforter, Friend, Savior and Source of our life without end. "
            "Chorus You are worthy, Father, CreYou are worthy, Savior, Sustainer. "
            "You are worthy, worthy and wonderful; Worthy of worship and praise."
        )
        reference = (
            "Worthy Of Worship (Judson)\n"
            "Verse 1 Worthy of worship, worthy of praise, Worthy of honor and glory; "
            "Worthy of all the glad songs we can sing, Worthy of all of the offerings we bring.\n"
            "Verse 2 Worthy of reverence, worthy of fear, Worthy of love and devotion; "
            "Worthy of bowing and bending of knees, Worthy of all this and added to these...\n"
            "Verse 3 Almighty Father, Master and Lord, King of all kings and Redeemer, "
            "Wonderful Counselor, Comforter, Friend, Savior and Source of our life without end.\n"
            "Chorus You are worthy, Father, Creator. You are worthy, Savior, Sustainer. "
            "You are worthy, worthy and wonderful; Worthy of worship and praise.\n"
            "CCLI Song # 123\n© 1988 Van Ness Press, Inc."
        )
        result = compare_text(extracted, reference)
        self.assertTrue(result.matches)
        self.assertGreaterEqual(result.score, 0.9)

    def test_sheet_image_is_preferred_to_number(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hymns.json"
            path.write_text(
                json.dumps(
                    [
                        {"Number": 3, "SheetImage": "99.jpg", "cclilyrcs": "wrong"},
                        {"Number": 88, "SheetImage": "3.jpg", "cclilyrcs": "right"},
                    ]
                ),
                encoding="utf-8",
            )
            lyrics, record = reference_from_hymns_json(path, "3")
            self.assertEqual(lyrics, "right")
            self.assertEqual(record["Number"], 88)

    def test_order_is_reported_separately_from_content(self) -> None:
        extracted = (
            "1. First verse words. 2. Second verse words. "
            "3. Third verse words. Chorus You are worthy."
        )
        reference = (
            "Verse 1 First verse words. Chorus You are worthy. "
            "Verse 2 Second verse words. Verse 3 Third verse words."
        )
        result = compare_text(extracted, reference)
        self.assertTrue(result.match)
        self.assertEqual(result.content_score, 1.0)
        self.assertTrue(result.verse_order_mismatch)
        self.assertEqual(result.extracted_order, ["1", "2", "3", "chorus"])
        self.assertEqual(result.reference_order, ["1", "chorus", "2", "3"])
        self.assertEqual(result.issues[0]["type"], "verse_order_mismatch")

    def test_colon_after_chorus_is_an_order_label(self) -> None:
        self.assertEqual(
            section_order("1. Verse one\n2. Verse two\n3. Verse three\nChorus: You are worthy"),
            ["1", "2", "3", "chorus"],
        )


if __name__ == "__main__":
    unittest.main()
