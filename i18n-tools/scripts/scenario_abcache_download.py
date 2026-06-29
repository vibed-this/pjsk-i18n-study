"""Download AssetBundles via sssekai abcache (official CDN)."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--region", choices=["jp", "cn"], required=True)
    parser.add_argument("--filter", required=True, help="regex on bundleName")
    parser.add_argument("--download-dir", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--app-hash", required=True)
    parser.add_argument("--no-update", action="store_true")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s %(message)s")

    from sssekai.entrypoint.abcache import main_abcache

    class Cfg:
        proxy = None
        db = str(args.db)
        no_update = args.no_update
        dump = None
        app_region = args.region
        app_platform = "android"
        app_version = args.app_version
        app_appHash = args.app_hash
        app_abVersion = None
        app_asset_host = None
        app_asset_version = None
        app_asset_hash = None
        download_no_overwrite = False
        download_filter = args.filter
        download_filter_cache_diff = None
        download_dir = str(args.download_dir)
        download_ensure_deps = False
        download_workers = args.workers
        dump_master_data = None
        dump_user_data = None
        keep_compact = False
        auth_credential = None

    args.download_dir.mkdir(parents=True, exist_ok=True)
    main_abcache(Cfg())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())