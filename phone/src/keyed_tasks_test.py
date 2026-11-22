import asyncio

import pytest

from keyed_tasks import KeyedTasks


async def test_close_cancels_the_tasks_still_running():
    tasks = KeyedTasks()
    tasks.start("a", asyncio.sleep(60))
    assert "a" in tasks
    await tasks.close()
    assert "a" not in tasks


async def test_close_raises_a_task_that_failed():
    async def fail() -> None:
        raise ValueError("broken feed")

    tasks = KeyedTasks()
    tasks.start("a", fail())
    await asyncio.sleep(0)
    with pytest.raises(ValueError, match="broken feed"):
        await tasks.close()


async def test_a_key_runs_one_task_at_a_time():
    tasks = KeyedTasks()
    tasks.start("a", asyncio.sleep(60))
    with pytest.raises(RuntimeError):
        tasks.start("a", asyncio.sleep(60))
    tasks.stop("a")
    tasks.start("a", asyncio.sleep(60))
    await tasks.close()
