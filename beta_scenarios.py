"""Exercise the beta through real subprocess CLI runs, in disposable directories."""
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import time

script = Path(__file__).parent / "turbo_sort.py"


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


reports = []
for iteration in range(1, 3):
    with tempfile.TemporaryDirectory(prefix="turbo-sort-beta-") as folder:
        base = Path(folder)
        source, tv, movies = (base / name for name in ("source", "tv", "movies"))
        source.mkdir()
        for episode in range(1, 101):
            stem = f"Example_Show_S01E{episode:03}"
            (source / (stem + ".mkv")).write_bytes(bytes([episode]) * 16384)
            (source / (stem + ".en.srt")).write_bytes(f"English {episode}".encode())
            (source / (stem + ".fr.srt")).write_bytes(f"French {episode}".encode())
        (source / "Movie.2020.2160p.mkv").write_bytes(b"large-payload" * (1024 * 1024))
        for name in ("Unknown.mkv", "News.2023.02.29.mkv", "Duplicate.2020.720p.mkv", "Duplicate.2020.1080p.mkv"):
            (source / name).write_bytes(name.encode())
        commands = [sys.executable, str(script), "--source", str(source), "--tv", str(tv),
                    "--movies", str(movies), "--min-size-mb", "0", "--cleanup-empty"]
        before = snapshot(base)
        rows = []
        for phase, flags in (("preview", []), ("apply", ["--apply"]), ("repeat", ["--apply"])):
            start = time.perf_counter()
            proc = subprocess.run(commands + flags, capture_output=True, text=True, check=True)
            summary = json.loads(proc.stdout.splitlines()[-1])
            rows.append({"phase": phase, "seconds": round(time.perf_counter() - start, 3), **summary})
            if phase == "preview":
                assert snapshot(base) == before, "Preview mutated files"
            elif phase == "apply":
                assert summary["moved"] == 301 and summary["failed"] == 0
                after_apply = snapshot(base)
                assert sorted(before.values()) == sorted(after_apply.values()), "Content lost or corrupted"
            else:
                assert summary["moved"] == 0 and summary["failed"] == 0
                assert snapshot(base) == after_apply, "Repeat run changed organized files"
        assert len(list(source.glob("*.mkv"))) == 4
        reports.append({"batch": iteration, "input_files": len(before), "runs": rows,
                        "all_file_hashes_preserved": True})
print(json.dumps({"python": platform.python_version(), "platform": platform.system(), "batches": reports}, indent=2))
