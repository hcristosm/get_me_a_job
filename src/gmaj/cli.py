import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmaj", description="Find niche jobs, score fit, apply with less friction.")
    sub = p.add_subparsers(dest="cmd")
    init = sub.add_parser("init", help="build your profile and search tracks from a CV PDF")
    init.add_argument("--cv", required=True, type=Path)
    init.add_argument("--force", action="store_true", help="overwrite existing profile/search files")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.cmd == "init":
        from gmaj.llm import LLMError
        from gmaj.onboarding import init
        try:
            return init(args.cv, args.force)
        except (LLMError, ValueError, OSError) as e:
            print(f"error: {e}")
            return 1
    build_parser().print_help()
    return 0
