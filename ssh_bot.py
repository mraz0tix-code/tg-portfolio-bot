#!/usr/bin/env python3
"""
Login Alert Bot - sends English Telegram alerts about login attempts
(SSH success / failure, invalid users, brute force, sudo/su failures),
enriched with GeoIP, ISP, proxy/VPN/hosting flags, reverse DNS, local time, etc.

Run:   python3 bot.py            (needs root or membership in group 'adm'/'systemd-journal')
Test:  python3 bot.py --test     (prints sample alerts, sends nothing)
"""
import collections
import html
import ipaddress
import os
import queue
import re
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime

import requests

try:
    from zoneinfo import ZoneInfo
except ImportError:  # python < 3.9
    ZoneInfo = None

# --------------------------------------------------------------------------- config


def load_env(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


load_env(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

TOKEN = ("YOUR_TOKEN")
CHAT_ID = os.getenv("YOUR_CHAT_ID")
LOG_SOURCE = os.getenv("LOG_SOURCE", "journal")  # journal | file
LOG_FILE = os.getenv("LOG_FILE", "/var/log/auth.log")  # use /var/log/secure on RHEL/CentOS
IGNORE_IPS = {x.strip() for x in os.getenv("IGNORE_IPS", "").split(",") if x.strip()}
BRUTE_THRESHOLD = int(os.getenv("BRUTE_THRESHOLD", "5"))  # failures in window => BRUTE FORCE
BRUTE_WINDOW = int(os.getenv("BRUTE_WINDOW", "600"))  # seconds
SEND_LOCATION_PIN = os.getenv("SEND_LOCATION_PIN", "1") == "1"  # map pin for success / brute force
NOTIFY_PRIVATE = os.getenv("NOTIFY_PRIVATE", "1") == "1"  # alerts for LAN/loopback sources
HOSTNAME = socket.gethostname()

MILESTONES = {1, 5, 10, 25, 50, 100, 250, 500}  # failure counts (per IP, per window) that trigger an alert


def log(*a):
    print(datetime.now().strftime("%F %T"), *a, file=sys.stderr, flush=True)


# --------------------------------------------------------------------------- parsing

PATTERNS = [
    ("success", re.compile(
        r"Accepted (?P<method>\S+) for (?P<user>\S+) from (?P<ip>\S+) port (?P<port>\d+)"
        r"(?: ssh2)?(?:: (?P<key>\S+ SHA256:\S+))?")),
    ("failed", re.compile(
        r"Failed (?P<method>\S+) for (?P<invalid>invalid user )?(?P<user>\S+) "
        r"from (?P<ip>\S+) port (?P<port>\d+)")),
    ("max_attempts", re.compile(
        r"maximum authentication attempts exceeded for (?P<invalid>invalid user )?(?P<user>\S+) "
        r"from (?P<ip>\S+) port (?P<port>\d+)")),
    ("preauth_close", re.compile(
        r"Connection closed by (?:authenticating|invalid) user (?P<user>\S+) (?P<ip>\S+) port (?P<port>\d+) \[preauth\]")),
    ("scan", re.compile(
        r"(?:Did not receive identification string from|Unable to negotiate with|"
        r"Connection reset by|banner exchange: Connection from) (?:invalid user \S+ |authenticating user \S+ )?"
        r"(?P<ip>[0-9a-fA-F:.]+)")),
    ("sudo_fail", re.compile(r"sudo: .*authentication failure;.*\suser=(?P<user>\S+)")),
    ("su_fail", re.compile(r"FAILED SU \(to (?P<target>\S+)\) (?P<user>\S+)")),
    ("su_fail", re.compile(r"\bsu: .*authentication failure;.*\suser=(?P<user>\S+)")),
]

FAIL_KINDS = {"failed", "max_attempts", "preauth_close", "scan"}

TITLES = {
    "success": ("✅", "SUCCESSFUL LOGIN"),
    "failed": ("🚫", "LOGIN ATTEMPT REJECTED"),
    "max_attempts": ("🚫", "REJECTED: MAX AUTH ATTEMPTS EXCEEDED"),
    "preauth_close": ("🚫", "CONNECTION DROPPED BEFORE AUTH"),
    "scan": ("🔍", "SUSPICIOUS CONNECTION / SCAN"),
    "sudo_fail": ("⚠️", "SUDO AUTHENTICATION FAILED"),
    "su_fail": ("⚠️", "SU AUTHENTICATION FAILED"),
}


def parse(line):
    for kind, rx in PATTERNS:
        m = rx.search(line)
        if m:
            ev = {k: v for k, v in m.groupdict().items() if v is not None}
            ev["kind"] = kind
            ev["raw"] = line.strip()
            if "invalid" in ev:
                ev["invalid"] = True
            ev["ip"] = ev.get("ip", "").strip("[]")
            return ev
    return None


# --------------------------------------------------------------------------- geo / enrichment

_geo_cache = {}


def geo(ip):
    if not ip:
        return {"none": True}
    try:
        a = ipaddress.ip_address(ip)
    except ValueError:
        return {"error": "not an IP address"}
    if a.is_private or a.is_loopback or a.is_link_local or a.is_reserved:
        return {"local": True}
    c = _geo_cache.get(ip)
    if c and c[0] > time.time():
        return c[1]
    ttl = 86400
    try:
        r = requests.get(
            f"http://ip-api.com/json/{ip}",
            params={"fields": "status,message,country,countryCode,regionName,city,zip,lat,lon,"
                              "timezone,isp,org,as,asname,reverse,mobile,proxy,hosting"},
            timeout=6)
        d = r.json()
        if d.get("status") != "success":
            d = {"error": d.get("message", "lookup failed")}
            ttl = 60
    except Exception as e:  # noqa
        d = {"error": str(e)[:80]}
        ttl = 60
    _geo_cache[ip] = (time.time() + ttl, d)
    return d


def rdns(ip):
    try:
        socket.setdefaulttimeout(3)
        return socket.gethostbyaddr(ip)[0]
    except Exception:  # noqa
        return None


def flag(cc):
    if cc and len(cc) == 2 and cc.isalpha():
        return "".join(chr(0x1F1E6 + ord(c) - 65) for c in cc.upper())
    return ""


def local_time(tz):
    if not (tz and ZoneInfo):
        return None
    try:
        return datetime.now(ZoneInfo(tz)).strftime("%Y-%m-%d %H:%M:%S (%Z, UTC%z)")
    except Exception:  # noqa
        return None


# --------------------------------------------------------------------------- message building


def e(x):
    return html.escape(str(x))


def row(label, value):
    return f"<b>{label}:</b> {value}"


def build(ev):
    kind = ev["kind"]
    icon, title = TITLES[kind]
    brute = kind in FAIL_KINDS and ev.get("count", 0) >= BRUTE_THRESHOLD
    if brute:
        icon, title = "🔥", "BRUTE-FORCE ATTACK DETECTED"
    if kind == "success" and ev.get("prior_fails", 0) >= 3:
        icon, title = "❗", "SUCCESSFUL LOGIN AFTER MANY FAILURES"

    lines = [f"{icon} <b>{title}</b>", ""]
    result = "ACCEPTED ✅" if kind == "success" else "REJECTED ❌"
    lines.append(row("Result", result))
    lines.append(row("Server", f"<code>{e(HOSTNAME)}</code>"))
    lines.append(row("Time", e(datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S %Z (UTC%z)"))))

    if ev.get("user"):
        extra = " (non-existent user)" if ev.get("invalid") else ""
        if ev["user"] == "root":
            extra += " ⚠️ privileged account"
        lines.append(row("Username", f"<code>{e(ev['user'])}</code>{extra}"))
    if ev.get("target"):
        lines.append(row("Target user", f"<code>{e(ev['target'])}</code>"))
    if ev.get("method"):
        lines.append(row("Auth method", f"<code>{e(ev['method'])}</code>"))
    if ev.get("key"):
        lines.append(row("SSH key", f"<code>{e(ev['key'])}</code>"))

    ip = ev.get("ip")
    g = None
    if ip:
        g = geo(ip)
        lines.append("")
        lines.append(row("Source IP", f"<code>{e(ip)}</code>"))
        if ev.get("port"):
            lines.append(row("Source port", f"<code>{e(ev['port'])}</code>"))
        if g.get("local"):
            lines.append(row("Location", "private / local network"))
        elif g.get("error"):
            lines.append(row("Location", "GeoIP lookup unavailable"))
        elif g.get("country"):
            lines.append(row("Country", f"{flag(g.get('countryCode'))} {e(g['country'])} ({e(g.get('countryCode', ''))})"))
            place = ", ".join(x for x in (g.get("city"), g.get("regionName")) if x)
            if place:
                lines.append(row("City / Region", e(place)))
            if g.get("zip"):
                lines.append(row("ZIP", e(g["zip"])))
            if g.get("lat") is not None:
                lat, lon = g["lat"], g["lon"]
                lines.append(row("Coordinates", f"<code>{lat}, {lon}</code> "
                                                f"(<a href=\"https://maps.google.com/?q={lat},{lon}\">map</a>)"))
            if g.get("timezone"):
                lt = local_time(g["timezone"])
                lines.append(row("Timezone", e(g["timezone"])))
                if lt:
                    lines.append(row("Local time there", e(lt)))
            if g.get("isp"):
                lines.append(row("ISP", e(g["isp"])))
            if g.get("org") and g.get("org") != g.get("isp"):
                lines.append(row("Organization", e(g["org"])))
            if g.get("as"):
                lines.append(row("AS", e(g["as"])))
            flags = []
            if g.get("proxy"):
                flags.append("🕵️ proxy/VPN/Tor")
            if g.get("hosting"):
                flags.append("🖥 hosting/datacenter")
            if g.get("mobile"):
                flags.append("📱 mobile network")
            lines.append(row("Flags", ", ".join(flags) if flags else "none"))
        rd = g.get("reverse") if isinstance(g, dict) and g.get("reverse") else rdns(ip)
        if rd:
            lines.append(row("Reverse DNS", f"<code>{e(rd)}</code>"))
        lines.append(row("Lookup", f"<a href=\"https://www.abuseipdb.com/check/{e(ip)}\">AbuseIPDB</a> | "
                                   f"<a href=\"https://www.shodan.io/host/{e(ip)}\">Shodan</a> | "
                                   f"<a href=\"https://www.virustotal.com/gui/ip-address/{e(ip)}\">VirusTotal</a>"))

    if kind in FAIL_KINDS and ev.get("count"):
        lines.append("")
        lines.append(row("Attempts from this IP", f"{ev['count']} in last {BRUTE_WINDOW // 60} min"))
        if ev.get("users_tried"):
            shown = ", ".join(f"<code>{e(u)}</code>" for u in ev["users_tried"][:10])
            more = f" +{len(ev['users_tried']) - 10} more" if len(ev["users_tried"]) > 10 else ""
            lines.append(row("Usernames tried", shown + more))
    if kind == "success" and ev.get("prior_fails"):
        lines.append("")
        lines.append(row("⚠️ Failed attempts before success", f"{ev['prior_fails']} (same IP, last {BRUTE_WINDOW // 60} min)"))
        if ev.get("users_tried"):
            lines.append(row("Usernames tried", ", ".join(f"<code>{e(u)}</code>" for u in ev["users_tried"][:10])))

    lines.append("")
    lines.append(f"<i>Log:</i> <code>{e(ev['raw'][-300:])}</code>")
    return "\n".join(lines), g


# --------------------------------------------------------------------------- telegram


def tg(method, payload):
    for _ in range(5):
        try:
            r = requests.post(f"https://api.telegram.org/bot{TOKEN}/{method}", json=payload, timeout=15)
            if r.status_code == 429:
                time.sleep(r.json().get("parameters", {}).get("retry_after", 5) + 1)
                continue
            if not r.ok:
                log("telegram error:", r.status_code, r.text[:200])
            return r.ok
        except Exception as ex:  # noqa
            log("telegram exception:", ex)
            time.sleep(3)
    return False


outbox = queue.Queue()


def worker():
    while True:
        ev = outbox.get()
        try:
            text, g = build(ev)
            tg("sendMessage", {"chat_id": CHAT_ID, "text": text[:4096], "parse_mode": "HTML",
                               "disable_web_page_preview": True})
            important = ev["kind"] == "success" or ev.get("count", 0) >= BRUTE_THRESHOLD
            if SEND_LOCATION_PIN and important and isinstance(g, dict) and g.get("lat") is not None:
                tg("sendLocation", {"chat_id": CHAT_ID, "latitude": g["lat"], "longitude": g["lon"]})
        except Exception as ex:  # noqa
            log("worker error:", ex)
        time.sleep(0.5)  # gentle on Telegram rate limits


# --------------------------------------------------------------------------- event handling

stats = collections.defaultdict(lambda: {"times": collections.deque(), "users": set()})


def prune(ip, now):
    st = stats[ip]
    while st["times"] and now - st["times"][0] > BRUTE_WINDOW:
        st["times"].popleft()
    if not st["times"]:
        st["users"].clear()
    return st


def is_private(ip):
    try:
        a = ipaddress.ip_address(ip)
        return a.is_private or a.is_loopback or a.is_link_local
    except ValueError:
        return False


def handle(line):
    ev = parse(line)
    if not ev:
        return
    ip = ev.get("ip")
    if ip and ip in IGNORE_IPS:
        return
    if ip and not NOTIFY_PRIVATE and is_private(ip):
        return
    now = time.time()
    kind = ev["kind"]

    if kind in FAIL_KINDS and ip:
        st = prune(ip, now)
        st["times"].append(now)
        if ev.get("user"):
            st["users"].add(ev["user"])
        n = len(st["times"])
        ev["count"] = n
        ev["users_tried"] = sorted(st["users"])
        if not (n in MILESTONES or (n > 500 and n % 500 == 0)):
            return  # throttle: do not spam during a brute-force run
    elif kind == "success" and ip:
        st = prune(ip, now)
        ev["prior_fails"] = len(st["times"])
        ev["users_tried"] = sorted(st["users"])

    outbox.put(ev)

    if len(stats) > 5000:
        for k in list(stats):
            prune(k, now)
            if not stats[k]["times"]:
                del stats[k]


# --------------------------------------------------------------------------- log sources


def follow_journal():
    while True:
        log("following journalctl")
        p = subprocess.Popen(["journalctl", "-f", "-n", "0", "-o", "short-iso", "--no-pager"],
                             stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, errors="replace")
        for line in p.stdout:
            handle(line)
        log("journalctl exited, restarting in 5s")
        time.sleep(5)


def follow_file(path):
    log("following", path)
    f, inode = None, None
    while True:
        try:
            st = os.stat(path)
            if f is None or st.st_ino != inode:
                if f:
                    f.close()
                f = open(path, encoding="utf-8", errors="replace")
                if inode is None:
                    f.seek(0, os.SEEK_END)  # first open: only new lines
                inode = st.st_ino
            line = f.readline()
            if line:
                handle(line)
                continue
            if st.st_size < f.tell():  # truncated
                f.seek(0)
        except FileNotFoundError:
            time.sleep(2)
        time.sleep(0.5)


# --------------------------------------------------------------------------- main

SAMPLES = [
    "2026-10-30T21:40:01+0000 srv sshd[111]: Accepted publickey for alice from 8.8.8.8 port 51234 ssh2: ED25519 SHA256:abc123",
    "2026-10-30T21:40:05+0000 srv sshd[112]: Failed password for invalid user admin from 1.1.1.1 port 40022 ssh2",
    "2026-10-30T21:40:06+0000 srv sshd[113]: Failed password for root from 192.168.1.50 port 40023 ssh2",
    "2026-10-30T21:40:07+0000 srv sshd[114]: Connection closed by authenticating user root 1.1.1.1 port 40024 [preauth]",
    "2026-10-30T21:40:08+0000 srv sshd[115]: Did not receive identification string from 1.1.1.1 port 40025",
    "2026-10-30T21:40:09+0000 srv sudo: pam_unix(sudo:auth): authentication failure; logname=bob uid=1000 euid=0 tty=/dev/pts/0 ruser=bob rhost=  user=bob",
    "2026-10-30T21:40:10+0000 srv su[999]: FAILED SU (to root) bob on pts/1",
    "2026-10-30T21:40:11+0000 srv sshd[116]: error: maximum authentication attempts exceeded for invalid user <b>x</b> from 1.1.1.1 port 40026 ssh2 [preauth]",
]


def main():
    if "--test" in sys.argv:
        for i, s in enumerate(SAMPLES):
            ev = parse(s)
            print(f"--- sample {i + 1}: {ev['kind'] if ev else 'NOT PARSED'}")
            if ev:
                ev["count"] = BRUTE_THRESHOLD if i == 7 else 1
                ev["users_tried"] = ["root", "admin"]
                print(re.sub(r"<[^>]+>", "", build(ev)[0]))
        return
    if not TOKEN or not CHAT_ID:
        sys.exit("Set BOT_TOKEN and CHAT_ID in .env (see .env.example)")
    threading.Thread(target=worker, daemon=True).start()
    tg("sendMessage", {"chat_id": CHAT_ID, "parse_mode": "HTML",
                       "text": f"🟢 <b>Login Alert Bot started</b> on <code>{e(HOSTNAME)}</code>\nSource: {LOG_SOURCE}"})
    if LOG_SOURCE == "file":
        follow_file(LOG_FILE)
    else:
        follow_journal()


if __name__ == "__main__":
    main()
