# Lark AI LinkedIn Content Agent

Implements `docs/BOT_PROMPT.md` (policy), `docs/BRAND.md` (voice, wins on conflicts) and `docs/RUNBOOK.md` (mechanics) as a standalone Python agent.

## What it does

| Lane | Command | Output |
|---|---|---|
| 1 PM post | `python -m agent.cli run --lane post` | Single-image post |
| 8 PM carousel | `python -m agent.cli run --lane carousel` | Branded educational PDF carousel (1080x1350) |

Each run: comment pass first, then Apify discovery (YouTube, TikTok, Instagram; one scrape per day shared by both lanes), clustering and scoring, dedup against the rolling 14-day topic log, security-story verification, caption with a slop gate (rule checks plus an LLM editor, 3 attempts), image with a vision gate (or slides with a vision review), then stage or publish.

## Modes (`mode.txt` or `AGENT_MODE`)

- `approve` (default, start here): nothing is sent. A draft is saved in `drafts/`, you get a notification, then run `python -m agent.cli approve --lane post` (or `skip`). Approving also sends the drafted comment replies.
- `auto`: publishes directly after all gates pass and sends up to 3 replies per post per run.

## Setup

```bash
cd linkedin-agent
pip install -r requirements.txt
cp .env.example .env     # fill in keys
python -m agent.cli status
python -m agent.cli run --lane post     # approve mode: stages a draft only
```

Scheduling (Lagos time, adjust `TZ`): 

```
0 13 * * *  cd /path/linkedin-agent && python -m agent.cli run --lane post
0 20 * * *  cd /path/linkedin-agent && python -m agent.cli run --lane carousel
0 */4 * * * cd /path/linkedin-agent && python -m agent.cli comments
```

## Things you must do or check

1. **Rotate your Apify token.** The original RUNBOOK contained a live-looking token. This project reads it only from `APIFY_TOKEN`.
2. **LinkedIn access.** Create an app, get `w_member_social` for posting. Reading comments needs `r_member_social`, a restricted product that needs LinkedIn approval. Without it, the comment pass logs a warning and skips; posting still works.
3. **Set `LINKEDIN_API_VERSION`** to a currently supported `YYYYMM` version (LinkedIn retires old ones). Posting uses `/rest/posts`, `/rest/images`, `/rest/documents`.
4. **Image provider.** Defaults to NVIDIA FLUX (`NVIDIA_API_KEY`); set `IMAGE_PROVIDER=openai` to use OpenAI images instead.
5. **Fonts.** The carousel looks for `fonts/Poppins-{Bold,SemiBold,Medium,Regular}.ttf` and falls back to DejaVu. Drop the Poppins TTFs into `fonts/` for the intended look.
6. The code was syntax-checked and the carousel renderer and rule checks were run offline. Apify, LinkedIn, image, and Anthropic calls were **not** run live here, so test in `approve` mode first.

## Layout

```
agent/  config, state, discovery, selector, writer, image, carousel, linkedin, comments, notify, pipeline, cli
docs/   BOT_PROMPT.md, BRAND.md, RUNBOOK.md
state/  published.json, topics.json, discovery-latest.json
drafts/ images/ carousels/
```

## Guardrails built in

- Dry-run by default in the LinkedIn client; only `publish=True` sends.
- Max one post per lane per day.
- Security stories are covered only if two independent sources corroborate them (otherwise skipped with a note).
- Banned phrases, hashtag/emoji caps and no em dashes enforced before the LLM review. Captions never invent builds, stats or experiences.
- Failure is a valid outcome: if the gates reject everything, nothing is published and you are notified.
