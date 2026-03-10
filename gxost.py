import argparse
import json
import sys
import urllib.request
import urllib.error
import urllib.parse
import socket
import hashlib
import re
import time
import os
import random
import shutil
ANSI_GREEN = "\033[92m"
ANSI_RESET = "\033[0m"
ANSI_WHITE = "\033[97m"
RAINBOW = ["\033[91m", "\033[93m", "\033[92m", "\033[96m", "\033[94m", "\033[95m"]
RED = "\033[91m"
DARK = "\033[31m"


def _http_get(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Gxost-OSINT)",
            "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content_type = resp.headers.get("Content-Type", "")
            data = resp.read()
            if "application/json" in content_type:
                try:
                    return json.loads(data.decode("utf-8", errors="ignore"))
                except json.JSONDecodeError:
                    return {"raw": data.decode("utf-8", errors="ignore")}
            else:
                return {"raw": data.decode("utf-8", errors="ignore")}
    except urllib.error.HTTPError as e:
        return {"error": f"http_error:{e.code}"}
    except urllib.error.URLError as e:
        return {"error": f"url_error:{getattr(e, 'reason', '')}"}
    except Exception as e:
        return {"error": f"unexpected_error:{e}"}


def _http_head_status(url, timeout=10):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (Gxost-OSINT)"},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status
    except urllib.error.HTTPError as e:
        return e.code
    except Exception:
        return None


def ip_lookup(ip):
    result = {"ip": ip}
    r1 = _http_get(f"https://ipapi.co/{ip}/json/")
    if "error" not in r1:
        result["ipapi"] = r1
    r2 = _http_get(f"https://ipinfo.io/{ip}/json")
    if "error" not in r2:
        result["ipinfo"] = r2
    return result


def _dns_resolve_google(name, qtype):
    return _http_get(f"https://dns.google/resolve?name={name}&type={qtype}")


def domain_dns(domain):
    result = {"domain": domain}
    a = _dns_resolve_google(domain, "A")
    aaaa = _dns_resolve_google(domain, "AAAA")
    mx = _dns_resolve_google(domain, "MX")
    ns = _dns_resolve_google(domain, "NS")
    result["A"] = a.get("Answer", [])
    result["AAAA"] = aaaa.get("Answer", [])
    result["MX"] = mx.get("Answer", [])
    result["NS"] = ns.get("Answer", [])
    try:
        result["resolve"] = socket.gethostbyname(domain)
    except Exception:
        result["resolve"] = None
    return result


def email_checks(email):
    fmt_ok = bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", email))
    domain = email.split("@")[-1] if fmt_ok else None
    gravatar_hash = hashlib.md5(email.strip().lower().encode("utf-8")).hexdigest()
    grav_url = f"https://www.gravatar.com/avatar/{gravatar_hash}?d=404"
    status = _http_head_status(grav_url)
    has_gravatar = status == 200
    mx = domain_dns(domain) if domain else {}
    return {
        "email": email,
        "format_valid": fmt_ok,
        "domain": domain,
        "has_gravatar": has_gravatar,
        "gravatar_status": status,
        "mx_records": mx.get("MX", []),
    }


def username_checks(username):
    sites = {
        "github": f"https://github.com/{username}",
        "gitlab": f"https://gitlab.com/{username}",
        "reddit": f"https://www.reddit.com/user/{username}",
        "devto": f"https://dev.to/{username}",
        "medium": f"https://medium.com/@{username}",
        "twitter": f"https://twitter.com/{username}",
        "instagram": f"https://www.instagram.com/{username}/",
        "tiktok": f"https://www.tiktok.com/@{username}",
        "youtube": f"https://www.youtube.com/@{username}",
        "x": f"https://x.com/{username}",
    }
    result = {"username": username, "profiles": {}}
    for site, url in sites.items():
        status = _http_head_status(url)
        if status is None or status >= 400:
            page = _http_get(url)
            exists = False
            raw = page.get("raw")
            if isinstance(raw, str):
                exists = "404" not in raw.lower()
            result["profiles"][site] = {"url": url, "exists": exists, "status": status}
        else:
            result["profiles"][site] = {"url": url, "exists": True, "status": status}
    return result

