# Ecom Django app: Docker and EC2 deployment

This project runs as a non-root Django/Gunicorn container. Docker Compose persists the SQLite database and uploaded media in named volumes. GitHub Actions runs Django checks and tests, then copies the project to EC2 and deploys it with Docker Compose when code is pushed to `main`.

The app is available at `http://<EC2-public-DNS>:8000/products/`.

## Run locally with Docker

1. Copy `.env.example` to `.env`.
2. Set `DJANGO_SECRET_KEY` to a long random value and `DJANGO_ALLOWED_HOSTS` to `localhost,127.0.0.1`.
3. Run:

   ```sh
   docker compose up --build
   ```

4. Open `http://localhost:8000/products/`.

The first start automatically runs database migrations and collects static files.

## Prepare EC2 once

1. Launch an Ubuntu 24.04 EC2 instance and assign a stable public address or DNS name.
2. Install Docker Engine, the Compose plugin, and rsync. For Ubuntu's packages, run:

   ```sh
   sudo apt-get update
   sudo apt-get install -y docker.io docker-compose-v2 rsync
   sudo systemctl enable --now docker
   sudo usermod -aG docker "$USER"
   ```

   Reconnect after adding the account to the `docker` group. Ensure it can run `docker compose` without `sudo`.
3. Create the deployment directory and grant ownership to the deployment account:

   ```sh
   sudo mkdir -p /opt/ecom
   sudo chown "$USER":"$USER" /opt/ecom
   ```

4. Configure the instance security group:
   - Allow SSH (TCP 22) only from the deployment runner's trusted static egress IP. Do not expose SSH to `0.0.0.0/0`. GitHub-hosted runner addresses change; use a self-hosted runner or another controlled static-egress setup rather than opening SSH to the world.
   - Allow TCP 8000 only from the intended client addresses. This starter exposes HTTP directly; use a TLS-terminating reverse proxy or load balancer before serving real users.

## Configure GitHub Actions

In the GitHub repository, open **Settings → Secrets and variables → Actions → New repository secret** and add:

| Secret | Value |
| --- | --- |
| `EC2_HOST` | EC2 public DNS name or IP |
| `EC2_USER` | Linux account that owns `/opt/ecom` and can run Docker |
| `EC2_SSH_KEY` | Private SSH key for that account (never commit it) |
| `EC2_KNOWN_HOSTS` | Verified host-key line(s) for the EC2 host |
| `DJANGO_SECRET_KEY` | A unique, long random Django secret |
| `DJANGO_ALLOWED_HOSTS` | Comma-separated hostnames, e.g. `ec2-203-0-113-10.compute-1.amazonaws.com,www.example.com` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Optional comma-separated full origins, e.g. `https://www.example.com` |

Set `EC2_KNOWN_HOSTS` to the host-key entry for the same host used in `EC2_HOST`. Obtain it with `ssh-keyscan -H <EC2_HOST>` and verify the host-key fingerprint through a trusted channel before saving it. Do not disable SSH host-key checking.

Push to the `main` branch (or run the workflow manually from the Actions tab). The workflow tests the project first, then deploys it to `/opt/ecom`. On EC2, Docker Compose rebuilds the image, applies migrations, collects static files, and restarts the service. The `.env` file is written from GitHub secrets on each deployment and excluded from the copied source.

## Data and operations

- Database and uploaded media survive container rebuilds in Docker volumes `ecom_data` and `ecom_media`.
- Back up those volumes before destructive maintenance. `docker compose down -v` deletes them.
- View deployment logs on EC2 with `cd /opt/ecom && docker compose logs -f web`.
- For production traffic, configure HTTPS and set `DJANGO_CSRF_TRUSTED_ORIGINS` to the HTTPS origin(s).
