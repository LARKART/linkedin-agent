# Draft 2026-10-12 (slidevideo)

**Status:** published

**Topic:** Coding agents treated as collaborators in long-running experimental work
**Why now:** Strong velocity (19.4) and high comment count within 32 hours on a concrete, unusually large-scale agentic coding experiment that shows real production friction, not hype

## Caption

Most demos of agentic coding show a 10-minute task.

A developer recently documented something very different: a coding agent run across hundreds of billions of tokens on a single decompilation project, publicly shared as a build log.

That scale changes what actually matters.

In a short demo, the model's raw capability is the story. Over a project that long, the story becomes everything around the model: how context gets managed, how errors get caught before they compound, how progress gets checkpointed, when a human needs to step in and redirect.

The interesting part isn't that the agent could write code for that long. It's what kind of scaffolding makes that possible without the whole thing drifting off course.

That's the actual engineering problem in agentic coding right now. Not "can it code," but "can it stay reliable, correctable, and on-task across thousands of steps."

Most businesses experimenting with AI agents will never run a job that large. But the same principle applies at smaller scale: the orchestration around the model, not the model itself, is what determines whether an agent is production-ready or just a good demo.

What's the longest-running agent task you've seen someone actually document in public?

## Sources

- hackernews: https://momo5502.com/posts/2026-10-09-game-decompilation/
