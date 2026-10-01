# RUNBOOK — LinkedIn Content Automation daily run

Mechanics for executing BOT_PROMPT.md in this workspace. The policy lives in BOT_PROMPT.md; this file tells you which tools to call and where state goes.

## Mode

Read `/workspace/linkedin-content-bot/mode.txt`. Value is `approve` or `auto`.

- **approve** — nothing is sent. Every publish and every comment reply is staged and delivered for Paul's approval.
- **auto** — publishes directly after all quality gates pass.

## State files

- `state/published.json` — array of records: `{date, postUrn, topic, hook, caption, imagePrompt, imagePath, sources[]}`. Append after every successful publish.
- `state/topics.json` — recent topics covered (rolling 14 days), for dedup.
- `drafts/YYYY-MM-DD.md` — today's staged draft.
- `images/` — generated visuals.

## Per-run procedure (in order)

### 1. Comment pass (first, so replies land within 24h)
- Load post URNs from `state/published.json` (last 7 days).
- `linkedin_list_comments` on each. Classify per BOT_PROMPT §13.
- Draft replies per §14-16.
- **approve mode:** include drafted replies in the approval notification. Do NOT send.
- **auto mode:** send via `linkedin_reply_comment` with `publish:true`, max 3 replies per post per run, varied wording.

### 2. Trend discovery (BOT_PROMPT §2-4)
Call Apify's **REST API directly from bash** — do NOT use the Apify MCP tools (they are denied on unattended turns). Verified working Sep 30.

Token handling (never inline the token in a URL or command string):
```bash
export APIFY_TOKEN="$(assistant credentials reveal --service 'Apify' --field 'api_token')"
```
Then in a python script read `os.environ['APIFY_TOKEN']` and use `Authorization: Bearer` headers.

One-call pattern per platform (synchronous, returns dataset items):
`POST https://api.apify.com/v2/acts/{user}~{actor}/run-sync-get-dataset-items` with a JSON body and `Authorization: Bearer $APIFY_TOKEN`.

