# Shared helpers for running an asyncio loop integrated with GLib.
import asyncio
import concurrent.futures
import logging
import threading
from typing import Dict, Optional, Set

from gi.events import GLibEventLoopPolicy
from gi.repository import GLib

_policy: Optional[GLibEventLoopPolicy] = None
_loop: Optional[asyncio.AbstractEventLoop] = None
_thread: Optional[threading.Thread] = None
_started: Optional[threading.Event] = None
_tasks: Set[asyncio.Task] = set()
_tasks_lock = threading.Lock()
_init_lock = threading.Lock()


def _run_loop(loop: asyncio.AbstractEventLoop, started: threading.Event) -> None:
    """Run the background event loop."""
    asyncio.set_event_loop(loop)
    started.set()
    try:
        loop.run_forever()
    except Exception:
        logging.exception("Background loop failed")
    finally:
        pending = list(asyncio.all_tasks(loop))
        for task in pending:
            task.cancel()
        if pending:
            try:
                loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
        if not loop.is_closed():
            loop.close()
        global _loop
        _loop = None


def get_event_loop() -> asyncio.AbstractEventLoop:
    """Return the single persistent asyncio loop, created on a background thread."""
    global _policy, _loop, _thread, _started
    if _loop is not None and not _loop.is_closed():
        return _loop

    with _init_lock:
        if _loop is not None and not _loop.is_closed():
            return _loop

        if _policy is None:
            _policy = GLibEventLoopPolicy()
        _loop = _policy.new_event_loop()
        _started = threading.Event()
        _thread = threading.Thread(
            target=_run_loop,
            args=(_loop, _started),
            name="ks-asyncio",
            daemon=True,
        )
        _thread.start()
        if not _started.wait(timeout=5.0):
            _loop.close()
            _loop = None
            _started = None
            _thread = None
            raise RuntimeError("asyncio background loop did not start")
        return _loop


def _make_task(loop, coro, name: Optional[str] = None):
    task = loop.create_task(coro, name=name)
    with _tasks_lock:
        _tasks.add(task)
    task.add_done_callback(_discard_task)
    return task


def _discard_task(task):
    with _tasks_lock:
        _tasks.discard(task)


def _report_unhandled(task):
    """Log exceptions from an unhandled task.

    Skips logging when the task's exception was already observed
    (indicated by the ``_exception_observed`` attribute set by
    ``schedule()``'s completion callback).
    """
    if task.cancelled():
        return
    if getattr(task, "_exception_observed", False):
        return
    exc = task.exception()
    if exc is not None:
        logging.error(
            "Unhandled exception in task %s",
            task.get_name(),
            exc_info=(type(exc), exc, exc.__traceback__),
        )


def schedule(coro, *, name: Optional[str] = None) -> concurrent.futures.Future:
    """Submit *coro* to the background loop. Returns a future for observing completion.

    Cancelling the returned future does not cancel the underlying task.
    """
    loop = get_event_loop()
    fut = concurrent.futures.Future()

    def _submit():
        try:
            task = _make_task(loop, coro, name)
        except Exception as exc:
            coro.close()
            if not fut.done():
                fut.set_exception(exc)
            return

        def _finish(task):
            if fut.done():
                return
            if task.cancelled():
                fut.cancel()
            elif task.exception() is not None:
                fut.set_exception(task.exception())
                task._exception_observed = True
            else:
                task._exception_observed = True
                fut.set_result(task.result())

        task.add_done_callback(_finish)
        task.add_done_callback(_report_unhandled)

    try:
        loop.call_soon_threadsafe(_submit)
    except RuntimeError:
        coro.close()
        if not fut.done():
            fut.set_exception(RuntimeError("Event loop is not running"))
    return fut


def cancel_all_tasks() -> None:
    """Cancel every tracked background task."""
    with _tasks_lock:
        tasks = list(_tasks)
    cancel_tasks(tasks)


def cancel_tasks(tasks) -> None:
    """Cancel the asyncio tasks in *tasks*.

    *tasks* must be a snapshot (e.g. ``list(collection)``) taken while
    holding the collection's lock, or a collection that is guaranteed
    not to be mutated during this call.  The collection is iterated
    twice — once on the calling thread to locate the event loop, and
    again inside the loop callback to issue cancellations.
    """
    if not tasks:
        return

    # Tracked tasks may belong to more than one event loop (e.g. a fresh loop
    # per test). Group them by loop and cancel on every *live* loop, skipping
    # tasks whose loop has already been closed -- a closed loop would raise on
    # ``call_soon_threadsafe`` and must not stop the others from being cancelled.
    by_loop: Dict[asyncio.AbstractEventLoop, list] = {}
    for task in tasks:
        if task is None:
            continue
        loop = task.get_loop()
        if loop is None or loop.is_closed():
            continue
        by_loop.setdefault(loop, []).append(task)

    def _cancel(loop_tasks):
        for task in loop_tasks:
            if not task.done():
                task.cancel()

    for loop, loop_tasks in by_loop.items():
        try:
            loop.call_soon_threadsafe(_cancel, loop_tasks)
        except RuntimeError:
            pass


def on_gtk_thread(fn, *args, **kwargs):
    """Ensure *fn* runs on the GTK main thread.

    Always returns a concurrent.futures.Future.
    """
    fut = concurrent.futures.Future()

    if threading.current_thread() is threading.main_thread():
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            fut.set_exception(exc)
        else:
            fut.set_result(result)
        return fut

    def run():
        try:
            result = fn(*args, **kwargs)
        except Exception as exc:
            fut.set_exception(exc)
        else:
            fut.set_result(result)
        return False  # Remove the idle source

    GLib.idle_add(run)
    return fut
