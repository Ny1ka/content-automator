import sys
import time


class ProgressReporter:
    """Stderr progress markers for long-running, multi-step pipeline stages.

    Meant for steps with a handful to a few dozen discrete units of work
    (transcription chunks, analysis sliding windows, render passes) where a
    human is watching a log and wants to know "how far in, how much longer" —
    not a general logging framework.
    """

    def __init__(self, label: str, total: int):
        self.label = label
        self.total = total
        self.done_count = 0
        self.start_time = time.time()
        self._emit(f"start (0/{total})")

    def step(self, note: str = ""):
        self.done_count += 1
        elapsed = time.time() - self.start_time
        avg = elapsed / self.done_count
        remaining = avg * (self.total - self.done_count)
        pct = 100 * self.done_count / self.total
        suffix = f" — {note}" if note else ""
        self._emit(
            f"{self.done_count}/{self.total} ({pct:.0f}%) "
            f"elapsed={_fmt(elapsed)} eta={_fmt(remaining)}{suffix}"
        )

    def finish(self, note: str = ""):
        elapsed = time.time() - self.start_time
        suffix = f" — {note}" if note else ""
        self._emit(f"done ({self.total}/{self.total}) in {_fmt(elapsed)}{suffix}")

    def _emit(self, msg: str):
        print(f"[{self.label}] {msg}", file=sys.stderr, flush=True)


def _fmt(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}h{m:02d}m{s:02d}s"
    if m:
        return f"{m}m{s:02d}s"
    return f"{s}s"
