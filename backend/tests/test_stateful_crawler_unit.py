import os
import sys
import unittest
from unittest.mock import AsyncMock

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from stateful_crawler import (
    ACCEPT_PATTERNS,
    MANAGE_PATTERNS,
    REJECT_PATTERNS,
    _perform_consent_action,
)


class TestPerformConsentAction(unittest.IsolatedAsyncioTestCase):
    async def test_accept_direct_click(self):
        click_fn = AsyncMock(side_effect=[True])

        clicked, action = await _perform_consent_action(object(), "accept", click_fn=click_fn)

        self.assertTrue(clicked)
        self.assertEqual(action, "accept_clicked")
        self.assertEqual(click_fn.await_count, 1)
        self.assertEqual(click_fn.await_args_list[0].args[1], ACCEPT_PATTERNS)

    async def test_accept_manage_fallback_success(self):
        click_fn = AsyncMock(side_effect=[False, True, True])

        clicked, action = await _perform_consent_action(object(), "accept", click_fn=click_fn)

        self.assertTrue(clicked)
        self.assertEqual(action, "manage_then_accept_clicked")
        self.assertEqual(click_fn.await_count, 3)
        self.assertEqual(click_fn.await_args_list[0].args[1], ACCEPT_PATTERNS)
        self.assertEqual(click_fn.await_args_list[1].args[1], MANAGE_PATTERNS)
        self.assertEqual(click_fn.await_args_list[2].args[1], ACCEPT_PATTERNS)

    async def test_reject_manage_fallback_success(self):
        click_fn = AsyncMock(side_effect=[False, True, True])

        clicked, action = await _perform_consent_action(object(), "reject", click_fn=click_fn)

        self.assertTrue(clicked)
        self.assertEqual(action, "manage_then_reject_clicked")
        self.assertEqual(click_fn.await_count, 3)
        self.assertEqual(click_fn.await_args_list[0].args[1], REJECT_PATTERNS)
        self.assertEqual(click_fn.await_args_list[1].args[1], MANAGE_PATTERNS)
        self.assertEqual(click_fn.await_args_list[2].args[1], REJECT_PATTERNS)

    async def test_reject_not_found_when_manage_missing(self):
        click_fn = AsyncMock(side_effect=[False, False])

        clicked, action = await _perform_consent_action(object(), "reject", click_fn=click_fn)

        self.assertFalse(clicked)
        self.assertEqual(action, "reject_not_found")


if __name__ == "__main__":
    unittest.main()
