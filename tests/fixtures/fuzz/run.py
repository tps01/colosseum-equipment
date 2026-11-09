"""Seed a writable corpus and launch the shared target in Docker or Linux CI."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    target = os.environ.get("FUZZ_TARGET", "scpi_binary")
    if target not in {"scpi_binary", "ubx_stream", "mask_validation"}:
        raise ValueError(f"Unknown fuzz target: {target}")
    work = Path(os.environ.get("FUZZ_WORK", "/work")).resolve()
    if target != "scpi_binary":
        work = work / target
    corpus = work / "corpus"
    artifacts = work / "artifacts"
    corpus.mkdir(parents=True, exist_ok=True)
    artifacts.mkdir(parents=True, exist_ok=True)
    seed_dir = Path(__file__).parent / "corpus"
    if target != "scpi_binary":
        seed_dir = Path(__file__).parent / target
    for seed in seed_dir.iterdir():
        destination = corpus / seed.name
        if not destination.exists():
            destination.write_bytes(seed.read_bytes())
    args = sys.argv[1:] or ["-max_total_time=60"]
    # A single input filename replays it; otherwise continue evolving the corpus.
    replay = any(not arg.startswith("-") for arg in args)
    command = [sys.executable, "-m", f"tests.fuzz.{target}"]
    if not replay:
        command.append(str(corpus))
    command.extend(["-max_len=4096", "-timeout=5", f"-artifact_prefix={artifacts}/"])
    os.execv(sys.executable, [*command, *args])


if __name__ == "__main__":
    main()
