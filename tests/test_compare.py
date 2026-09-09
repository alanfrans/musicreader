import json
import tempfile
import unittest
from pathlib import Path

from musicreader.compare import compare_text, normalize_for_compare, reference_from_hymns_json


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


if __name__ == "__main__":
    unittest.main()
