import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tracker.stateful_adapter import _compute_mismatch_detected


class TestMismatchDetected(unittest.TestCase):
    def _stateful(self, s0=None, s1=None, s2=None):
        return {
            "states": {
                "S0": s0 or {},
                "S1": s1 or {},
                "S2": s2 or {},
            }
        }

    def test_effective_consent_not_mismatch(self):
        stateful = self._stateful(
            s0={"known_tracker_count": 0, "nonessential_cookie_count": 0},
            s1={"known_tracker_count": 0, "nonessential_cookie_count": 0},
            s2={"known_tracker_count": 1, "nonessential_cookie_count": 1},
        )
        self.assertFalse(_compute_mismatch_detected(stateful, {"usable_for_mismatch": True}))

    def test_bad_reject_is_mismatch(self):
        stateful = self._stateful(
            s0={"known_tracker_count": 0, "nonessential_cookie_count": 0},
            s1={"known_tracker_count": 1, "nonessential_cookie_count": 1},
            s2={"known_tracker_count": 1, "nonessential_cookie_count": 1},
        )
        self.assertTrue(_compute_mismatch_detected(stateful, {"usable_for_mismatch": True}))

    def test_preconsent_is_mismatch(self):
        stateful = self._stateful(
            s0={"known_tracker_count": 1, "nonessential_cookie_count": 1},
            s1={"known_tracker_count": 1, "nonessential_cookie_count": 1},
            s2={"known_tracker_count": 1, "nonessential_cookie_count": 1},
        )
        self.assertTrue(_compute_mismatch_detected(stateful, {"usable_for_mismatch": True}))

    def test_cookie_only_consent_values_do_not_trigger(self):
        stateful = self._stateful(
            s0={"known_tracker_count": 0, "nonessential_cookie_count": 0},
            s1={"known_tracker_count": 0, "nonessential_cookie_count": 0},
            s2={"known_tracker_count": 0, "nonessential_cookie_count": 1},
        )
        self.assertFalse(_compute_mismatch_detected(stateful, {"usable_for_mismatch": True}))

    def test_unusable_for_mismatch_is_false(self):
        stateful = self._stateful(
            s0={"known_tracker_count": 1, "nonessential_cookie_count": 1},
            s1={"known_tracker_count": 1, "nonessential_cookie_count": 1},
        )
        self.assertFalse(_compute_mismatch_detected(stateful, {"usable_for_mismatch": False}))


if __name__ == "__main__":
    unittest.main()
