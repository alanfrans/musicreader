import unittest

import cv2
import numpy as np

from musicreader.layout import lyric_regions


class LayoutTests(unittest.TestCase):
    def test_finds_lyric_gap_between_two_staves(self) -> None:
        image = np.full((500, 800, 3), 255, dtype=np.uint8)
        for start in (100, 300):
            for y in range(start, start + 41, 10):
                cv2.line(image, (80, y), (720, y), (0, 0, 0), 2)
                # Simulate an interrupted/thick rule producing a second peak.
                cv2.line(image, (80, y + 3), (720, y + 3), (0, 0, 0), 1)

        regions, warnings = lyric_regions(image)

        self.assertEqual(warnings, [])
        self.assertEqual(len(regions), 1)
        self.assertGreater(regions[0].top, 140)
        self.assertLess(regions[0].bottom, 300)


if __name__ == "__main__":
    unittest.main()
