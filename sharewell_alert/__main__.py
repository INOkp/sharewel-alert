from __future__ import annotations

import argparse
import logging
from pathlib import Path

from .config import Config
from .monitor import check_once, print_current, run_loop, send_test_notification, simulate_new_listing


def main() -> None:
    parser = argparse.ArgumentParser(description="Notify Slack when new ShareWel listings appear.")
    parser.add_argument("--once", action="store_true", help="run one check and exit")
    parser.add_argument("--dry-run", action="store_true", help="do not post to Slack or update state")
    parser.add_argument("--print-current", action="store_true", help="print current listing titles and exit")
    parser.add_argument("--send-test-notification", action="store_true", help="send a fixed Slack test message and exit")
    parser.add_argument(
        "--simulate-new-listing",
        action="store_true",
        help="send the current first ShareWel listing title as a simulated new listing and exit",
    )
    parser.add_argument("--interval", type=int, help="override SHAREWEL_CHECK_INTERVAL_SECONDS")
    parser.add_argument("--state-file", type=Path, help="override SHAREWEL_STATE_FILE")
    parser.add_argument(
        "--notify-on-first-run",
        action="store_true",
        help="notify all current listings if the state file does not exist",
    )
    parser.add_argument("--log-level", default="INFO", help="DEBUG, INFO, WARNING, ERROR")
    args = parser.parse_args()

    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(message)s",
    )

    config = Config.from_env().with_overrides(
        interval_seconds=args.interval,
        state_file=args.state_file,
        notify_on_first_run=True if args.notify_on_first_run else None,
    )

    if args.print_current:
        print_current(config)
        return

    if args.send_test_notification:
        result = send_test_notification(config, dry_run=args.dry_run)
        logging.info("test notification sent=%s", result.notified)
        return

    if args.simulate_new_listing:
        result = simulate_new_listing(config, dry_run=args.dry_run)
        logging.info(
            "current=%s simulated_new=%s notified=%s",
            result.current_count,
            len(result.new_listings),
            result.notified,
        )
        for listing in result.new_listings:
            logging.info("simulated new: %s", listing.title)
        return

    if args.once:
        result = check_once(config, dry_run=args.dry_run)
        logging.info(
            "current=%s new=%s seeded=%s notified=%s state=%s",
            result.current_count,
            len(result.new_listings),
            result.seeded,
            result.notified,
            result.state_file,
        )
        for listing in result.new_listings:
            logging.info("new: %s", listing.title)
        return

    run_loop(config, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
