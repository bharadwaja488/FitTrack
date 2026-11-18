"""Read-only GET smoke checks for a public Vercel deployment origin."""
import argparse
import http.client
import ipaddress
import json
import socket
import ssl
import sys
from urllib.parse import urlsplit


LOCAL_SUFFIXES = (".localhost", ".local", ".internal", ".test", ".invalid")


def resolve_public_origin(url, *, allow_path=False):
    """Resolve and validate every destination before pinning requests to it."""
    try:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        parsed_port = parsed.port
        port = 443 if parsed_port is None else parsed_port
    except ValueError:
        raise ValueError("Provide a public HTTPS hostname on port 443.") from None
    host = host.rstrip(".").lower()
    if (parsed.scheme != "https" or not host or parsed.username or parsed.password
            or (not allow_path and parsed.path not in ("", "/"))
            or parsed.query or parsed.fragment or port != 443):
        raise ValueError("Provide a public HTTPS hostname on port 443 without credentials or a query.")
    if "." not in host or host == "localhost" or host.endswith(LOCAL_SUFFIXES):
        raise ValueError("The smoke test accepts public DNS hostnames only.")
    try:
        host = host.encode("idna").decode("ascii")
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("IP literals are not accepted; provide a public DNS hostname.")

    try:
        addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except OSError:
        raise ValueError("The public hostname could not be resolved.") from None
    if not addresses:
        raise ValueError("The public hostname did not resolve to an address.")
    for address_info in addresses:
        try:
            address = ipaddress.ip_address(address_info[4][0])
        except ValueError:
            raise ValueError("The hostname resolved to an invalid network address.") from None
        if (not address.is_global or address.is_private or address.is_loopback or address.is_link_local
                or address.is_multicast or address.is_unspecified or address.is_reserved):
            raise ValueError("The hostname resolved to a non-public network address.")
    return host, port, addresses


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    """HTTPS connection pinned to the already-validated DNS results."""

    def __init__(self, host, port, addresses, timeout=20):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self.addresses = addresses

    def connect(self):
        for family, socktype, proto, _canonname, sockaddr in self.addresses:
            raw_socket = socket.socket(family, socktype, proto)
            raw_socket.settimeout(self.timeout)
            try:
                raw_socket.connect(sockaddr)
                self.sock = self._context.wrap_socket(raw_socket, server_hostname=self.host)
                return
            except OSError:
                raw_socket.close()
        raise OSError("Unable to connect to a validated public address.") from None


def request(url):
    host, port, addresses = resolve_public_origin(url, allow_path=True)
    parsed = urlsplit(url)
    target = parsed.path or "/"
    connection = PinnedHTTPSConnection(host, port, addresses, timeout=20)
    try:
        connection.request("GET", target, headers={"Cache-Control": "no-cache"})
        response = connection.getresponse()
        body = response.read(65_536)
        return response.status, dict(response.getheaders()), body
    except Exception:
        raise RuntimeError("The HTTPS smoke request failed.") from None
    finally:
        connection.close()


def run(frontend_url):
    host, _port, _addresses = resolve_public_origin(frontend_url)
    frontend_url = f"https://{host}"
    checks = [
        ("API health", f"{frontend_url}/api/health", "api"),
        ("authentication providers", f"{frontend_url}/api/auth/providers", "api"),
        ("CSRF bootstrap", f"{frontend_url}/api/auth/csrf", "api"),
        ("activity route refresh", f"{frontend_url}/app/activity", "spa"),
    ]
    for label, url, kind in checks:
        status, headers, body = request(url)
        if status != 200:
            # Redirects are reported and never followed.
            raise RuntimeError(f"{label} returned HTTP {status}.")
        if kind == "api":
            payload = json.loads(body)
            normalized_headers = {key.lower(): value for key, value in headers.items()}
            if "no-store" not in normalized_headers.get("cache-control", "").lower():
                raise RuntimeError(f"{label} response is missing Cache-Control: no-store.")
            if label == "API health" and payload.get("data", {}).get("status") != "ok":
                raise RuntimeError("API health returned an unexpected response.")
            if label == "CSRF bootstrap" and not payload.get("data", {}).get("csrf_token"):
                raise RuntimeError("CSRF bootstrap did not return a token.")
            if label == "authentication providers" and not isinstance(payload.get("data"), dict):
                raise RuntimeError("Authentication providers returned an unexpected response.")
        elif b"<html" not in body[:2048].lower():
            raise RuntimeError("Direct activity navigation did not return the SPA document.")
        print(f"PASS {label}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frontend-url", required=True, help="public HTTPS Vercel deployment origin")
    args = parser.parse_args(argv)
    try:
        run(args.frontend_url)
    except Exception:
        # Do not echo user URLs, response bodies, or resolver/connector details.
        print("Smoke check failed; verify the public HTTPS deployment and expected endpoint responses.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
