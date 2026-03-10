import argparse
import json
import sys
import urllib.request
import urllib.error
import socket
import hashlib
import re
ANSI_GREEN = "\033[92m"
ANSI_RESET = "\033[0m"


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


def _print_output(data, as_json):
    if as_json:
        print(json.dumps(data, indent=2, ensure_ascii=False))
    else:
        print(json.dumps(data, indent=2, ensure_ascii=False))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Gxost: Lightweight OSINT CLI for IP, domain, email, and username checks",
        epilog=ANSI_GREEN
        + (
            "Show help: python gxost.py --help \n"
            " - IP lookup: python gxost.py ip 8.8.8.8 --json \n"
            " - Domain DNS: python gxost.py domain example.com --json \n"
            " - Email checks: python gxost.py email test@example.com --json \n"
            " - Username footprint: python gxost.py username octocat --json \n"
            " \n"
            " usage: gxost.py [-h] {ip,domain,email,username} ... \n"
            " \n"
            " Gxost: Lightweight OSINT CLI for IP, domain, email, and username checks \n"
            " \n"
            " positional arguments: \n"
            "   {ip,domain,email,username} \n"
            "     ip                  Lookup information about an IP address \n"
            "     domain              Resolve DNS records for a domain \n"
            "     email               Validate email and check Gravatar/MX \n"
            "     username            Check username presence on common sites \n"
            " \n"
            " options: \n"
            "   -h, --help            show this help message and exit \n"
        )
        + ANSI_RESET,
        formatter_class=argparse.RawTextHelpFormatter,
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
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
    args = parser.parse_args(argv)
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
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