Actors and inputs (keep result counts small, ~10-20 each; these are pay-per-result):
- **YouTube** — `streamers~youtube-scraper`: `{"searchQueries": ["AI agents", "Claude Code", "AI automation business"], "dateFilter": "week", "maxResults": 10, "sortingOrder": "relevance"}`
- **TikTok** — `clockworks~tiktok-scraper`: `{"searchQueries": ["AI agents", "automation"], "searchSection": "/video", "resultsPerPage": 15}`
- **Instagram** — `apify~instagram-scraper` with `directUrls` (the `search` param returns junk): `{"directUrls": ["https://www.instagram.com/explore/tags/aiagents/"], "resultsType": "posts", "resultsLimit": 15, "onlyPostsNewerThan": "1 day"}` (rotate the tag URL: #aiagents, #claudecode, #automation, #buildinpublic)

If a call fails or network is blocked on the scheduled run, fall back to `web_search` with freshness filters (past day / past week) on the same topics. Extract underlying ideas (never copy wording), cluster, score per §4.

**Save the raw results with a timestamp** to `/workspace/linkedin-content-bot/state/discovery-latest.json` — the 8 PM carousel lane reuses this scrape so the platform pays for discovery once per day, not twice.

### 3. Selection and dedup (§5)
Check `state/topics.json` and `state/published.json`. No repeat of topic, hook, structure, or visual concept.

### 3b. Security-story verification lane (BOTH lanes)
When the top-velocity story is a security incident — breach, attack, exploit, leak, hack, malware, credential theft — do NOT skip it for being negative or risky. Cover it if and only if it verifies. Procedure, in order:
1. **Research before writing.** Run web_search on the story with several distinct queries (incident name, vendor/product name + "breach"/"incident", official domain). Find at least TWO independent corroborating sources beyond the viral video/post — a vendor statement, official blog, reputable news outlet, or regulator/CERT filing.
2. **Verify before covering.** Only proceed if you can name the specific corroborating sources and what they confirm. State the confirmed facts only: what happened, who is affected, what was confirmed vs. still unknown.
3. **If unverifiable, skip with a note.** Say so in the run notification: `SKIPPED (unverified security story): <story> — could not corroborate with independent sources`. Then pick the next-highest-velocity topic and continue the run normally.
4. **Never** invent details, casualty/scale numbers, or attribution. No "sources say" without sources. Speculation and unconfirmed claims stay out of captions and slides entirely.

### 4. Caption (§6-8, gate §11)
**Brand voice is mandatory** — read `/workspace/linkedin-content-bot/BRAND.md` first and write in that voice. Where BOT_PROMPT §7-8 and BRAND.md disagree, BRAND.md wins. Key rules from the brand: lead with the business problem, show the workflow/mechanism, connect technology to outcomes, clear + conversational + technical + confident, short paragraphs, strong first sentence, end with a natural question or invitation when appropriate. Never: hype ("10x", "game changer", "revolutionary"), fake statistics, guaranteed results, overpromised autonomy, sales pitch in every post. First-person experience must be genuinely Paul's: he runs Lark AI Agency, builds agentic AI, n8n/make/Zapier automation, CRM/GTM systems, and Claude Code applications. Never invent builds, anecdotes, stats, or results.

### 5. Image (§9-10)
```
python3 /workspace/bin/nvidia_image_gen.py "<image prompt>" --output-dir /workspace/linkedin-content-bot/images --filename YYYY-MM-DD-<slug>
```
- The script raises loudly on CONTENT_FILTERED and black-placeholder results. Rework the prompt once, then try a different visual concept once. If it still fails, publish text-only and say so in the notification.
- After generation, view the image (file_read) and apply the §10 gate. Regenerate once if it fails; text-only is better than a bad image.

### 6. approve mode — publish path
- Save `drafts/YYYY-MM-DD.md` with: caption, image path, image prompt, sources, drafted comment replies.
- Send ONE notification:
  ```
  assistant notifications send --source-channel scheduler --title "LinkedIn post ready — approval needed" --message "<hook> <full caption> Image: <path>. Sources: <urls>. [Drafted comment replies if any.] Open this schedule's conversation and reply 'publish' to post it, or 'skip' to discard."
  ```
- Do NOT call `linkedin_post` with `publish:true`. End the run.
- When Paul replies **publish** in the run conversation: call `linkedin_post` with `{text, imagePath, publish:true}`, append the record to `state/published.json`, confirm briefly.
- When Paul replies **skip**: mark it discarded in state, post nothing.

### 7. auto mode — publish path
- `linkedin_post` with `{text, imagePath, publish:true}`.
- Append the full record to `state/published.json` and the topic to `state/topics.json`.
- Send the §20 execution summary via `assistant notifications send --source-channel scheduler --title "LinkedIn post published"`.

### 8. Failure is a valid outcome
If no viable topic, or gates reject everything, do NOT publish something marginal. Send a short notification explaining what blocked, and stop.

## Hard rules

- The posting server dry-runs by default; `publish:true` is the only send path.
- Never expose tokens or secrets in output.
- Max one new post per day from this job.
- If the notification pipeline fails, still log the draft to disk before ending the run.

---

# CAROUSEL LANE — daily 8:00 PM (separate schedule)

The 8 PM post is a **branded document carousel** (PDF), different from the 1 PM single-image post. Same policy file, same mode.txt, same state logs, but:

### Topic selection — VIRAL-FIRST, EDUCATIONAL FORMAT
The carousel's job: find the **AI topic going viral right now** (Apify discovery, step 2 above) and turn it into **educational carousel content** that teaches the underlying idea.
- Discovery is REQUIRED, not optional. Read `/workspace/linkedin-content-bot/state/discovery-latest.json` — if it exists and is from today, reuse it (both lanes share one scrape; do not pay twice). If missing or stale, run the discovery step yourself and save results there with a timestamp.
- Pick the highest-velocity AI topic NOT already in `state/topics.json`. Velocity over lifetime views (BOT_PROMPT §2 freshness rules apply).
- **Security stories go through the verification lane (step 3b above) — same rules, both lanes.** Verified breach/attack topics are fair game for educational carousels (e.g. "how the attack actually worked"); unverified ones are skipped with a note in the run notification.
- Educational format: teach it. Hook slide → what it is / why it's blowing up → 3-6 slides explaining the mechanism, steps, or lessons → practical takeaway → CTA. The reader must leave knowing something they can use.
- Originality rule (BOT_PROMPT §6) still applies: teach the idea in Paul's voice with his interpretation — never copy the source's wording or story.
- Must still fit a content pillar in BRAND.md §7. A viral topic that can't be taught through his pillars is the wrong topic.

### Slide build
1. Draft a slide spec (5-9 slides, last one is CTA): JSON with `slides: [{kicker, headline, sub?, bullets?}, ...]`, title field. Hook slide → teaching slides → CTA slide (kicker "CTA" renders the Lark AI Agency footer).
2. Render: `python3 /workspace/bin/carousel_builder.py <spec.json> --output-dir /workspace/linkedin-content-bot/carousels/<date>`
   - Brand palette is baked in: navy, emerald #50C878, orange #FFA500 (sparingly), white. 1080x1350 portrait. CTA slide renders on a full emerald background.
   - Brand font is **Poppins** (Bold/SemiBold/Medium/Regular, self-hosted at `linkedin-content-bot/fonts/`, downloaded from Google Fonts) — picked as the closest standard match to the LARK wordmark's geometric rounded sans; brand.md never named a font. If Paul names the real one, swap the TTFs in that directory and everything follows.
   - Optional `--background <image>`: an FLUX-generated texture behind the slides (auto dark overlay). Skip it if the FLUX output is too busy — flat navy is on-brand.
3. View slide-01 and one middle slide (file_read). Regenerate once if text overflows, contrast fails, or it looks cluttered (BRAND.md §9 rules).

### Caption
Same brand-voice rules as step 4 above. Structure: hook → what's inside the carousel → one useful takeaway → soft CTA from the BRAND.md §14 CTA library. Under 3000 chars.

### Publish
`linkedin_post` with `{text, documentPath: <pdf>, publish: true}` — the server uploads the PDF via the official Documents API (`/rest/documents?action=initializeUpload`) and attaches it as a document carousel. Never pass both `imagePath` and `documentPath`.

### Approve mode (same as the 1 PM lane)
Save spec + PDF + caption draft, send ONE approval notification, end the run. On Paul's "publish" reply: upload + publish, log to state. On "skip": discard, log nothing to published.json.
