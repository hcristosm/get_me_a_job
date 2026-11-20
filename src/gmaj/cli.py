import argparse
from pathlib import Path


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="gmaj", description="Find niche jobs, score fit, apply with less friction.")
    sub = p.add_subparsers(dest="cmd")
    init = sub.add_parser("init", help="build your profile and search tracks from a CV PDF")
    init.add_argument("--cv", required=True, type=Path)
    init.add_argument("--force", action="store_true", help="overwrite existing profile/search files")
    sub.add_parser("collect", help="collect, filter and score jobs now")
    sub.add_parser("open", help="open the dashboard; the app stops by itself when you close it")
    serve = sub.add_parser("serve", help="run the web interface until Ctrl+C")
    serve.add_argument("--port", type=int)
    sched = sub.add_parser("schedule", help="optional: run 'collect' automatically every day (off by default)")
    sched.add_argument("action", choices=["install", "remove"])
    sched.add_argument("--hour", type=int, default=8)
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
    if args.cmd == "collect":
        from gmaj.llm import LLMError
        from gmaj.pipeline import ConfigError, run_collect
        try:
            rep = run_collect()
        except (ConfigError, LLMError, ValueError) as e:
            print(e)
            return 1
        if rep.skipped:
            print("Another collect is already running.")
            return 0
        print(f"fetched {rep.fetched}, new {rep.new}, kept {rep.kept}, scored {rep.scored}")
        for err in rep.errors:
            print(f"  error: {err}")
        return 0
    if args.cmd == "open":
        from gmaj.config import load_settings
        from gmaj.launcher import open_app
        return open_app(load_settings().port)
    if args.cmd == "serve":
        import uvicorn

        from gmaj.config import load_settings
        from gmaj.web.app import create_app
        port = args.port or load_settings().port
        print(f"get_me_a_job: http://127.0.0.1:{port}")
        uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="warning")
        return 0
    if args.cmd == "schedule":
        import shutil
        import sys

        from gmaj.schedule import gmaj_exe, install, remove
        if sys.platform != "linux" or not shutil.which("systemctl"):
            print(f"No systemd here. Add this line with 'crontab -e' instead:\n0 {args.hour} * * * {gmaj_exe()} collect")
            return 0
        install(args.hour) if args.action == "install" else remove()
        print(f"Daily collect {'enabled at %02d:00' % args.hour if args.action == 'install' else 'disabled'}.")
        return 0
    build_parser().print_help()
    return 0
