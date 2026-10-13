# Draft 2026-10-13 (slidevideo)

**Status:** blocked

**Topic:** Codex CLI silently installs a background daemon
**Why now:** Fast-rising HN thread (460 points, 238 comments in ~7 hours) showing developers are actively scrutinizing what coding agents do behind the scenes once they move past the demo stage.

## Caption

Codex CLI was shipping a persistent, self-updating background daemon by default.

No prompt. No explicit opt-in. It just installed itself and kept running.

A thread on Hacker News picked this apart this week — 460+ points, 238 comments in about seven hours. Developers going through what the tool actually does once you install it, not just what it demos well.

That reaction makes sense.

A coding agent isn't just a chat window anymore. It's a process with permissions, update cycles, and access to your machine. That deserves the same scrutiny as any other software you'd let run in the background: what it installs, what it touches, whether it tells you first.

Most people evaluating agent tools right now are still testing capability — can it write the code, can it fix the bug. Fewer are asking what it's doing when you're not looking at the terminal.

Both questions matter. Right now, only one of them is getting asked.

What would you want disclosed before an agent installs anything persistent on your system?

## Sources

- hackernews: https://github.com/openai/codex/issues/48195
