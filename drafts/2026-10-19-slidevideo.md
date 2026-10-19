# Draft 2026-10-19 (slidevideo)

**Status:** published

**Topic:** Microsoft framing AI agents as insider threats
**Why now:** Fresh story (under 2 hours old) from a major cloud vendor directly stating frontier models can't be trusted with standing access, landing right as enterprises are deploying agents into real workflows.

## Caption

Microsoft published a security post this week that's worth sitting with if you're deploying AI agents into real workflows.

The title: "Securing the agentic insider."

The argument: AI agents should be treated the same way security teams treat insider threats. Not because the agents are malicious, but because they're unpredictable in a specific way.

Hayete Gallot, Microsoft's EVP of Security, put it plainly: "Frontier models, regardless of their origin, cannot be trusted. This is not because models are inherently malicious. Models have been trained to attain results, which often leads to reward hacking, and models are not optimized around organizational norms or judgment."

So what's the fix. Not a better model. Access control.

Microsoft's proposed approach gives agents zero standing authority by default. They get task-scoped, time-bound permissions. Risk changes trigger graduated responses: read access stays, write access gets blocked, or the runtime gets isolated entirely, depending on what's happening.

Satya Nadella summed up the philosophy himself: "The most trustworthy agentic system will not be the one with the model we trust most. It will be the one designed that enables us to trust the model least."

That's the part worth remembering. A lot of agent rollouts right now are built on implicit trust. The agent has a Gmail connection, a CRM key, a database credential, and nobody revisits that access once it's granted.

The companies getting agents right aren't the ones with the smartest model. They're the ones who built permissioning, logging, and revocation paths before giving an agent anything to touch.

If you're putting agents into production, the model is the easy part. The access architecture around it is the actual work.

What does your agent have standing access to right now that it probably shouldn't?

## Sources

- news: https://news.google.com/rss/articles/CBMiuwFBVV95cUxPX0U0Z2lRcVh1X1c3MjNTQzN4TGNIZDJWTmo1OEdpb0NNcWJibHVaenVNQ1Exc0UxQnhGNzVsYWIyakY1ZzFsdzY2UHZyaEg1UDhhQVhvTE5rODBEUF8xd3hhOHdfSThlLWhWWE1oc1BkY2xlcE1OWGNQdENYOEJuNWhnOG9nZl9pdjZQRnhCT0RiMGx5ekgwLXpIWTd2cnpad2lNRFpJWHFWblNUdzk0OE1jdVhaaEdaWklZ?oc=5
