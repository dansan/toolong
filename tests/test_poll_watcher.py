import os
import time
from types import SimpleNamespace

from toolong.poll_watcher import PollWatcher


def test_lines_written_in_quick_succession_are_batched(tmp_path):
    path = tmp_path / "growing.log"
    path.write_bytes(b"")
    fileno = os.open(path, os.O_RDONLY)
    batches: list[list[int]] = []
    watcher = PollWatcher()
    watcher.add(SimpleNamespace(fileno=fileno), lambda size, breaks: batches.append(breaks), print)
    watcher.start()
    try:
        with path.open("ab", buffering=0) as log:
            for number in range(100):
                log.write(b"line %d\n" % number)
                time.sleep(0.01)
        time.sleep(2 * PollWatcher.interval)
    finally:
        watcher.close()
        os.close(fileno)
    assert sum(len(breaks) for breaks in batches) == 100
    # One second of writing: about 4 batches at 0.25 s, about 20 at the old 0.05 s.
    assert len(batches) <= 10
