# Draft 2026-11-10 (slidevideo)

**Status:** published

**Topic:** Coding Agent Secrets Exposure at Scale
**Why now:** Fresh report (within last ~54 hours) quantifying 1,122 exposed files is generating heavy discussion (422 comments) about agent permission design, directly extending the ongoing conversation about coding agent guardrails.

## Caption

A security firm scanned over 100,000 public GitHub repos for one specific file: Claude Code's settings.local.json.

1,122 of them had secrets sitting inside. Database passwords, AWS keys, SSH logins, API tokens. 1,379 credentials total, out in the open.

Here's how it happened.

When Claude Code asks permission to run a command and you click "don't ask again," it saves that command to a local settings file so it won't ask next time. If the command you approved had a password typed into it, the password gets saved too. Word for word.

That file is supposed to be gitignored automatically. In a lot of these repos, it wasn't, and it got committed and pushed like any other file.

Nobody did anything obviously wrong. A developer approved a command. The tool remembered it. The repo went public. Three unremarkable steps, one exposed credential.

Anthropic's Claude Code lead responded directly on Hacker News, saying they're looking at built-in secret scanning and changes to how permissions get handled. That's the right instinct, but it's worth sitting with why this slipped through for this long.

Convenience settings are where security gaps hide best. Nobody reviews a "don't ask again" click the way they'd review a pull request. It feels like a UI preference, not a data handling decision.

If you're running coding agents against real credentials, worth checking what they're writing to disk, not just what they're writing to your codebase.

What gets saved quietly is usually more interesting than what gets asked out loud.

## Sources

- hackernews: https://apiiro.com/blog/coding-agents-leaking-secrets-github-dont-ask-again
