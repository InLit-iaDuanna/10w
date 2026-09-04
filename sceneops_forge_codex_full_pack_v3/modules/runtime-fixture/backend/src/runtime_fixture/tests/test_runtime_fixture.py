import unittest

from runtime_fixture import RuntimeFixtureError, run_runtime_fixture


class RuntimeFixtureTests(unittest.TestCase):
    def test_success_is_deterministic_mock(self):
        self.assertEqual(
            run_runtime_fixture(),
            {
                "status": "succeeded",
                "mode": "mock",
                "value": "runtime-fixture-v1",
            },
        )

    def test_failure_is_explicit_mock(self):
        with self.assertRaises(RuntimeFixtureError) as caught:
            run_runtime_fixture(True)
        self.assertEqual(caught.exception.code, "FIXTURE_REQUESTED_FAILURE")
        self.assertEqual(caught.exception.mode, "mock")


if __name__ == "__main__":
    unittest.main()
