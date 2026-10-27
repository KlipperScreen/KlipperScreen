"""Unit tests for async_utils cross-thread rendezvous (on_gtk_thread).

These tests exercise the *else* branch of ``on_gtk_thread`` — the path used
in production when a coroutine runs on the background async loop thread.
They use a real GLibEventLoop for the asyncio barrier and mock GLib.idle_add
to invoke the GTK callback directly (simulating the GTK main thread).
"""

import asyncio
import threading
import unittest
from unittest.mock import patch

from gi.events import GLibEventLoopPolicy

import ks_includes.async_utils as async_utils


class TestOnGtkThreadElseBranch(unittest.TestCase):
    """Test the cross-thread rendezvous path of on_gtk_thread."""

    def _run_on_worker(self, coro_factory):
        """Run *coro_factory* on a worker thread driven by a GLibEventLoop.

        Returns (result, exception) where exactly one is not None.
        """
        loop = GLibEventLoopPolicy().new_event_loop()
        created = threading.Event()
        worker_done = threading.Event()
        holder = {}

        def worker():
            asyncio.set_event_loop(loop)

            async def main():
                return await coro_factory(loop)

            task = loop.create_task(main())

            def on_done(t):
                holder["task"] = t
                loop.stop()

            task.add_done_callback(on_done)
            created.set()
            loop.run_forever()
            loop.close()
            worker_done.set()

        # Patch async_utils.GLib.idle_add to invoke the callback directly
        # (simulating the GTK main thread processing the idle source).
        with patch.object(async_utils, "get_event_loop", return_value=loop):
            with patch.object(async_utils, "GLib") as mock_glib:

                def fake_idle_add(cb, *args):
                    cb(*args)
                    return 1

                mock_glib.idle_add = fake_idle_add

                t = threading.Thread(target=worker, name="worker", daemon=True)
                t.start()
                assert created.wait(5), "task not created"
                t.join(8)
                assert worker_done.wait(2), "worker did not finish"
                fut = holder.get("task")
                if fut is None:
                    return None, "no task"
                if fut.cancelled():
                    return None, "cancelled"
                try:
                    return fut.result(), None
                except Exception as e:
                    return None, e

    def test_result_propagates(self):
        """Widget method result propagates back through on_gtk_thread."""
        results = {}

        def widget_fn(x):
            results["val"] = x
            results["thread"] = threading.current_thread().name
            return x * 2

        async def make_coro(loop):
            return await asyncio.wrap_future(async_utils.on_gtk_thread(widget_fn, 21))

        result, exc = self._run_on_worker(make_coro)
        self.assertIsNone(exc, f"unexpected exception: {exc}")
        self.assertEqual(result, 42)
        self.assertEqual(results.get("val"), 21)

    def test_exception_propagates(self):
        """Widget method exception propagates back through on_gtk_thread."""
        results = {}

        def raise_fn(x):
            results["val"] = x
            raise ValueError("boom-" + str(x))

        async def make_coro(loop):
            return await asyncio.wrap_future(async_utils.on_gtk_thread(raise_fn, 7))

        result, exc = self._run_on_worker(make_coro)
        self.assertIsNone(result)
        self.assertIsInstance(exc, ValueError)
        self.assertIn("boom-7", str(exc))
        self.assertEqual(results.get("val"), 7)


if __name__ == "__main__":
    unittest.main()
