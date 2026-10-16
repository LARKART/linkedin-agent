# Draft 2026-10-16 (slidevideo)

**Status:** published

**Topic:** AI code review catching bugs humans can't triage fast enough
**Why now:** Fresh story (6h old) with strong velocity on HN showing a real production consequence of AI code review at scale, paired with a parallel story of Anthropic's own internal code review process for Claude Code.

## Caption

An AI reviewer found more real bugs in a major open-source project than the maintainers could fix before the planned release.

So the release got delayed.

Not because the tool failed. Because it worked.

This is a pattern worth paying attention to. For years, the assumption was that finding bugs was the hard part. Teams built linters, static analysis, review checklists, all aimed at surfacing problems earlier.

Now a different bottleneck is showing up. AI code review can surface legitimate issues faster than a human team can realistically triage, prioritize, and resolve them.

The constraint didn't disappear. It moved.

It's the same thing I see in automation work outside of code. Once you remove the slow manual step, whatever's downstream becomes the new slow step. Faster lead capture just means someone needs to respond to more leads. Faster data sync just means someone needs to act on more accurate data, sooner.

AI doesn't remove bottlenecks. It relocates them to wherever human judgment still has to happen.

That's not an argument against using these tools. It's an argument for designing the process around the new bottleneck, not the old one. More findings only help if there's a realistic plan for who reviews, prioritizes, and closes them out.

Where do you think the bottleneck moves in your workflow once the first one gets automated away?

## Sources

- hackernews: https://www.theregister.com/databases/2026/10/16/postgres-19-delayed-after-ai-reviewers-find-more-bugs-than-humans-can-fix/5303471
- hackernews: https://claude.dev/blog/solving-code-review-at-anthropic/
