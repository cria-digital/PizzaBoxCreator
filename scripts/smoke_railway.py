"""Smoke test for a deployed Pizza Box Agent URL."""

from __future__ import annotations

import argparse
import sys
from urllib.parse import urljoin

import httpx


def _url(base_url: str, path: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", path.lstrip("/"))


def _check(client: httpx.Client, base_url: str, path: str, expected: int = 200) -> None:
    response = client.get(_url(base_url, path))
    if response.status_code != expected:
        raise AssertionError(f"{path}: expected {expected}, got {response.status_code}")
    print(f"ok {path} -> {response.status_code}")


def run(base_url: str, user: str | None, password: str | None) -> None:
    with httpx.Client(timeout=20.0, follow_redirects=False) as client:
        health = client.get(_url(base_url, "/health"))
        health.raise_for_status()
        payload = health.json()
        if payload.get("status") != "ok" or payload.get("database") is not True:
            raise AssertionError(f"/health unhealthy: {payload}")
        print(f"ok /health -> {payload}")

        _check(client, base_url, "/login")
        _check(client, base_url, "/metrics")
        _check(client, base_url, "/api/catalog")

        if user and password:
            login = client.post(
                _url(base_url, "/login"),
                data={"username": user, "password": password, "next": "/"},
            )
            if login.status_code not in (302, 303):
                raise AssertionError(f"login failed: {login.status_code}")
            dashboard = client.get(_url(base_url, "/"), follow_redirects=False)
            if dashboard.status_code != 200:
                raise AssertionError(f"dashboard failed after login: {dashboard.status_code}")
            print("ok authenticated dashboard")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url")
    parser.add_argument("--user")
    parser.add_argument("--password")
    args = parser.parse_args()

    try:
        run(args.base_url, args.user, args.password)
    except Exception as exc:
        print(f"failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
