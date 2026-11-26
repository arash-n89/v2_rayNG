import base64
import html
import json
import re
import socket
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

# ---- edit these ----
CHANNELS = ["irconfig", "Digihub_GP", "DigiHubAI", "proxy_kafee"]  # public channel usernames, without @
PAGES = 5          # pages per channel (~20 posts each)
MAX_OUT = 500      # max configs kept in the subscription
TIMEOUT = 4        # seconds for the TCP check
# --------------------

LINK = re.compile(r'(?:vless|vmess|trojan|ss)://[^\s<>"\'`]+', re.I)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "ignore")


def scrape(channel):
    found, before = [], None
    for _ in range(PAGES):
        url = f"https://t.me/s/{channel}" + (f"?before={before}" if before else "")
        page = fetch(url)
        text = re.sub(r"<br\s*/?>", "\n", page)
        text = html.unescape(re.sub(r"<[^>]+>", " ", text))
        found += [m.rstrip(".,;)]،") for m in LINK.findall(text)]
        ids = [int(i) for i in re.findall(r'data-post="[^"/]+/(\d+)"', page)]
        if not ids or min(ids) == before:
            break
        before = min(ids)
    return found


def b64(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4)).decode("utf-8", "ignore")


def host_port(link):
    try:
        scheme, rest = link.split("://", 1)
        rest = rest.split("#")[0]
        if scheme.lower() == "vmess":
            d = json.loads(b64(rest))
            return d["add"], int(d["port"])
        if scheme.lower() == "ss" and "@" not in rest:
            rest = b64(rest)
        u = urllib.parse.urlsplit("//" + rest)
        return u.hostname, u.port
    except Exception:
        return None


def check(link):
    hp = host_port(link)
    if not hp or not hp[0] or not hp[1]:
        return None
    t = time.time()
    try:
        with socket.create_connection(hp, timeout=TIMEOUT):
            pass
    except OSError:
        return None
    return time.time() - t, link


def main():
    links = []
    for ch in CHANNELS:
        try:
            got = scrape(ch.strip().lstrip("@"))
            print(ch, len(got))
            links += got
        except Exception as e:
            print(ch, "failed:", e)
    links = list(dict.fromkeys(links))
    print("unique:", len(links))

    with ThreadPoolExecutor(64) as ex:
        ok = [r for r in ex.map(check, links) if r]
    ok.sort()
    best = [l for _, l in ok[:MAX_OUT]]
    print("alive:", len(ok), "kept:", len(best))

    if best:  # never overwrite a good list with an empty one
        data = base64.b64encode("\n".join(best).encode()).decode()
        with open("sub.txt", "w") as f:
            f.write(data)


if __name__ == "__main__":
    main()
  
