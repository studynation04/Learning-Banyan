# Deploy Learning Banyan on Hostinger (existing IPv4 site)

This app needs a **VPS**. Hostinger shared hosting cannot run Django.

You already have a website on the VPS **IPv4 address** (no domain). This setup
puts Learning Banyan on **port 8080** so the existing site on port **80** is
not replaced.

| Site | Address |
| --- | --- |
| Existing website | `http://YOUR_VPS_IPV4/` (port 80, unchanged) |
| Learning Banyan | `http://YOUR_VPS_IPV4:8080/` |

No domain and no HTTPS are required. Let’s Encrypt needs a domain name, so this
install stays on HTTP until you add one later.

## 1. Copy the project to the VPS

SSH into the VPS (hPanel → VPS → Browser terminal, or PuTTY).

```bash
sudo mkdir -p /var/www
sudo chown "$USER":"$USER" /var/www
cd /var/www
git clone https://github.com/Sharandeep-Sandhu/Learning-Banyan.git learning-banyan
cd learning-banyan
```

Or upload the project folder with FileZilla / SCP into `/var/www/learning-banyan`.

Python **3.12+** is required (Django 6). Ubuntu 24.04 is fine. On Ubuntu 22.04:

```bash
sudo apt update
sudo apt install -y python3.12 python3.12-venv
```

## 2. Install (does not touch port 80)

```bash
cd /var/www/learning-banyan
sudo bash deploy/hostinger/install.sh
```

The script will:

- create a virtualenv and install `requirements.txt`
- write `.env` with your VPS IP and `PORT=8080`
- run `migrate` + `collectstatic`
- start a **systemd** service named `learning-banyan`
- leave nginx/apache and port 80 alone

## 3. Open port 8080 in two places

1. **Hostinger hPanel** → VPS → **Firewall** → allow **TCP 8080** (this is easy to miss).
2. If `ufw` is enabled, the install script already runs `ufw allow 8080/tcp`.

## 4. Open the site

```
http://YOUR_VPS_IPV4:8080/
http://YOUR_VPS_IPV4:8080/healthz/
http://YOUR_VPS_IPV4:8080/login/          # student / admin login
http://YOUR_VPS_IPV4:8080/admin-panel/    # after admin login
```

Create an admin user:

```bash
sudo -u "$USER" /var/www/learning-banyan/.venv/bin/python \
  /var/www/learning-banyan/manage.py createsuperuser
```

## 5. Useful commands

```bash
sudo systemctl status learning-banyan
sudo journalctl -u learning-banyan -f
sudo systemctl restart learning-banyan
```

After a `git pull` on the VPS:

```bash
cd /var/www/learning-banyan
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart learning-banyan
```

## 6. Optional later: a domain + HTTPS

When you buy a domain:

1. DNS **A** record `@` → VPS IPv4.
2. Point nginx/apache at this app (see `deploy/hostinger/nginx-optional.conf`).
3. In `.env` set:

```
PUBLIC_HOST=yourdomain.com
PUBLIC_PORT=443
PUBLIC_SCHEME=https
SITE_URL=https://yourdomain.com
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com
CSRF_TRUSTED_ORIGINS=https://yourdomain.com,https://www.yourdomain.com
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
PORT=8080
```

4. `sudo systemctl restart learning-banyan`

Until then, keep `PUBLIC_SCHEME=http` and `SECURE_SSL_REDIRECT=False`.

## What not to do

- Do **not** change the VPS OS template (that wipes the existing website).
- Do **not** bind this app to port 80 or 443 while the other site is using them.
- Do **not** set `DEBUG=True` on the VPS.