def social_media_trace(username):
    base = username_checks(username)
    details = []
    for name, info in base["profiles"].items():
        details.append({"platform": name, "url": info["url"], "exists": info["exists"], "status": info["status"]})
    base["summary"] = {"found": sum(1 for d in details if d["exists"]), "total": len(details)}
    base["details"] = details
    return base

def phone_lookup(number):
    raw = number.strip()
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("00"):
        digits = "+" + digits[2:]
    if not digits.startswith("+") and digits.isdigit():
        digits = "+" + digits
    code_map = {
        "1": "US/Canada",
        "44": "UK",
        "49": "Germany",
        "33": "France",
        "34": "Spain",
        "39": "Italy",
        "90": "Turkey",
        "91": "India",
        "81": "Japan",
        "61": "Australia",
        "55": "Brazil",
    }
    country = None
    for k in sorted(code_map.keys(), key=lambda x: -len(x)):
        if digits.startswith("+" + k):
            country = code_map[k]
            break
    length = len(re.sub(r"\D", "", digits))
    e164_ok = digits.startswith("+") and 8 <= length <= 15
    return {"input": number, "normalized": digits, "country_guess": country, "length": length, "e164_valid": e164_ok}

def metadata_extractor(target):
    t = target.strip()
    def _is_url(x):
        return x.lower().startswith(("http://", "https://"))
    if _is_url(t):
        head_status = _http_head_status(t)
        page = _http_get(t)
        raw = page.get("raw", "")
        title = None
        desc = None
        if isinstance(raw, str):
            m = re.search(r"<title>(.*?)</title>", raw, re.IGNORECASE | re.DOTALL)
            if m:
                title = m.group(1).strip()
            m2 = re.search(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']', raw, re.IGNORECASE | re.DOTALL)
            if m2:
                desc = m2.group(1).strip()
        return {"url": t, "status": head_status, "title": title, "description": desc}
    else:
        p = t
        info = {"path": p, "exists": os.path.isfile(p)}
        if os.path.isfile(p):
            try:
                with open(p, "rb") as f:
                    data = f.read(4096)
                size = os.path.getsize(p)
                sha = hashlib.sha256()
                with open(p, "rb") as f:
                    for chunk in iter(lambda: f.read(8192), b""):
                        sha.update(chunk)
                mime = None
                if data.startswith(b"\xFF\xD8"):
                    mime = "image/jpeg"
                elif data.startswith(b"\x89PNG\r\n\x1a\n"):
                    mime = "image/png"
                elif data.startswith(b"%PDF"):
                    mime = "application/pdf"
                info.update({"size": size, "sha256": sha.hexdigest(), "mime_guess": mime})
            except Exception as e:
                info["error"] = str(e)
        return info

def dark_web_scan(query):
    q = urllib.parse.quote(query)
    res = _http_get(f"https://ahmia.fi/search/?q={q}")
    raw = res.get("raw", "")
    links = []
    if isinstance(raw, str):
        for m in re.finditer(r'href=["\'](https?://[^"\']+?\.onion[^"\']*)["\']', raw, re.IGNORECASE):
            links.append(m.group(1))
    return {"query": query, "results": links[:20], "count": len(links)}

def _print_output(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))

def rainbow_text(s):
    out = []
    for i, ch in enumerate(s):
        out.append(RAINBOW[i % len(RAINBOW)] + ch)
    return "".join(out) + ANSI_RESET

def animate_rainbow_line(s, cycles=1, delay=0.05):
    for c in range(cycles):
        for shift in range(len(RAINBOW)):
            colors = RAINBOW[shift:] + RAINBOW[:shift]
            out = []
            for i, ch in enumerate(s):
                out.append(colors[i % len(colors)] + ch)
            print("\r" + "".join(out) + ANSI_RESET, end="", flush=True)
            time.sleep(delay)
    print()

