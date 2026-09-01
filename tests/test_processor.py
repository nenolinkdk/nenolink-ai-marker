from pathlib import Path
import tempfile
import unittest

from PIL import Image

from nenolink_ai_marker.models import MarkerSettings
from nenolink_ai_marker.processor import ImageProcessor, output_path


class ProcessorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root / "photo.png"
        self.badge = self.root / "badge.png"
        Image.new("RGB", (200, 100), "white").save(self.source)
        Image.new("RGBA", (100, 50), (255, 0, 0, 255)).save(self.badge)

    def tearDown(self):
        self.temp.cleanup()

    def test_all_positions(self):
        pixels = {"top-left": (5, 5), "top-right": (195, 5), "bottom-left": (5, 95), "bottom-right": (195, 95)}
        for position, pixel in pixels.items():
            result = ImageProcessor().process(self.source, self.badge, MarkerSettings(position=position, size_percent=20, margin=2))
            self.assertEqual(result.getpixel(pixel)[:3], (255, 0, 0))

    def test_opacity(self):
        result = ImageProcessor().process(self.source, self.badge, MarkerSettings(size_percent=20, margin=0, opacity=50))
        red, green, blue, alpha = result.getpixel((199, 99))
        self.assertEqual((red, alpha), (255, 255))
        self.assertTrue(120 <= green <= 135 and 120 <= blue <= 135)

    def test_output_path_does_not_overwrite(self):
        (self.root / "photo_ai.png").touch()
        self.assertEqual(output_path(self.source), self.root / "photo_ai_2.png")

    def test_rejects_video(self):
        with self.assertRaisesRegex(ValueError, "Unsupported"):
            ImageProcessor().process(self.root / "movie.mp4", self.badge, MarkerSettings())

    def test_large_margin_keeps_badge_visible(self):
        result = ImageProcessor().process(self.source, self.badge, MarkerSettings(position="top-left", margin=2000))
        self.assertEqual(result.getpixel((49, 49))[:3], (255, 0, 0))


if __name__ == "__main__":
    unittest.main()
