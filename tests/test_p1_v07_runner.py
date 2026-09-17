from pathlib import Path

from esg_reliable_discovery.p1_v07_runner import run_p1_v07_task


def test_v07_runner_is_importable_and_requires_arguments():
    assert callable(run_p1_v07_task)
    assert Path("prompts/p1_synthetic_evaluation_v0.7.txt").is_file()
