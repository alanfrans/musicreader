import unittest

import numpy as np

from musicreader.models import ExtractionResult, TextBox
from musicreader.reconstruct import (
    merge_page_verses,
    normalize_lyrics,
    reconstruct_page,
    reconstruct_page_sections,
    rows_from_boxes,
)


class ReconstructionTests(unittest.TestCase):
    def test_parallel_rows_are_joined_by_verse(self) -> None:
        systems = [
            [
                "1. Praise to the Lord, the Al - might - y",
                "2. Praise to the Lord, who o'er all things",
            ],
            [
                "the King of cre - a - tion!",
                "so won - drous - ly reign - eth!",
            ],
        ]

        verses = reconstruct_page(systems)

        self.assertEqual(
            verses[1], "Praise to the Lord, the Almighty the King of creation!"
        )
        self.assertEqual(
            verses[2],
            "Praise to the Lord, who o'er all things so wondrously reigneth!",
        )

    def test_single_numbered_row_keeps_its_verse_number(self) -> None:
        verses = reconstruct_page(
            [["4. Praise to the Lord"], ["O let all that is in me"]]
        )
        self.assertEqual(verses, {4: "Praise to the Lord O let all that is in me"})

    def test_repeated_optional_setting_is_not_appended(self) -> None:
        merged = merge_page_verses(
            [
                {1: "First verse", 4: "Praise to the Lord, adore Him!"},
                {4: "Praise to the Lord adore Him!"},
            ]
        )
        self.assertEqual(merged[4], "Praise to the Lord, adore Him!")

    def test_syllable_and_punctuation_spacing_is_normalized(self) -> None:
        self.assertEqual(
            normalize_lyrics("0 let all, Al • might - y ,   reign - eth !"),
            "O let all, Almighty, reigneth!",
        )

    def test_standalone_lyric_letters_are_retained(self) -> None:
        boxes = [
            TextBox("O", 0.99, np.array([[0, 0], [8, 0], [8, 10], [0, 10]])),
            TextBox("Lord", 0.99, np.array([[15, 0], [40, 0], [40, 10], [15, 10]])),
        ]
        self.assertEqual(rows_from_boxes(boxes, 0.45), ["O Lord"])

    def test_single_fourth_verse_keeps_its_display_number(self) -> None:
        result = ExtractionResult({4: "Praise to the Lord"})
        self.assertEqual(result.text, "4. Praise to the Lord")

    def test_chorus_can_start_in_a_three_row_system(self) -> None:
        verses, chorus = reconstruct_page_sections(
            [
                [
                    "Worthy of worship, worthy of praise,",
                    "Worthy of reverence, worthy of fear,",
                    "Almighty Father, Master and Lord,",
                ],
                [
                    "Worthy of all the offerings we bring.",
                    "Worthy of all this and added to these... You are worthy, Father, Creator.",
                    "Savior and Source of our life without end.",
                ],
                ["You are worthy, Savior, Sustainer. You are worthy,"],
                ["worthy and wonderful; Worthy of worship and praise."],
            ]
        )
        self.assertEqual(
            verses[2],
            "Worthy of reverence, worthy of fear, Worthy of all this and added to these...",
        )
        self.assertEqual(
            chorus,
            "You are worthy, Father, Creator. You are worthy, Savior, Sustainer. "
            "You are worthy, worthy and wonderful; Worthy of worship and praise.",
        )


if __name__ == "__main__":
    unittest.main()
