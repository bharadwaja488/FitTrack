import importlib.util
import socket
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "smoke_deployment.py"
spec = importlib.util.spec_from_file_location("fittrack_smoke_deployment", SCRIPT)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


def addr_info(ip, family=socket.AF_INET):
    sockaddr = (ip, 443) if family == socket.AF_INET else (ip, 443, 0, 0)
    return family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", sockaddr


@pytest.mark.parametrize("url", [
    "http://fittrack.example.com",
    "https://localhost",
    "https://app.localhost",
    "https://127.0.0.1",
    "https://10.1.2.3",
    "https://169.254.10.20",
    "https://224.0.0.1",
    "https://0.0.0.0",
    "https://192.0.2.10",
    "https://fittrack.example.com:444",
    "https://user:password@fittrack.example.com",
    "https://fittrack.example.com/path",
    "https://fittrack.example.com?token=value",
])
def test_smoke_rejects_unsafe_or_non_origin_urls(url):
    with pytest.raises(ValueError):
        smoke.resolve_public_origin(url)


def test_public_dns_hostname_is_accepted_when_all_answers_are_public(monkeypatch):
    answers = [addr_info("8.8.8.8"), addr_info("2606:4700:4700::1111", socket.AF_INET6)]
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: answers)
    host, port, resolved = smoke.resolve_public_origin("https://fittrack.example.com")
    assert host == "fittrack.example.com"
    assert port == 443
    assert resolved == answers


@pytest.mark.parametrize("ip", [
    "127.0.0.1", "10.1.2.3", "169.254.1.1", "224.0.0.1", "0.0.0.0", "192.0.2.1",
    "::1", "fc00::1", "fe80::1", "ff02::1", "::", "2001:db8::1",
])
def test_dns_results_must_all_be_public(ip, monkeypatch):
    family = socket.AF_INET6 if ":" in ip else socket.AF_INET
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: [addr_info(ip, family)])
    with pytest.raises(ValueError, match="non-public"):
        smoke.resolve_public_origin("https://fittrack.example.com")


def test_a_mixed_public_and_private_dns_answer_is_rejected(monkeypatch):
    monkeypatch.setattr(
        smoke.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [addr_info("8.8.8.8"), addr_info("10.0.0.2")],
    )
    with pytest.raises(ValueError, match="non-public"):
        smoke.resolve_public_origin("https://fittrack.example.com")


def test_smoke_checks_proxy_api_contract_and_deep_route(monkeypatch, capsys):
    responses = [
        (200, {"Cache-Control": "no-store"}, b'{"data":{"status":"ok"}}'),
        (200, {"Cache-Control": "no-store"}, b'{"data":{"google_enabled":false}}'),
        (200, {"Cache-Control": "no-store"}, b'{"data":{"csrf_token":"test-token"}}'),
        (200, {}, b"<!doctype html><html></html>"),
    ]
    requested = []
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: [addr_info("8.8.8.8")])

    def fake_request(url):
        requested.append(url)
        return responses.pop(0)

    monkeypatch.setattr(smoke, "request", fake_request)
    smoke.run("https://fittrack.example.com")
    assert requested == [
        "https://fittrack.example.com/api/health",
        "https://fittrack.example.com/api/auth/providers",
        "https://fittrack.example.com/api/auth/csrf",
        "https://fittrack.example.com/app/activity",
    ]
    assert capsys.readouterr().out.count("PASS") == 4


def test_http_request_is_get_only_and_uses_pinned_addresses(monkeypatch):
    resolved = [addr_info("8.8.8.8")]
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: resolved)
    captured = {}

    class Response:
        status = 200

        def read(self, _limit):
            return b"{}"

        def getheaders(self):
            return [("Cache-Control", "no-store")]

    class FakeConnection:
        def __init__(self, host, port, addresses, timeout):
            captured.update(host=host, port=port, addresses=addresses, timeout=timeout)

        def request(self, method, target, headers):
            captured.update(method=method, target=target, headers=headers)

        def getresponse(self):
            return Response()

        def close(self):
            pass

    monkeypatch.setattr(smoke, "PinnedHTTPSConnection", FakeConnection)
    status, _headers, body = smoke.request("https://fittrack.example.com/api/health")
    assert status == 200
    assert body == b"{}"
    assert captured["method"] == "GET"
    assert captured["addresses"] is resolved
    assert captured["target"] == "/api/health"


def test_redirect_is_not_followed(monkeypatch):
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: [addr_info("8.8.8.8")])
    calls = []

    class RedirectResponse:
        status = 302

        def read(self, _limit):
            return b"sensitive response body must not be echoed"

        def getheaders(self):
            return [("Location", "https://127.0.0.1/private")]

    class RedirectConnection:
        def __init__(self, *_args, **_kwargs):
            calls.append("connect")

        def request(self, method, *_args, **_kwargs):
            assert method == "GET"

        def getresponse(self):
            return RedirectResponse()

        def close(self):
            pass

    monkeypatch.setattr(smoke, "PinnedHTTPSConnection", RedirectConnection)
    with pytest.raises(RuntimeError, match="HTTP 302"):
        smoke.run("https://fittrack.example.com")
    assert calls == ["connect"]


def test_smoke_errors_do_not_echo_response_or_destination(monkeypatch, capsys):
    monkeypatch.setattr(smoke.socket, "getaddrinfo", lambda *_args, **_kwargs: [addr_info("8.8.8.8")])

    class BadConnection:
        def __init__(self, *_args, **_kwargs):
            pass

        def request(self, *_args, **_kwargs):
            raise RuntimeError("password=private-value https://private.example.test")

        def close(self):
            pass

    monkeypatch.setattr(smoke, "PinnedHTTPSConnection", BadConnection)
    assert smoke.main(["--frontend-url", "https://fittrack.example.com"]) == 1
    output = capsys.readouterr().err
    assert "private-value" not in output
    assert "private.example.test" not in output
