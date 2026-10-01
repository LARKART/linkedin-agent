# 24/7 cloud deployment

The agent is local by default (runs on your Mac via launchd). To run even when your
Mac is **off**, host it on an always-on machine. It's a small Python app with a few
API keys and file-based state, so any cheap Linux VPS works.

## What moves to the cloud
- The code + `.env` (your API keys) + `fonts/`.
- `state/` and `drafts/` (and `images/`, `carousels/`, `logs/`) — mount these as a
  **persistent volume** so dedup history and staged drafts survive restarts.

## Publish mode
- Start in **approve** (`AGENT_MODE=approve`): it stages drafts and notifies you; you
  approve remotely. Good for the first few days to watch quality.
- Switch to **auto** (`AGENT_MODE=auto`): after the gates pass it publishes on its own.

Set a `NOTIFY_WEBHOOK_URL` (Slack/Discord) so you actually see the pings — on an
unattended runner that webhook is your only notification channel.

---

## Option A — GitHub Actions (chosen; no server to run)

The workflow is already in `.github/workflows/agent.yml`. Schedules (UTC):
`07:00` = 08:00 WAT post, `17:00` = 18:00 WAT carousel, every 4h = comments.

### 1. Push the repo to GitHub (private)
```bash
cd ~/linkedin-agent
gh repo create linkedin-agent --private --source=. --push    # or add a remote + git push
```
`.env` is gitignored and never leaves your machine.

### 2. Add the secrets (Settings → Secrets and variables → Actions → Secrets)
`ANTHROPIC_API_KEY`, `APIFY_TOKEN`, `LINKEDIN_ACCESS_TOKEN`, `LINKEDIN_AUTHOR_URN`,
`NVIDIA_API_KEY`, and optionally `OPENAI_API_KEY`, `NOTIFY_WEBHOOK_URL`.

### 3. Add the variables (same page → Variables tab)
`AGENT_MODE=approve` to start (flip to `auto` when ready). Optional: `IMAGE_PROVIDER`,
`LINKEDIN_API_VERSION`.

### 4. Test now
Actions tab → "LinkedIn agent" → **Run workflow** → command `run`, lane `post`.
In approve mode it stages a draft, commits it back, and uploads it as a run
**artifact** (download to eyeball the caption + image). To publish a staged draft:
Run workflow → command `approve`, lane `post`.

### 5. Go hands-off
Change the `AGENT_MODE` variable to `auto`. From then on the scheduled runs publish
after the gates pass. No approve step needed.

**GitHub Actions caveats**
- Times are UTC and scheduled runs can be **delayed** several minutes under load.
- Scheduled workflows are **auto-disabled after 60 days** with no repo activity —
  the auto-publish commits keep it active, but if you pause it, re-enable in Actions.
- State (`state/`, `drafts/`) is **committed back** to the repo each run for dedup and
  approve. Keep the repo **private**.
- The LinkedIn token expires ~60 days — refresh it locally and update the secret.

---

## Option B — Docker on a VPS

On any VPS with Docker + Docker Compose (DigitalOcean, Hetzner, Fly.io, EC2, …):

```bash
# 1. copy the project to the server (includes .env and fonts/)
rsync -av --exclude .venv ~/linkedin-agent/ user@server:~/linkedin-agent/

# 2. build + start (schedule runs inside the container via supercronic)
cd ~/linkedin-agent/deploy
docker compose up -d --build

# 3. watch it
docker compose logs -f
```

Schedule lives in `deploy/crontab` (container timezone = Africa/Lagos; edit freely).
State persists under `deploy/data/` on the host.

Approve a staged draft remotely (while in approve mode):
```bash
docker compose exec linkedin-agent python -m agent.cli approve --lane post
```

Switch to auto mode: set `AGENT_MODE=auto` in `.env`, then `docker compose up -d`.

---

## Option C — Plain VPS + cron

```bash
rsync -av --exclude .venv ~/linkedin-agent/ user@server:~/linkedin-agent/
ssh user@server
cd ~/linkedin-agent
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
sudo timedatectl set-timezone Africa/Lagos      # so cron times match
crontab -e        # paste the three lines below
```

```cron
0 8 * * *   cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli run --lane post      >> logs/cron.post.log 2>&1
0 18 * * *  cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli run --lane carousel  >> logs/cron.carousel.log 2>&1
0 */4 * * * cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli comments             >> logs/cron.comments.log 2>&1
```

---

## Security
- `.env` holds live secrets. Keep the server locked down (SSH keys only, firewall).
- The secrets shared in chat during setup (Apify, NVIDIA, Anthropic, LinkedIn client
  secret) should be **rotated** before this runs unattended.
- The LinkedIn access token expires ~every 60 days — re-run `get_linkedin_token.py`
  (locally) and update `.env` on the server, or implement refresh-token renewal.
