from __future__ import annotations

import argparse
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply final video links to submission docs.")
    parser.add_argument("--loom", required=True, help="Public Loom walkthrough URL.")
    parser.add_argument("--debug", required=True, help="Public AI-debugging screen recording URL.")
    args = parser.parse_args()

    loom = _valid_url(args.loom, "--loom")
    debug = _valid_url(args.debug, "--debug")

    replacements = {
        "FINAL_SUBMISSION_PACKET.md": {
            "- Loom walkthrough link: add after recording.": f"- Loom walkthrough link: {loom}",
            "- AI-debugging screen recording link: add after recording.": (
                f"- AI-debugging screen recording link: {debug}"
            ),
        },
        "SUBMISSION_CHECKLIST.md": {
            "- [ ] Loom walkthrough link.": f"- [x] Loom walkthrough link: {loom}.",
            "- [ ] 5-minute AI-debugging screen recording link.": (
                f"- [x] 5-minute AI-debugging screen recording link: {debug}."
            ),
        },
        "FORM_ANSWERS.md": {
            "- Loom walkthrough link: Pending Loom walkthrough URL.": f"- Loom walkthrough link: {loom}",
            "- AI-debugging screen recording link: Pending AI-debugging screen recording URL.": (
                f"- AI-debugging screen recording link: {debug}"
            ),
        },
        "README.md": {
            "- [LOOM.md](LOOM.md): 5-minute walkthrough script.": (
                f"- Loom walkthrough: {loom}\n"
                "- [LOOM.md](LOOM.md): 5-minute walkthrough script."
            ),
            "- [AI_DEBUGGING_RECORDING.md](AI_DEBUGGING_RECORDING.md): 5-minute AI-debugging recording script.": (
                f"- AI-debugging screen recording: {debug}\n"
                "- [AI_DEBUGGING_RECORDING.md](AI_DEBUGGING_RECORDING.md): "
                "5-minute AI-debugging recording script."
            ),
        },
    }

    for relative_path, file_replacements in replacements.items():
        path = ROOT / relative_path
        text = path.read_text()
        for old, new in file_replacements.items():
            if old not in text:
                raise SystemExit(f"Expected placeholder not found in {relative_path}: {old}")
            text = text.replace(old, new, 1)
        path.write_text(text)
        print(f"updated {relative_path}")


def _valid_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc:
        raise SystemExit(f"{label} must be a public https URL.")
    return value.rstrip()


if __name__ == "__main__":
    main()
