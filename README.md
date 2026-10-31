# Login Alert Bot (Telegram)

Sends English Telegram alerts about login attempts on your Linux server, accepted or rejected.

## What it reports
- SSH: successful logins, failed passwords, invalid users, max-attempts exceeded, dropped pre-auth connections, scans
- `sudo` and `su` authentication failures
- Per alert: result (accepted/rejected), server, time, username, auth method, SSH key fingerprint, source IP and port,
  country (with flag), city, region, ZIP, coordinates + map link, timezone, local time there, ISP, organization, AS,
  proxy/VPN/Tor, hosting/datacenter and mobile flags, reverse DNS, links to AbuseIPDB / Shodan / VirusTotal, raw log line
- Brute-force detection: counts attempts per IP, lists usernames tried, escalates to a BRUTE-FORCE alert
- Warns when a login succeeds right after many failures from the same IP
- Map pin for successful logins and brute force
- Throttling: alerts at attempt 1, 5, 10, 25, 50, 100, 250, 500, then every 500, so you are not spammed

## Setup
1. Create a bot with @BotFather, copy the token.
2. Get your chat id (message @userinfobot).
3. Send any message to your new bot once, so it can write to you.
4. On the server:

```bash
sudo mkdir -p /opt/login-alert-bot
sudo cp bot.py requirements.txt .env.example /opt/login-alert-bot/
cd /opt/login-alert-bot
sudo pip3 install -r requirements.txt     # or: sudo apt install python3-requests
sudo cp .env.example .env && sudo nano .env
sudo chmod 600 .env
python3 bot.py --test                      # preview alerts, sends nothing
sudo cp /path/to/login-alert-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now login-alert-bot
journalctl -u login-alert-bot -f
```

## Notes
- GeoIP uses the free ip-api.com (about 45 requests/min, HTTP only). Results are cached 24h.
- On CentOS/RHEL or when there is no journald auth log, set `LOG_SOURCE=file` and `LOG_FILE=/var/log/secure`.
- Only monitors this server's own logs. It does not track logins to other machines.
