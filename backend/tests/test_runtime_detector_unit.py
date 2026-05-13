import os
import sys
import unittest

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from tracker.runtime_detector import (
    CookieEvent,
    RuntimeDetectionResult,
    TrackerEvent,
    VendorSummary,
    _build_tracker_events,
    runtime_to_tracker_detection_result,
)


class TestRuntimeDetectorUnit(unittest.TestCase):
    def test_build_tracker_events_matches_known_domain(self):
        events = _build_tracker_events(
            [
                {
                    "url": "https://www.googletagmanager.com/gtm.js?id=GTM-TEST",
                    "resource_type": "script",
                    "method": "GET",
                }
            ],
            first_party_etld1="example.com",
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].vendor, "Google Tag Manager")
        self.assertTrue(events[0].known)
        self.assertEqual(events[0].source, "network_request")

    def test_build_tracker_events_keeps_unknown_tracking_like_third_party(self):
        events = _build_tracker_events(
            [
                {
                    "url": "https://metrics.example-cdn.test/collect?uid=123",
                    "resource_type": "image",
                    "method": "GET",
                }
            ],
            first_party_etld1="example.com",
        )

        self.assertEqual(len(events), 1)
        self.assertFalse(events[0].known)
        self.assertEqual(events[0].category, "Unknown third-party tracking")

    def test_runtime_result_converts_to_legacy_tracker_result(self):
        runtime = RuntimeDetectionResult(
            url="https://example.com",
            final_url="https://example.com",
            first_party_etld1="example.com",
            total_requests=2,
            third_party_request_count=1,
            tracker_events=[
                TrackerEvent(
                    url="https://www.googletagmanager.com/gtm.js?id=GTM-TEST",
                    domain="www.googletagmanager.com",
                    etld1="googletagmanager.com",
                    vendor="Google Tag Manager",
                    category="Tag Manager",
                    risk="medium",
                    resource_type="script",
                    source="network_request",
                    evidence="script request to known tracker",
                    known=True,
                )
            ],
            cookie_events=[
                CookieEvent(
                    name="_ga",
                    domain="example.com",
                    etld1="example.com",
                    first_party=True,
                    category="analytics",
                    value_preview="GA1.1",
                    secure=True,
                    httponly=False,
                    samesite="Lax",
                    expires=None,
                    duration_label="session",
                    source="browser_cookie_jar",
                )
            ],
            vendors=[
                VendorSummary(
                    domain="googletagmanager.com",
                    name="Google Tag Manager",
                    category="Tag Manager",
                    risk="medium",
                    request_count=1,
                    resource_types=["script"],
                    sample_url="https://www.googletagmanager.com/gtm.js?id=GTM-TEST",
                    known=True,
                )
            ],
            total_tracker_count=1,
            total_cookie_count=1,
            third_party_cookie_count=0,
            by_category={"Tag Manager": 1},
            cmp_detected=None,
            fingerprinting_detected=False,
            fingerprinting_evidence=[],
            session_recording_detected=False,
            session_recording_evidence=[],
            privacy_sandbox_detected=False,
        )

        legacy = runtime_to_tracker_detection_result(runtime)

        self.assertEqual(legacy.total_tracker_count, 1)
        self.assertEqual(legacy.trackers[0].name, "Google Tag Manager")
        self.assertEqual(legacy.trackers[0].source_type, "script")
        self.assertEqual(legacy.cookies[0].category, "analytics")
        self.assertEqual(legacy.cookie_security["secure_pct"], 100.0)


if __name__ == "__main__":
    unittest.main()
