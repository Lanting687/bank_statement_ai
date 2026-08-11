# Deploying to a single server (Lightsail or any Ubuntu 22.04 VPS)

Run these on the server itself, after `git clone`-ing the repo and
installing Node.js (see main README for the app's own dev setup; this
covers the production single-server path only).

## 1. Backend: Python venv

```bash
sudo apt install -y python3-venv python3-pip
cd ~/bank_statement_ai
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
deactivate
```

`python-doctr[torch]` is a multi-GB install -- this step takes a while
and needs several GB of free disk space.

## 2. Backend: .env

```bash
cat > ~/bank_statement_ai/.env << 'EOF'
DEEPSEEK_API_KEY=your_key_here
DEEPSEEK_API_URL=https://api.deepseek.com/v1
EOF
chmod 600 ~/bank_statement_ai/.env
```

## 3. Frontend: install and build for production

Optional: set a Google Analytics Measurement ID before building. Next.js
inlines `NEXT_PUBLIC_*` vars into the client bundle at build time, so this
has to be in place *before* `npm run build`, not just set at runtime --
`.env.local` is gitignored, same as the backend's `.env`:

```bash
cat > ~/bank_statement_ai/frontend/.env.local << 'EOF'
NEXT_PUBLIC_GA_ID=G-XXXXXXXXXX
EOF
```

Skip this step if you don't want analytics -- `app/layout.tsx` only
renders the GoogleAnalytics component when this var is set, so it's fully
opt-in.

```bash
cd ~/bank_statement_ai/frontend
npm install
npm run build
cd ..
```

## 4. systemd services

```bash
sudo cp deploy/backend.service /etc/systemd/system/bank-statement-backend.service
sudo cp deploy/frontend.service /etc/systemd/system/bank-statement-frontend.service
sudo systemctl daemon-reload
sudo systemctl enable --now bank-statement-backend
sudo systemctl enable --now bank-statement-frontend
```

Check both came up clean:

```bash
sudo systemctl status bank-statement-backend
sudo systemctl status bank-statement-frontend
```

## 5. Caddy (reverse proxy + automatic HTTPS)

```bash
sudo apt install -y debian-keyring debian-archive-keyring apt-transport-https curl
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/gpg.key' | sudo gpg --dearmor -o /usr/share/keyrings/caddy-stable-archive-keyring.gpg
curl -1sLf 'https://dl.cloudsmith.io/public/caddy/stable/debian.deb.txt' | sudo tee /etc/apt/sources.list.d/caddy-stable.list
sudo apt update
sudo apt install -y caddy
```

Edit `/etc/caddy/Caddyfile` (copy `deploy/Caddyfile` from this repo and
fill in your domain, or use the IP-only `:80` variant if you don't have
one yet), then:

```bash
sudo cp deploy/Caddyfile /etc/caddy/Caddyfile
sudo systemctl reload caddy
```

If using a domain: point its DNS A record at the instance's static IP
before reloading Caddy, or the Let's Encrypt cert request will fail.

## 6. Verify

```bash
curl http://127.0.0.1:8000/api/health   # backend directly
curl -I http://localhost:3000           # frontend directly
```

Then visit the domain (or the instance's static IP) in a browser.

## Redeploying after a code change

```bash
cd ~/bank_statement_ai
git pull
source venv/bin/activate && pip install -r requirements.txt && deactivate
sudo systemctl restart bank-statement-backend
cd frontend && npm install && npm run build && cd ..
sudo systemctl restart bank-statement-frontend
```