def _render_big_text(s):
    font = {
        "G": [
            "█████",
            "█    ",
            "█ ███",
            "█   █",
            "█████",
        ],
        "X": [
            "█   █",
            " █ █ ",
            "  █  ",
            " █ █ ",
            "█   █",
        ],
        "O": [
            "█████",
            "█   █",
            "█   █",
            "█   █",
            "█████",
        ],
        "S": [
            "█████",
            "█    ",
            "█████",
            "    █",
            "█████",
        ],
        "T": [
            "█████",
            "  █  ",
            "  █  ",
            "  █  ",
            "  █  ",
        ],
        "6": [
            "█████",
            "█    ",
            "█████",
            "█   █",
            "█████",
        ],
        " ": [
            "     ",
            "     ",
            "     ",
            "     ",
            "     ",
        ],
    }
    s = s.upper()
    lines = [""] * 5
    for ch in s:
        block = font.get(ch, font[" "])
        for i in range(5):
            lines[i] += block[i] + "  "
    return lines

def drip_banner(text):
    os.system("")
    lines = _render_big_text(text)
    for i, row in enumerate(lines):
        color = "\033[91m" if i < 2 else "\033[31m"
        print(color + row + ANSI_RESET)
        time.sleep(0.03)
    width = len(lines[0])
    for d in range(3):
        line = []
        for i in range(width):
            ch = "|" if random.random() < 0.06 else " "
            line.append(ch)
        print("\033[31m" + "".join(line) + ANSI_RESET)
        time.sleep(0.03)

def _pixel_font():
    return {
        "G": [
            "████████",
            "██      ",
            "██  ███ ",
            "██    ██",
            "██    ██",
            "██  █ ██",
            "██    ██",
            "████████",
        ],
        "X": [
            "██    ██",
            " ██  ██ ",
            "  ████  ",
            "   ██   ",
            "  ████  ",
            " ██  ██ ",
            "██    ██",
            "        ",
        ],
        "O": [
            "████████",
            "██    ██",
            "██    ██",
            "██    ██",
            "██    ██",
            "██    ██",
            "████████",
            "        ",
        ],
        "S": [
            "████████",
            "██      ",
            "██████  ",
            "     ██ ",
            "      ██",
            "██    ██",
            "████████",
            "        ",
        ],
        "T": [
            "████████",
            "   ██   ",
            "   ██   ",
            "   ██   ",
            "   ██   ",
            "   ██   ",
            "   ██   ",
            "        ",
        ],
        "6": [
            "████████",
            "██      ",
            "██████  ",
            "██    ██",
            "██    ██",
            "██    ██",
            "████████",
            "        ",
        ],
        " ": [
            "        ",
            "        ",
            "        ",
            "        ",
            "        ",
            "        ",
            "        ",
            "        ",
        ],
    }

def _render_blackbird_text(text):
    font = _pixel_font()
    text = text.upper()
    rows = [""] * len(next(iter(font.values())))
    mask = []
    for ch in text:
        block = font.get(ch, font[" "])
        for i in range(len(block)):
            rows[i] += block[i] + " "
    return rows, mask

def blackbird_banner(text):
    os.system("")
    rows, mask = _render_blackbird_text(text)
    for i, row in enumerate(rows):
        color = "\033[91m" if i < 2 else "\033[31m"
        print(color + row.replace("█", "█") + ANSI_RESET)
        time.sleep(0.02)
    width = len(rows[0])
    drip_rows = 8
    for r in range(drip_rows):
        line = []
        for i in range(width):
            ch = rows[0][i]
            if ch != " " and random.random() < max(0.12 - r * 0.012, 0.02):
                line.append("█")
            else:
                line.append(" ")
        print("\033[31m" + "".join(line) + ANSI_RESET)
        time.sleep(0.02)

def three_d_banner(text):
    os.system("")
    rows, _ = _render_blackbird_text(text)
    layers = 3
    offx = 2
    offy = 1
    for layer in range(layers, 0, -1):
        shade = "\033[31m"
        for i, row in enumerate(rows):
            print(" " * (layer * offx) + shade + row + ANSI_RESET)
        time.sleep(0.02)
    for i, row in enumerate(rows):
        print("\033[91m" + row + ANSI_RESET)
        time.sleep(0.01)

def banner():
    os.system("")
    three_d_banner("GXOST X6")
    print("\033[95mMade with ♥ by Gxost\033[0m")
    animate_rainbow_line("Welcome to Gxost OSINT", cycles=1, delay=0.06)

