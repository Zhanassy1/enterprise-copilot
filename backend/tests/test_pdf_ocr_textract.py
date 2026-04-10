"""Textract helpers: S3 key parsing and block merging."""

import unittest

from app.services.pdf_ocr_textract import _blocks_to_page_text, parse_s3_storage_key


class PdfOcrTextractTests(unittest.TestCase):
    def test_parse_s3(self) -> None:
        self.assertEqual(parse_s3_storage_key("s3://my-bucket/path/to/doc.pdf"), ("my-bucket", "path/to/doc.pdf"))
        self.assertIsNone(parse_s3_storage_key("data/uploads/x.pdf"))
        self.assertIsNone(parse_s3_storage_key(""))

    def test_blocks_to_page_text_orders_lines(self) -> None:
        blocks = [
            {"BlockType": "LINE", "Page": 1, "Text": "Second", "Geometry": {"BoundingBox": {"Top": 0.5}}},
            {"BlockType": "LINE", "Page": 1, "Text": "First", "Geometry": {"BoundingBox": {"Top": 0.1}}},
            {"BlockType": "LINE", "Page": 2, "Text": "B", "Geometry": {"BoundingBox": {"Top": 0.0}}},
        ]
        text, n = _blocks_to_page_text(blocks)
        self.assertEqual(n, 2)
        self.assertIn("\f", text)
        p1, p2 = text.split("\f")
        self.assertIn("First", p1)
        self.assertIn("Second", p1)
        self.assertIn("B", p2)


if __name__ == "__main__":
    unittest.main()
