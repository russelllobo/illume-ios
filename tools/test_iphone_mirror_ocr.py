"""OCR tests use generated images only; never use a phone frame."""

from io import BytesIO
from pathlib import Path
import sys
import unittest

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
from iphone_mirror_ocr import detect_targets


class DetectTargetsTest(unittest.TestCase):
    def test_groups_words_and_normalizes_boxes(self):
        image = Image.new("RGB", (600, 360), "white")
        draw = ImageDraw.Draw(image)
        font = ImageFont.truetype("/usr/share/fonts/liberation/LiberationSans-Regular.ttf", 36)
        draw.text((90, 100), "Continue with Apple", fill="black", font=font)
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=95)

        targets = detect_targets(buffer.getvalue())
        match = next(target for target in targets if "Continue with Apple" in target["text"])
        self.assertGreater(match["confidence"], 0.5)
        self.assertTrue(0.1 < match["x"] < 0.3)
        self.assertTrue(0.2 < match["y"] < 0.4)
        for key in ("x", "y", "w", "h", "confidence"):
            self.assertGreaterEqual(match[key], 0)
            self.assertLessEqual(match[key], 1)

    def test_rejects_non_jpeg(self):
        with self.assertRaises(ValueError):
            detect_targets(b"not an image")


if __name__ == "__main__":
    unittest.main()