def clear():
    os.system("cls" if os.name == "nt" else "clear")

def glitch():
    for _ in range(6):
        clear()
        g = ""
        b = (
            "    ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗    ██╗  ██╗ ██████╗ \n"
            "   ██╔════╝ ╚██╗██╔╝██╔═══██╗██╔════╝╚══██╔══╝    ╚██╗██╔╝██╔════╝ \n"
            "   ██║  ███╗ ╚███╔╝ ██║   ██║███████╗   ██║        ╚███╔╝ █████╗   \n"
            "   ██║   ██║ ██╔██╗ ██║   ██║╚════██║   ██║        ██╔██╗ ██╔══╝   \n"
            "   ╚██████╔╝██╔╝ ██╗╚██████╔╝███████║   ██║       ██╔╝ ██╗███████╗ \n"
            "    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝       ╚═╝  ╚═╝╚══════╝ \n"
            "                 ██████╗  ██████╗                                   \n"
            "                 ╚════██╗██╔════╝                                   \n"
            "                  █████╔╝███████╗                                   \n"
            "                  ╚═══██╗██╔════╝                                   \n"
            "                 ██████╔╝╚██████╗                                   \n"
            "                 ╚═════╝  ╚═════╝                                   \n"
        )
        for c in b:
            if c != "\n" and random.random() < 0.04:
                g += random.choice("@#$%&")
            else:
                g += c
        print(RED + g + ANSI_RESET)
        time.sleep(0.08)

def drip():
    b = (
        "    ██████╗ ██╗  ██╗ ██████╗ ███████╗████████╗    ██╗  ██╗ ██████╗ \n"
        "   ██╔════╝ ╚██╗██╔╝██╔═══██╗██╔════╝╚══██╔══╝    ╚██╗██╔╝██╔════╝ \n"
        "   ██║  ███╗ ╚███╔╝ ██║   ██║███████╗   ██║        ╚███╔╝ █████╗   \n"
        "   ██║   ██║ ██╔██╗ ██║   ██║╚════██║   ██║        ██╔██╗ ██╔══╝   \n"
        "   ╚██████╔╝██╔╝ ██╗╚██████╔╝███████║   ██║       ██╔╝ ██╗███████╗ \n"
        "    ╚═════╝ ╚═╝  ╚═╝ ╚═════╝ ╚══════╝   ╚═╝       ╚═╝  ╚═╝╚══════╝ \n"
        "                 ██████╗  ██████╗                                   \n"
        "                 ╚════██╗██╔════╝                                   \n"
        "                  █████╔╝███████╗                                   \n"
        "                  ╚═══██╗██╔════╝                                   \n"
        "                 ██████╔╝╚██████╗                                   \n"
        "                 ╚═════╝  ╚═════╝                                   \n"
    )
    for line in b.split("\n"):
        print(RED + line + ANSI_RESET)
        if random.random() > 0.5:
            spaces = " " * random.randint(0, max(len(line) - 1, 0))
            print(DARK + spaces + "|" + ANSI_RESET)

def matrix():
    width = shutil.get_terminal_size().columns
    chars = "01"
    for _ in range(8):
        line = "".join(random.choice(chars) for _ in range(width))
        print(DARK + line + ANSI_RESET)
        time.sleep(0.04)

def progress():
    width = 40
    for i in range(width + 1):
        bar = "█" * i + "-" * (width - i)
        pct = int((i / width) * 100)
        print(f"\r{RED}SYSTEM BOOT [{bar}] {pct}%{ANSI_RESET}", end="", flush=True)
        time.sleep(0.05)
    print()

def boot():
    steps = [
        "Initializing GXOST X6 Core",
        "Injecting OSINT Framework",
        "Connecting Intelligence Grid",
        "Loading Recon Modules",
        "Deploying Investigation Interface",
        "System Ready",
    ]
    for s in steps:
        print(RED + "[+]" + ANSI_RESET, s)
        time.sleep(0.6)

def intro():
    clear()
    glitch()
    clear()
    drip()
    print()
    matrix()
    progress()
    boot()
    time.sleep(1)
    clear()

