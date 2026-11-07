import asyncio
import logging

from fastapi import FastAPI

log = logging.getLogger("tasks")


def spawn(app: FastAPI, coro) -> asyncio.Task:
    """Run a background coroutine and keep a reference so it is not garbage collected."""
    tasks: set = app.state.tasks
    task = asyncio.create_task(coro)
    tasks.add(task)

    def _done(t: asyncio.Task) -> None:
        tasks.discard(t)
        if not t.cancelled() and t.exception() is not None:
            log.error("background task failed", exc_info=t.exception())

    task.add_done_callback(_done)
    return task
