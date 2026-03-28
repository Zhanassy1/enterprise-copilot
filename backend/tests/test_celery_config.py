import unittest

from app.core.startup_checks import validate_celery_json_policy


class CeleryConfigTests(unittest.TestCase):
    def test_json_only_serializers(self) -> None:
        validate_celery_json_policy()


if __name__ == "__main__":
    unittest.main()