def menu():
    intro()
    print("\033[92m[!] Select your operation\033[0m")
    print("\033[93m[!] Please make sure you choose correctly\033[0m")
    print(RED + """ 
 ╔══════════════════════════════════════╗
 ║           GXOST X6 FRAMEWORK         ║
 ║        ELITE OSINT INTERFACE         ║
 ╠══════════════════════════════════════╣
 ║ 1 ▸ Username Intelligence            ║
 ║ 2 ▸ Email Recon                      ║
 ║ 3 ▸ Phone Lookup                     ║
 ║ 4 ▸ Domain Investigation             ║
 ║ 5 ▸ Social Media Trace               ║
 ║ 6 ▸ Metadata Extractor               ║
 ║ 7 ▸ Dark Web Scan                    ║
 ║ 9 ▸ Help                             ║
 ║ 8 ▸ Exit                             ║
 ╚══════════════════════════════════════╝
 """ + ANSI_RESET)
    choice = input(ANSI_WHITE + "Select option: " + ANSI_RESET).strip()
    if choice in ["1", "01"]:
        username = input(ANSI_WHITE + "Enter username: " + ANSI_RESET).strip()
        data = username_checks(username)
        _print_output(data, True)
    elif choice in ["2", "02"]:
        email = input(ANSI_WHITE + "Enter email: " + ANSI_RESET).strip()
        data = email_checks(email)
        _print_output(data, True)
    elif choice in ["3", "03"]:
        number = input(ANSI_WHITE + "Enter phone number: " + ANSI_RESET).strip()
        data = phone_lookup(number)
        _print_output(data, True)
    elif choice in ["4", "04"]:
        domain = input(ANSI_WHITE + "Enter domain: " + ANSI_RESET).strip()
        data = domain_dns(domain)
        _print_output(data, True)
    elif choice in ["5", "05"]:
        user = input(ANSI_WHITE + "Enter username: " + ANSI_RESET).strip()
        data = social_media_trace(user)
        _print_output(data, True)
    elif choice in ["6", "06"]:
        target = input(ANSI_WHITE + "Enter file path or URL: " + ANSI_RESET).strip()
        data = metadata_extractor(target)
        _print_output(data, True)
    elif choice in ["7", "07"]:
        query = input(ANSI_WHITE + "Enter search term: " + ANSI_RESET).strip()
        data = dark_web_scan(query)
        _print_output(data, True)
    elif choice in ["9", "09", "h", "H", "?"]:
        print(RED + """
 ╔══════════════════════════════════════════════════════════════════╗
 ║                           HELP / USAGE                           ║
 ╠══════════════════════════════════════════════════════════════════╣
 ║ 1 ▸ Username Intelligence                                        ║
 ║    Checks popular platforms for handle existence. Returns per-   ║
 ║    site status and a summary (found/total).                       ║
 ║    Example: enter "octocat"                                      ║
 ║                                                                  ║
 ║ 2 ▸ Email Recon                                                  ║
 ║    Validates format, extracts domain, resolves MX with DoH,      ║
 ║    checks Gravatar via HEAD request.                              ║
 ║    Example: enter "test@example.com"                              ║
 ║                                                                  ║
 ║ 3 ▸ Phone Lookup                                                 ║
 ║    Normalizes to E.164, guesses country by prefix, reports       ║
 ║    digit length and validity (no external API).                   ║
 ║    Example: enter "+905551234567"                                 ║
 ║                                                                  ║
 ║ 4 ▸ Domain Investigation                                         ║
 ║    Resolves A/AAAA/MX/NS via Google DoH and attempts host        ║
 ║    resolution. Outputs raw DNS answers.                           ║
 ║    Example: enter "example.com"                                   ║
 ║                                                                  ║
 ║ 5 ▸ Social Media Trace                                           ║
 ║    Aggregated username check with summary and detailed list.      ║
 ║    Example: enter "octocat"                                       ║
 ║                                                                  ║
 ║ 6 ▸ Metadata Extractor                                           ║
 ║    For URL: fetches title/description. For file: size, sha256,    ║
 ║    simple MIME guess (jpeg/png/pdf).                               ║
 ║    Example: "https://example.com" or "C:\\path\\to\\file.jpg"     ║
 ║                                                                  ║
 ║ 7 ▸ Dark Web Scan                                                ║
 ║    Queries Ahmia index; parses .onion links from HTML; no Tor     ║
 ║    required for this step.                                        ║
 ║    Example: enter a keyword like "crash"                          ║
 ║                                                                  ║
 ║ CLI equivalents:                                                  ║
 ║    gxost.py social <user> --json                                  ║
 ║    gxost.py email <addr> --json                                   ║
 ║    gxost.py phone <number> --json                                 ║
 ║    gxost.py domain <name> --json                                  ║
 ║    gxost.py meta <target> --json                                  ║
 ║    gxost.py dark <query> --json                                   ║
 ╚══════════════════════════════════════════════════════════════════╝
 """ + ANSI_RESET)
    elif choice in ["8", "08", "0", "00"]:
        return
    else:
        print("\033[91mInvalid choice\033[0m")
    input(ANSI_WHITE + "Press Enter to return to menu..." + ANSI_RESET)
    menu()

