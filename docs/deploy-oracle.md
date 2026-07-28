# Deploying AI Career Co-Pilot on Oracle Cloud (Always Free)

A single-pass runbook. Every phase ends with a **CHECKPOINT** — do not continue
until it passes. Most failed deployments come from moving on after a step that
silently didn't work.

Placeholders used throughout:

| Placeholder | Meaning |
|---|---|
| `<VPS_IP>` | Public IP of your instance |
| `<KEY>` | Path to your SSH private key |
| `<DUCK_NAME>` | Your DuckDNS subdomain, without `.duckdns.org` |
| `<DUCK_TOKEN>` | Your DuckDNS token |
| `<WEBPASS>` | Password you choose for the web login |

---

## Phase 0 — Decisions before you touch the console

**Shape.** Only one Always Free shape can run this app:

| Shape | Free RAM | Verdict |
|---|---|---|
| VM.Standard.E2.1.Micro (AMD) | 1 GB | Cannot run Ollama — `llama3.2:3b` needs ~4 GB |
| **VM.Standard.A1.Flex (Ampere ARM)** | **24 GB** | Use this |

Create **one** A1.Flex with the entire free allowance: **4 OCPU / 24 GB RAM**.

**Account type.** Always Free instances are reclaimed after ~7 days of low CPU.
Upgrade the account to **Pay As You Go**. Always Free resources stay free and
become exempt from reclamation. Without this, the VM can be deleted while idle.

**Known limitation.** Voice features will be disabled. `backend/app/config.py`
points `WHISPER_BIN` and `PIPER_BIN` at Windows `.exe` files; on Linux those
paths won't exist and the app degrades to text-only by design. Everything else
works.

---

## Phase 1 — Create the instance

1. Compute → Instances → **Create instance**
2. Image: **Canonical Ubuntu 24.04** (ships Python 3.12, which `requirements.txt` targets)
3. Shape: **VM.Standard.A1.Flex**, 4 OCPU, 24 GB RAM
4. Boot volume: **100 GB** (models are several GB each)
5. Add your SSH public key
6. Assign a **public IPv4 address**

If you hit **"Out of host capacity"** — common for A1 — retry in a different
Availability Domain, or another home region. Not your mistake.

### Make the IP permanent (do it now, not later)

Oracle public IPs are **ephemeral by default**: stop/start the instance and the
IP changes, breaking DNS and every link you shared.

VNIC → **IPv4 Addresses** → edit the public IP → change **Ephemeral → Reserved**.
Still free.

**CHECKPOINT 1**

```bash
ssh -i <KEY> ubuntu@<VPS_IP> "echo connected; uname -m; free -g | head -2"
```

Expect `connected`, `aarch64`, and ~23–24 GB total memory.

---

## Phase 2 — Open the ports (two layers — both required)

Oracle blocks traffic in the cloud **and** on the instance. Missing either makes
the site unreachable with no useful error.

**a) Cloud side** — VCN → Security Lists → Default → Add Ingress Rules:

- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port **80**
- Source `0.0.0.0/0`, IP Protocol TCP, Destination Port **443**

**b) Instance side** — Oracle's Ubuntu images drop everything except SSH:

```bash
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 80 -j ACCEPT
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 443 -j ACCEPT
sudo netfilter-persistent save
```

Never open **8000**, **5173**, or **11434**. They stay on loopback behind nginx.

**CHECKPOINT 2**

```bash
sudo apt update && sudo apt install -y nginx
curl -sI http://<VPS_IP> | head -1     # run from your laptop
```

Expect `HTTP/1.1 200 OK` (the nginx welcome page). If this hangs, one of the two
firewall layers is still closed — fix it now.

---

