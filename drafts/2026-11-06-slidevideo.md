# Draft 2026-11-06 (slidevideo)

**Status:** published

**Topic:** Orchestration Infrastructure for Agents at Scale
**Why now:** Fresh launch (HN Launch post) plus a concurrent architecture-pattern writeup landing in the same 24-48hr window shows real builder attention moving toward orchestration and reliability rather than raw model capability.

## Caption

A new YC launch this week is building infrastructure to run agents on object storage at scale. Around the same time, developers started publishing writeups on multi-agent architecture patterns, like how to split responsibilities across agents, handle failures, and keep state consistent.

Neither of these is about model quality.

They're about what happens after the model works. Once you can get an agent to do a task reliably once, the next question is different: how do you run that same agent a hundred times a day without it quietly failing, duplicating work, or losing context halfway through.

That's not a prompting problem. It's an infrastructure problem. State management, retries, logging, orchestration between agents that depend on each other's output.

Most demos skip this part because it's not exciting. But it's where the actual engineering work lives once you move past a single use case.

If builder attention is shifting toward orchestration and reliability instead of raw capability, that says something about where agentic AI actually is right now. The models are good enough for a lot of tasks. Running them consistently is the harder problem.

What does your current agent setup do when a step fails halfway through?

## Sources

- hackernews: https://github.com/rivet-dev/rivet
- hackernews: https://kadhar.dev/blog/multi-agent-systems-from-scratch