def main(argv=None):
    script = os.path.basename(sys.argv[0]) if sys.argv else "gxost.py"
    parser = argparse.ArgumentParser(
        description="Gxost: Lightweight OSINT CLI for IP, domain, email, and username checks",
        epilog=ANSI_GREEN
        + (
            f"Show help: python {script} --help \n"
            f" - IP lookup: python {script} ip 8.8.8.8 --json \n"
            f" - Domain DNS: python {script} domain example.com --json \n"
            f" - Email checks: python {script} email test@example.com --json \n"
            f" - Username footprint: python {script} username octocat --json \n"
        )
        + ANSI_RESET,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=False)
    p_ip = sub.add_parser("ip", help="Lookup information about an IP address")
    p_ip.add_argument("ip", help="The IP address to query")
    p_ip.add_argument("--json", action="store_true", help="Output JSON")
    p_domain = sub.add_parser("domain", help="Resolve DNS records for a domain")
    p_domain.add_argument("domain", help="The domain to query")
    p_domain.add_argument("--json", action="store_true", help="Output JSON")
    p_email = sub.add_parser("email", help="Validate email and check Gravatar/MX")
    p_email.add_argument("email", help="The email address to inspect")
    p_email.add_argument("--json", action="store_true", help="Output JSON")
    p_user = sub.add_parser("username", help="Check username presence on common sites")
    p_user.add_argument("username", help="The username/handle to check")
    p_user.add_argument("--json", action="store_true", help="Output JSON")
    p_social = sub.add_parser("social", help="Trace username across platforms")
    p_social.add_argument("username", help="The username to trace")
    p_social.add_argument("--json", action="store_true", help="Output JSON")
    p_phone = sub.add_parser("phone", help="Normalize and validate phone number")
    p_phone.add_argument("number", help="Phone number to lookup")
    p_phone.add_argument("--json", action="store_true", help="Output JSON")
    p_meta = sub.add_parser("meta", help="Extract metadata from file or URL")
    p_meta.add_argument("target", help="File path or URL")
    p_meta.add_argument("--json", action="store_true", help="Output JSON")
    p_dark = sub.add_parser("dark", help="Search dark web indexes for a term")
    p_dark.add_argument("query", help="Search term")
    p_dark.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args(argv)
    if not args.cmd:
        menu()
        return
    if args.cmd == "ip":
        data = ip_lookup(args.ip)
        _print_output(data, args.json)
    elif args.cmd == "domain":
        data = domain_dns(args.domain)
        _print_output(data, args.json)
    elif args.cmd == "email":
        data = email_checks(args.email)
        _print_output(data, args.json)
    elif args.cmd == "username":
        data = username_checks(args.username)
        _print_output(data, args.json)
    elif args.cmd == "social":
        data = social_media_trace(args.username)
        _print_output(data, args.json)
    elif args.cmd == "phone":
        data = phone_lookup(args.number)
        _print_output(data, args.json)
    elif args.cmd == "meta":
        data = metadata_extractor(args.target)
        _print_output(data, args.json)
    elif args.cmd == "dark":
        data = dark_web_scan(args.query)
        _print_output(data, args.json)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