## Phase 3 — Base packages

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3-venv python3-pip git curl apache2-utils \
                    build-essential python3-dev sqlite3
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt install -y nodejs
```

**CHECKPOINT 3**

```bash
python3 --version    # 3.12.x
node --version       # v20.x
nginx -v
```

---

## Phase 4 — Ollama and models

```bash
curl -fsSL https://ollama.com/install.sh | sh
sudo systemctl enable --now ollama
ollama pull llama3.2:3b
ollama pull llama3.2:1b
ollama pull nomic-embed-text
```

Keep the model resident so the first request after an idle period isn't slow:

```bash
sudo systemctl edit ollama
```

Add these three lines, save, exit:

```ini
[Service]
Environment="OLLAMA_KEEP_ALIVE=-1"
```

```bash
sudo systemctl restart ollama
```

**CHECKPOINT 4**

```bash
curl -s http://127.0.0.1:11434/api/tags | head -c 300
ollama list
```

All three models must appear.

> **Optional upgrade:** you have 24 GB instead of a laptop's 8 GB. The 3B default
> exists only for 8 GB machines. `ollama pull llama3.1:8b` and set
> `CHAT_MODEL=llama3.1:8b` in Phase 6 for noticeably better answers — no code
> change, because the model is a setting, not a constant.

---

## Phase 5 — Upload the code

From **Windows PowerShell** on your laptop:

```powershell
cd "d:\AI Career Co-Pilot Project"
tar -czf cc.tgz --exclude=node_modules --exclude=.venv --exclude=logs --exclude=dist --exclude=.pytest_cache --exclude=.ruff_cache career-copilot
scp -i <KEY> cc.tgz ubuntu@<VPS_IP>:/tmp/
```

On the server:

```bash
sudo mkdir -p /opt
sudo tar -xzf /tmp/cc.tgz -C /opt
sudo chown -R ubuntu:ubuntu /opt/career-copilot
ls /opt/career-copilot
```

**CHECKPOINT 5** — `backend`, `frontend`, `prompts`, and `data` are present.

---

## Phase 6 — Backend environment

This is the phase most likely to fail on ARM. Do it carefully.

```bash
cd /opt/career-copilot/backend
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
```

`sqlite-vec` and `PyMuPDF` need `linux-aarch64` wheels. `build-essential` and
`python3-dev` from Phase 3 cover the fallback to source builds.

Create the server config:

```bash
cat > /opt/career-copilot/backend/.env <<'EOF'
HOST=127.0.0.1
PORT=8000
OLLAMA_URL=http://127.0.0.1:11434
CHAT_MODEL=llama3.2:3b
QUESTION_MODEL=llama3.2:1b
EMBED_MODEL=nomic-embed-text
EOF
```

Keep `HOST=127.0.0.1`. nginx is the only thing that should face the internet.

**CHECKPOINT 6**

```bash
cd /opt/career-copilot/backend
.venv/bin/python -c "import app.main; print('imports OK')"
```

Must print `imports OK`. If a package failed to build, fix it here — nothing
downstream will work otherwise.

---

## Phase 7 — Run the backend as a service

```bash
sudo tee /etc/systemd/system/career-copilot.service >/dev/null <<'EOF'
[Unit]
Description=AI Career Co-Pilot backend
After=network.target ollama.service
Wants=ollama.service

[Service]
User=ubuntu
WorkingDirectory=/opt/career-copilot/backend
ExecStart=/opt/career-copilot/backend/.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now career-copilot
```

**CHECKPOINT 7**

```bash
systemctl is-active career-copilot          # active
curl -s http://127.0.0.1:8000/health        # {"status":"ok", ... "reachable":true ...}
```

If it isn't active: `journalctl -u career-copilot -n 50 --no-pager`

---

## Phase 8 — Build the frontend

```bash
cd /opt/career-copilot/frontend
npm ci
npm run build
ls dist/index.html
```

Vite does **not** run in production. `vite.config.js` and port 5173 are
dev-only; nginx serves `dist/` and takes over the proxying.

**CHECKPOINT 8** — `dist/index.html` exists.

---

## Phase 9 — nginx, with a password

The app has **no login of its own**. Every router in `backend/app/main.py`
(resumes, interviews, review, …) is unauthenticated. Public exposure without
this step means anyone with the URL can read every stored resume.

```bash
sudo htpasswd -c /etc/nginx/.htpasswd client     # set <WEBPASS> when prompted

sudo tee /etc/nginx/sites-available/career-copilot >/dev/null <<'EOF'
server {
    listen 80;
    server_name <DUCK_NAME>.duckdns.org;

    root /opt/career-copilot/frontend/dist;
    index index.html;
    client_max_body_size 30M;

    auth_basic "Career Co-Pilot";
    auth_basic_user_file /etc/nginx/.htpasswd;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location ~ ^/(api|health) {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_read_timeout 900s;
        proxy_send_timeout 900s;
        proxy_buffering off;
    }

    # Unauthenticated probe for uptime monitoring
    location = /healthz {
        auth_basic off;
        proxy_pass http://127.0.0.1:8000/health;
        proxy_read_timeout 10s;
    }
}
EOF

sudo ln -sf /etc/nginx/sites-available/career-copilot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

Three values are dictated by the code, not preference:

- **`proxy_read_timeout 900s`** — `config.py` sets `STRUCTURE_TIMEOUT = 600.0`.
  nginx's 60 s default returns **504** mid-generation.
- **`proxy_buffering off`** — required for streaming responses.
- **`client_max_body_size 30M`** — `MAX_AUDIO_BYTES` is 25 MB.

No CORS change is needed: nginx serves UI and API on the **same origin**, so the
loopback-only `CORS_ORIGINS` list never comes into play.

**CHECKPOINT 9**

```bash
curl -s -u client:<WEBPASS> http://127.0.0.1/health | head -c 120
curl -sI http://127.0.0.1 | head -1        # 401 without credentials = auth works
```

---

## Phase 10 — Free domain and HTTPS

