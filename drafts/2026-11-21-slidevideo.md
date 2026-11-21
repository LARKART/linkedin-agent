# Draft 2026-11-21 (slidevideo)

**Status:** published

**Topic:** Semantic governance policies for AI agents
**Why now:** Google for Developers just published semantic governance policy tooling for AI agents, and Citi publicly warned customers against third-party AI agents the same day, showing both platform vendors and enterprises converging on pre-action control as the default expectation

## Caption

Google shipped semantic governance policies for AI agents this week. Same day, Citi told customers not to connect third-party AI agents to their accounts.

Different companies, same conclusion: letting an agent act first and reviewing later doesn't scale.

Most agent setups still work like this. The agent calls a tool, does the thing, and someone checks the logs afterward if something breaks. That's fine for a demo. It falls apart once an agent has real access to a calendar, a CRM, or a bank account.

What's changing is where the check happens. Instead of reviewing what an agent did, the platform now checks what it's about to do before it does it. Permission lives in the policy layer, not in the prompt and not in someone's memory of what the agent is allowed to touch.

This matters for anyone building agents into a real workflow. A guardrail you wrote into a system prompt is a suggestion. A guardrail enforced at the platform level is a rule the agent physically cannot break.

If you're putting an agent in front of customer data, payment systems, or anything with downside risk, the question isn't whether the agent is smart enough. It's whether there's a permission check sitting between the agent's decision and the action it's about to take.

That's the boring infrastructure work nobody shows in demos. It's also the part that decides whether an agent is safe to actually deploy.

## Sources

- news: https://news.google.com/rss/articles/CBMitgFBVV95cUxObXJuMFkzWWRTYldvbW55aVVZYThrNFpvVHI3b1VDemh4N1dVMk5kdDF6dW9QVmlBWGxkTlJlQzZFbUw5TnFXMTBncWhpTEFCTl9FdjJLY1hSeHJTZndzZHRlcXdfLUR0c0hiQ3gyVC0wWHFINm5VOTViSEpHTXAzbWs4SnVrWmZnSmpTMHdMYTcwQTN0YWw3Vmc1cm8tODNjcDJiZklzV0R0dC1oY1JBWmJtYkxFZw?oc=5
- news: https://news.google.com/rss/articles/CBMiuAFBVV95cUxPSmNPaURFYldLb1VfcGlrcUdHTkxudWJFdlFwLXZHYi1SMlhzQ2xVaWlhYmdrT3JENHZ4b0hZSjY3YW42bHluWk9NTlJtd003a1YyMm1DblNDOGRQbFhOM0x5d1VVMnJJeEFyNXZYdFRGU2tRRUVUOE9TQ0prc3pSMkxVYVZQX2hudzZ4cXB4czEyQk9Vb0FiSUJCaVpQRERNX19GeHBpalVkRUQ1cldRWFlzdDJDR3NQ?oc=5
