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
