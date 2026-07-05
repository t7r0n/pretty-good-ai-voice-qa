from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path


def test_apply_video_links_updates_expected_placeholders(tmp_path: Path) -> None:
    source_root = Path.cwd()
    for name in ["FINAL_SUBMISSION_PACKET.md", "SUBMISSION_CHECKLIST.md", "FORM_ANSWERS.md", "README.md"]:
        shutil.copy(source_root / name, tmp_path / name)
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    shutil.copy(source_root / "scripts" / "apply_video_links.py", scripts / "apply_video_links.py")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/apply_video_links.py",
            "--loom",
            "https://loom.example.com/share/test",
            "--debug",
            "https://videos.example.com/debug",
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    packet = (tmp_path / "FINAL_SUBMISSION_PACKET.md").read_text()
    checklist = (tmp_path / "SUBMISSION_CHECKLIST.md").read_text()
    form_answers = (tmp_path / "FORM_ANSWERS.md").read_text()
    readme = (tmp_path / "README.md").read_text()
    assert "Loom walkthrough link: https://loom.example.com/share/test" in packet
    assert "AI-debugging screen recording link: https://videos.example.com/debug" in packet
    assert "- [x] Loom walkthrough link: https://loom.example.com/share/test." in checklist
    assert "- Loom walkthrough link: https://loom.example.com/share/test" in form_answers
    assert "- AI-debugging screen recording link: https://videos.example.com/debug" in form_answers
    assert "- Loom walkthrough: https://loom.example.com/share/test" in readme
