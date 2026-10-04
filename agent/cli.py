"""CLI: python -m agent.cli <command>"""
from __future__ import annotations

import argparse
import json
import sys

from . import comments, config, pipeline, state


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="agent", description="Lark AI LinkedIn content agent")
    sub = p.add_subparsers(dest="cmd", required=True)

    for name in ("run", "approve", "skip"):
        s = sub.add_parser(name)
        s.add_argument("--lane", choices=["post", "carousel", "video"], default="post")
        s.add_argument("--date")
        if name == "run":
            s.add_argument("--fresh", action="store_true", help="ignore today's discovery cache")
    sub.add_parser("comments", help="run the comment pass only (drafts replies; sends in auto mode)")
    sub.add_parser("status")
    sub.add_parser("mode")

    a = p.parse_args(argv)
    if a.cmd == "run":
        out = pipeline.run(a.lane, force_discovery=a.fresh)
        print(json.dumps(out, indent=2, default=str) if out else "nothing published")
    elif a.cmd == "approve":
        print(json.dumps(pipeline.approve(a.lane, a.date), indent=2, default=str))
    elif a.cmd == "skip":
        pipeline.skip(a.lane, a.date)
        print("discarded")
    elif a.cmd == "comments":
        replies = comments.run_pass()
        if config.mode() == "auto" and replies:
            replies = comments.send(replies, publish=True)
        print(json.dumps(replies, indent=2, default=str))
    elif a.cmd == "status":
        print(f"mode: {config.mode()}")
        print(f"published: {len(state.published())}  recent topics: {[t['topic'] for t in state.topics()]}")
    elif a.cmd == "mode":
        print(config.mode())
    return 0


if __name__ == "__main__":
    sys.exit(main())
