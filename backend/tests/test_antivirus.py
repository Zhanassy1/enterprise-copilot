import tempfile
import unittest

from app.services.antivirus import scan_uploaded_file_safe


class AntivirusHookTests(unittest.TestCase):
    def test_scan_accepts_readable_file(self) -> None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"clean")
            path = f.name
        try:
            scan_uploaded_file_safe(path)
        finally:
            import os

            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
