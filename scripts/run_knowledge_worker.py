from __future__ import annotations

import argparse
from pathlib import Path

from esg_reliable_discovery.worker import KnowledgeWorker

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--poll-seconds", type=float, default=15.0)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    worker_dir = ROOT / "artifacts/knowledge_worker"
    worker = KnowledgeWorker(
        root=ROOT,
        queue_path=ROOT / "configs/knowledge/worker_queue_v0.1.json",
        state_path=worker_dir / "worker_state.json",
        lock_path=worker_dir / "worker.lock",
        stop_path=worker_dir / "STOP",
    )
    if args.once:
        worker.acquire_lock()
        worker.process_once()
    else:
        worker.run(args.poll_seconds)


if __name__ == "__main__":
    main()
