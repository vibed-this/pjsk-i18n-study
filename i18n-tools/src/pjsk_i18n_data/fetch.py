from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import httpx

from .paths import CACHE_CN, CACHE_DIR, CACHE_JP, SOURCES_LOCK
from .sources import SourcesLock, utc_now_iso, write_json


@dataclass
class FetchResult:
    label: str
    url: str
    path: Path
    count: int
    sha256: str


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fetch_url(url: str, *, timeout: float = 120.0) -> bytes:
    with httpx.Client(timeout=timeout, follow_redirects=True) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.content


def fetch_wordings(
    *,
    sources_path: Path = SOURCES_LOCK,
    cache_dir: Path = CACHE_DIR,
    refresh: bool = False,
) -> tuple[FetchResult, FetchResult]:
    lock = SourcesLock.load(sources_path)
    cache_dir.mkdir(parents=True, exist_ok=True)

    results: list[FetchResult] = []
    for label, url, out_path in (
        ("cn", lock.cn_wordings_url, CACHE_CN),
        ("jp", lock.jp_wordings_url, CACHE_JP),
    ):
        if out_path.exists() and not refresh:
            raw = out_path.read_bytes()
            rows = json.loads(raw.decode("utf-8"))
            results.append(
                FetchResult(
                    label=label,
                    url=url,
                    path=out_path,
                    count=len(rows),
                    sha256=_sha256_bytes(raw),
                )
            )
            continue

        body = fetch_url(url)
        out_path.write_bytes(body)
        rows = json.loads(body.decode("utf-8"))
        results.append(
            FetchResult(
                label=label,
                url=url,
                path=out_path,
                count=len(rows),
                sha256=_sha256_bytes(body),
            )
        )

    # touch lock metadata (non-destructive merge)
    meta_path = cache_dir / "fetch-meta.json"
    write_json(
        meta_path,
        {
            "fetched_at": utc_now_iso(),
            "cn": {"url": results[0].url, "count": results[0].count, "sha256": results[0].sha256},
            "jp": {"url": results[1].url, "count": results[1].count, "sha256": results[1].sha256},
        },
    )
    return results[0], results[1]