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
  Set it in `.env` (or the compose `environment:` block) and restart.

Set a `NOTIFY_WEBHOOK_URL` (Slack/Discord) in `.env` so you actually see the pings —
on a headless server that webhook is your only notification channel.

---

## Option A — Docker (recommended)

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

## Option B — No Docker (plain VPS + cron)

```bash
rsync -av --exclude .venv ~/linkedin-agent/ user@server:~/linkedin-agent/
ssh user@server
cd ~/linkedin-agent
python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
sudo timedatectl set-timezone Africa/Lagos      # so cron times match
crontab -e        # paste the three lines below
```

```cron
0 13 * * *  cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli run --lane post      >> logs/cron.post.log 2>&1
0 20 * * *  cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli run --lane carousel  >> logs/cron.carousel.log 2>&1
0 */4 * * * cd /home/user/linkedin-agent && ./.venv/bin/python -m agent.cli comments             >> logs/cron.comments.log 2>&1
```

---

## Security
- `.env` holds live secrets. Keep the server locked down (SSH keys only, firewall).
- The secrets shared in chat during setup (Apify, NVIDIA, Anthropic, LinkedIn client
  secret) should be **rotated** before this runs unattended.
- The LinkedIn access token expires ~every 60 days — re-run `get_linkedin_token.py`
  (locally) and update `.env` on the server, or implement refresh-token renewal.
