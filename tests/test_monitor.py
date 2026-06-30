from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from sharewell_alert.config import Config
from sharewell_alert.monitor import (
    Listing,
    build_listing_details_payload,
    build_new_listings_payload,
    check_once,
    format_new_listings_message,
    load_state,
    save_state,
    send_test_notification,
    simulate_new_listing,
)


def test_config(state_file: Path, notify_on_first_run: bool = False) -> Config:
    return Config(
        api_url="https://example.invalid/api/v1/exhibits",
        site_url="https://sharewel.example",
        slack_webhook_url="https://example.invalid/slack",
        slack_bot_token=None,
        slack_channel_id=None,
        slack_thread_details=True,
        interval_seconds=60,
        state_file=state_file,
        kind="reuse",
        in_stock_only=True,
        expired_also=False,
        limit=150,
        request_timeout_seconds=1.0,
        notify_on_first_run=notify_on_first_run,
        max_pages=2,
        user_agent="test",
    )


class FakeClient:
    def __init__(self, listings: list[Listing]):
        self._listings = listings

    def fetch_listings(self) -> list[Listing]:
        return self._listings


class FakeNotifier:
    def __init__(self) -> None:
        self.sent: list[str] = []
        self.payloads: list[dict[str, object]] = []

    def send_text(self, text: str) -> None:
        self.sent.append(text)

    def send_listings(self, listings: list[Listing]) -> None:
        payload = build_new_listings_payload(listings, "https://sharewel.example")
        self.payloads.append(payload)
        self.sent.append(str(payload["text"]))


class MonitorTests(unittest.TestCase):
    def test_first_run_seeds_without_notification(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            notifier = FakeNotifier()
            result = check_once(
                test_config(state_file),
                client=FakeClient([Listing("1", "desk")]),
                notifier=notifier,
            )

            self.assertTrue(result.seeded)
            self.assertEqual([], result.new_listings)
            self.assertEqual([], notifier.sent)
            self.assertEqual({"1": "desk"}, load_state(state_file).items)

    def test_new_listing_is_notified_and_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            save_state(state_file, {"1": "desk"})
            notifier = FakeNotifier()

            result = check_once(
                test_config(state_file),
                client=FakeClient([Listing("1", "desk"), Listing("2", "chair")]),
                notifier=notifier,
            )

            self.assertFalse(result.seeded)
            self.assertEqual([Listing("2", "chair")], result.new_listings)
            self.assertEqual(
                [
                    "📢新着商品が公開されました‼️\n\n"
                    "> chair\n"
                    "<https://sharewel.example/exhibits/2|商品ページを開く>"
                ],
                notifier.sent,
            )
            self.assertEqual({"1": "desk", "2": "chair"}, load_state(state_file).items)

    def test_dry_run_does_not_write_state_or_notify(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            notifier = FakeNotifier()

            result = check_once(
                test_config(state_file, notify_on_first_run=True),
                dry_run=True,
                client=FakeClient([Listing("1", "desk")]),
                notifier=notifier,
            )

            self.assertEqual([Listing("1", "desk")], result.new_listings)
            self.assertFalse(state_file.exists())
            self.assertEqual([], notifier.sent)

    def test_test_notification_sends_fixed_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            notifier = FakeNotifier()

            result = send_test_notification(test_config(state_file), notifier=notifier)

            self.assertTrue(result.notified)
            self.assertEqual(["ShareWel Alert test notification"], notifier.sent)
            self.assertFalse(state_file.exists())

    def test_simulate_new_listing_sends_first_current_title_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "state.json"
            notifier = FakeNotifier()

            result = simulate_new_listing(
                test_config(state_file),
                client=FakeClient([Listing("1", "desk"), Listing("2", "chair")]),
                notifier=notifier,
            )

            self.assertEqual([Listing("1", "desk")], result.new_listings)
            self.assertTrue(result.notified)
            self.assertEqual(
                [
                    "📢新着商品が公開されました‼️\n\n"
                    "> desk\n"
                    "<https://sharewel.example/exhibits/1|商品ページを開く>"
                ],
                notifier.sent,
            )
            self.assertFalse(state_file.exists())

    def test_format_new_listings_message_quotes_titles_and_links(self) -> None:
        message = format_new_listings_message(
            [
                Listing("a/b", "desk <large>", "https://example.invalid/desk.jpg"),
                Listing("2", "chair"),
            ],
            "https://sharewel.example/",
        )

        self.assertEqual(
            "📢新着商品が2件公開されました‼️\n\n"
            "> desk &lt;large&gt;\n"
            "<https://sharewel.example/exhibits/a%2Fb|商品ページを開く>\n\n"
            "> chair\n"
            "<https://sharewel.example/exhibits/2|商品ページを開く>",
            message,
        )

    def test_build_new_listings_payload_includes_standalone_image_block(self) -> None:
        payload = build_new_listings_payload(
            [Listing("1", "desk", "https://example.invalid/desk.jpg")],
            "https://sharewel.example",
        )

        self.assertEqual("📢新着商品が公開されました‼️", payload["blocks"][0]["text"]["text"])
        self.assertEqual(
            {
                "type": "image",
                "image_url": "https://example.invalid/desk.jpg",
                "alt_text": "desk",
            },
            payload["blocks"][2],
        )

    def test_build_listing_details_payload_includes_details_and_additional_images(self) -> None:
        payload = build_listing_details_payload(
            Listing(
                "1",
                "desk",
                "https://example.invalid/main.jpg",
                (
                    "https://example.invalid/main.jpg",
                    "https://example.invalid/extra.jpg",
                ),
                description="A useful desk",
                owner_name="Owner",
                location="Hongo / Room 101",
                expiration="2026-05-31",
                items=("desk / 在庫: 1 / 状態: clean",),
            ),
            "https://sharewel.example",
        )

        self.assertEqual("詳細情報: desk", payload["text"])
        self.assertEqual("image", payload["blocks"][-1]["type"])
        self.assertEqual("https://example.invalid/extra.jpg", payload["blocks"][-1]["image_url"])


if __name__ == "__main__":
    unittest.main()
