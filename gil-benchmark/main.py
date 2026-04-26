# /// script
# requires-python = ">=3.13"
# dependencies = []
# ///
"""
GIL vs no-GIL comparison: `asyncio.to_thread()` + `asyncio.Semaphore`.

Each `asyncio` task spawns a real OS thread via `asyncio.to_thread()`.
Inside that thread, a `asyncio.Semaphore` limits how many threads may
do CPU work concurrently - making GIL contention directly observable.

Run with GIL (standard CPython 3.13):
    `uv run --python cpython-3.13 gil-benchmark/main.py`

Run without GIL (free-threaded CPython 3.13):
    `uv run --python cpython-3.13+freethreaded gil-benchmark/main.py`
"""

import asyncio
import threading
import time
from datetime import datetime, timezone

# config
TOTAL_TASKS = 1000 # asyncio tasks (and threads) to spawn
CONCURRENCY = 10 # max threads doing CPU work simultaneously
WORK_DURATION = 0.15 # seconds of CPU-bound work per thread

semaphore = asyncio.Semaphore(CONCURRENCY)
_active = 0
_lock = threading.Lock()

def ts() -> str:
    return datetime.now(timezone.utc).strftime("%H:%M:%S.%f")


def cpu_work(duration: float) -> int:
    """Pure CPU-bound busy loop - GIL contention shows up here."""
    end = time.perf_counter() + duration
    count = 0
    while time.perf_counter() < end:
        count += 1

def do_work(task_id: int) -> dict:
    """Runs inside a real OS thread — semaphore already acquired by the coroutine."""
    global _active
    with _lock:
        _active += 1
        print(f"... active={_active}")  # should never exceed CONCURRENCY
        assert _active <= CONCURRENCY, f"Semaphore broken! {_active} active"
    
    print(f"[{ts()}]  task {task_id} │ thread={threading.get_ident()} │ working")

    cpu_work(WORK_DURATION)
 
    print(f"[{ts()}]  task {task_id} │ thread={threading.get_ident()} │ done")

    with _lock:
        _active -= 1


async def worker(task_id: int) -> dict:
    """Waits for the asyncio semaphore, then dispatches work to a real OS thread."""
    print(f"[{ts()}]  task {task_id} │ waiting for semaphore")
 
    async with semaphore:
        return await asyncio.to_thread(do_work, task_id)


async def main() -> None:
    start = time.perf_counter()
    results = await asyncio.gather(*(worker(i) for i in range(1, TOTAL_TASKS + 1)))
    elapsed = time.perf_counter() - start
    print(f"Time elapsed: {elapsed:.1f}s")

if __name__ == "__main__":
    asyncio.run(main())