Register a subdomain at **duckdns.org** and point it at `<VPS_IP>`.

```bash
sudo snap install --classic certbot
sudo certbot --nginx -d <DUCK_NAME>.duckdns.org
```

Choose the redirect-to-HTTPS option. Without TLS, the password and every resume
travel in plaintext.

Keep DNS self-healing:

```bash
mkdir -p ~/duckdns
cat > ~/duckdns/duck.sh <<'EOF'
curl -s "https://www.duckdns.org/update?domains=<DUCK_NAME>&token=<DUCK_TOKEN>&ip=" >/dev/null
EOF
chmod +x ~/duckdns/duck.sh
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/duckdns/duck.sh") | crontab -
```

**CHECKPOINT 10**

```bash
curl -sI https://<DUCK_NAME>.duckdns.org | head -1     # 401 with valid TLS
sudo certbot renew --dry-run                            # simulated renewal OK
systemctl is-active snap.certbot.renew.timer            # active
```

An expired certificate is the most common way a "permanent" deployment dies at
day 90.

---

## Phase 11 — Make it survive everything

```bash
# Start on boot
sudo systemctl enable ollama career-copilot nginx

# Security patches without you
sudo apt install -y unattended-upgrades
sudo dpkg-reconfigure -plow unattended-upgrades

# Cap the journal so logs can't fill the disk
sudo mkdir -p /etc/systemd/journald.conf.d
printf '[Journal]\nSystemMaxUse=500M\n' | sudo tee /etc/systemd/journald.conf.d/size.conf
sudo systemctl restart systemd-journald

# Swap, as insurance against an OOM kill mid-generation
sudo fallocate -l 4G /swapfile && sudo chmod 600 /swapfile
sudo mkswap /swapfile && sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab

# Nightly database backup, 14-day retention
sudo mkdir -p /opt/backups && sudo chown ubuntu:ubuntu /opt/backups
(crontab -l 2>/dev/null; echo "0 2 * * * sqlite3 /opt/career-copilot/data/career_copilot.db \".backup '/opt/backups/cc-\$(date +\\%F).db'\" && find /opt/backups -name 'cc-*.db' -mtime +14 -delete") | crontab -
```

Use SQLite's `.backup`, not `cp` — copying a live database can capture a torn
file. Download a copy to your laptop periodically; a backup living only on the
same VPS is not a backup.

**Monitoring:** point **UptimeRobot** (free) at
`https://<DUCK_NAME>.duckdns.org/healthz` with email alerts, so you find out
before your examiner does.

---

## Phase 12 — Final acceptance test

The only test that counts is a real reboot.

```bash
sudo reboot
# wait ~90 seconds, reconnect
```

Then all of these must pass:

```bash
systemctl is-enabled ollama career-copilot nginx    # enabled  enabled  enabled
systemctl is-active  ollama career-copilot nginx    # active   active   active
curl -s -u client:<WEBPASS> https://<DUCK_NAME>.duckdns.org/health | grep '"status":"ok"'
curl -s -u client:<WEBPASS> https://<DUCK_NAME>.duckdns.org/health | grep '"reachable":true'
curl -sI https://<DUCK_NAME>.duckdns.org | head -1
```

Open the site in a browser, log in, and ask one question end-to-end. Expect the
first answer to take a while on CPU — that is normal, not a hang.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Site unreachable, connection times out | One firewall layer still closed | Redo Phase 2 — **both** layers |
| `502 Bad Gateway` | Backend not running | `journalctl -u career-copilot -n 50` |
| `504 Gateway Time-out` during generation | nginx timeout too low | `proxy_read_timeout 900s` in Phase 9 |
| Page loads, app shows **Offline** | Backend down or `/health` not proxied | `systemctl is-active career-copilot`, recheck the `location` block |
| Offline badge, backend up | Ollama down | `systemctl is-active ollama`, `ollama list` |
| `pip install` fails compiling | Missing toolchain on ARM | `sudo apt install build-essential python3-dev` |
| Instance vanished | Idle reclamation | Upgrade account to Pay As You Go (Phase 0) |
| Site broke after stop/start | Ephemeral IP changed | Reserve the IP (Phase 1) |
| Voice features missing | Windows-only binaries | Expected — see Phase 0 |

---

## What is deliberately not exposed

- **8000** (uvicorn) and **11434** (Ollama) stay on `127.0.0.1`
- **5173** does not exist in production — nginx serves the built `dist/`
- The only public surface is nginx on 80/443, password-protected except `/healthz`

## Note for the report

Local-first is this project's design claim (`SOW 6.4`, "privacy by
architecture"). Hosting changes that: resumes now live on a server you
administer rather than the user's machine. Present this deployment as an
**optional access mode**, with loopback-only remaining the default
architecture — and update the "100% local & private" banner wording for the
hosted build so the claim matches reality.
