#!/usr/bin/env python3
"""Storage maintenance entry point for cron or scheduled jobs."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[1]
if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

from app.config import settings  # noqa: E402
from app.db.session import get_db, init_db  # noqa: E402
from app.services import storage_service  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor and clean Pizza Box storage.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Preview cleanup without deleting files.")
    mode.add_argument("--execute", action="store_true", help="Delete files allowed by the retention policy.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON.")
    parser.add_argument("--retention-delivered-days", type=int, default=None)
    parser.add_argument("--retention-temp-hours", type=int, default=None)
    parser.add_argument("--max-backups", type=int, default=None)
    parser.add_argument("--fail-on-critical", action="store_true")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow --execute even when STORAGE_CLEANUP_ENABLED is false.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings.ensure_dirs()
    init_db()

    db = next(get_db())
    try:
        snapshot = storage_service.get_storage_snapshot(db, emit_alerts=True, username="cron")

        if args.execute:
            if not settings.storage_cleanup_enabled and not args.force:
                result = {
                    "skipped": True,
                    "reason": "STORAGE_CLEANUP_ENABLED=false",
                    "snapshot": snapshot,
                    "hint": "Set STORAGE_CLEANUP_ENABLED=true or pass --force.",
                }
            else:
                policy = storage_service.get_storage_policy(
                    dry_run=False,
                    retention_delivered_days=args.retention_delivered_days,
                    retention_temp_hours=args.retention_temp_hours,
                    backup_max_files=args.max_backups,
                )
                result = {
                    "skipped": False,
                    "snapshot": snapshot,
                    "cleanup": storage_service.execute_cleanup(
                        db,
                        policy=policy,
                        username="cron",
                        force=True,
                    ),
                }
        else:
            policy = storage_service.get_storage_policy(
                dry_run=True,
                retention_delivered_days=args.retention_delivered_days,
                retention_temp_hours=args.retention_temp_hours,
                backup_max_files=args.max_backups,
            )
            result = {
                "skipped": False,
                "snapshot": snapshot,
                "cleanup_plan": storage_service.build_cleanup_plan(db, policy=policy),
            }

        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print(_human_summary(result))

        if args.fail_on_critical and snapshot["status"] == "critical":
            return 2
        return 0
    finally:
        db.close()


def _human_summary(result: dict) -> str:
    snapshot = result["snapshot"]
    lines = [
        f"Storage status: {snapshot['status']} ({snapshot['percent_used']}% used)",
        f"Disk: {snapshot['used_gb']} GB used / {snapshot['total_gb']} GB total",
    ]
    if result.get("skipped"):
        lines.append(f"Cleanup skipped: {result['reason']}")
        lines.append(result["hint"])
        return "\n".join(lines)

    cleanup = result.get("cleanup")
    if cleanup:
        lines.append(
            f"Cleanup executed: {cleanup['deleted_files']} files removed, "
            f"{cleanup['freed_mb']} MB freed"
        )
        if cleanup["errors"]:
            lines.append(f"Errors: {len(cleanup['errors'])}")
        return "\n".join(lines)

    plan = result["cleanup_plan"]
    lines.append(f"Cleanup dry-run: {plan['total_files']} files, {plan['total_mb']} MB reclaimable")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
