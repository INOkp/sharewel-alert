from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from .config import Config

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class Listing:
    id: str
    title: str
    image_url: str | None = None
    image_urls: tuple[str, ...] = ()
    description: str = ""
    owner_name: str = ""
    location: str = ""
    expiration: str = ""
    items: tuple[str, ...] = ()


@dataclass(frozen=True)
class State:
    items: dict[str, str]


@dataclass(frozen=True)
class CheckResult:
    current_count: int
    new_listings: list[Listing]
    seeded: bool
    notified: bool
    state_file: Path


class ShareWelError(RuntimeError):
    pass


class SlackNotificationError(RuntimeError):
    pass


class ShareWelClient:
    def __init__(self, config: Config):
        self._config = config

    def fetch_listings(self) -> list[Listing]:
        listings: list[Listing] = []
        seen_ids: set[str] = set()
        offset = 0

        for _page in range(self._config.max_pages):
            payload = self._get_json(offset)
            exhibits = payload.get("exhibits")
            if not isinstance(exhibits, list):
                raise ShareWelError("ShareWel API response does not contain exhibits list")

            for exhibit in exhibits:
                listing = _listing_from_exhibit(exhibit)
                if listing is None or listing.id in seen_ids:
                    continue
                listings.append(listing)
                seen_ids.add(listing.id)

            if not exhibits:
                break

            offset += len(exhibits)
            total = _as_int(payload.get("params", {}).get("total"))
            if total is not None and offset >= total:
                break
            if len(exhibits) < self._config.limit:
                break
        else:
            LOGGER.warning("Reached SHAREWEL_MAX_PAGES=%s before exhausting results", self._config.max_pages)

        return listings

    def _get_json(self, offset: int) -> dict[str, Any]:
        params = {
            "kind": self._config.kind,
            "inStock": _bool_param(self._config.in_stock_only),
            "expiredAlso": _bool_param(self._config.expired_also),
            "limit": self._config.limit,
            "offset": offset,
        }
        url = f"{self._config.api_url}?{urlencode(params)}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": self._config.user_agent,
            },
        )

        try:
            with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                return json.loads(response.read().decode(charset))
        except HTTPError as exc:
            raise ShareWelError(f"ShareWel API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise ShareWelError(f"Failed to connect to ShareWel API: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise ShareWelError("ShareWel API returned invalid JSON") from exc


class SlackNotifier:
    def __init__(self, config: Config):
        self._config = config

    def send_payload(self, payload: dict[str, Any]) -> None:
        if not payload.get("text") and not payload.get("blocks"):
            return
        if not self._config.slack_webhook_url:
            raise SlackNotificationError("SLACK_WEBHOOK_URL is not set")

        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = Request(
            self._config.slack_webhook_url,
            data=body,
            headers={
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": self._config.user_agent,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                if response.status < 200 or response.status >= 300:
                    raise SlackNotificationError(f"Slack webhook returned HTTP {response.status}")
        except HTTPError as exc:
            raise SlackNotificationError(f"Slack webhook returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise SlackNotificationError(f"Failed to connect to Slack webhook: {exc.reason}") from exc

    def send_text(self, text: str) -> None:
        if not text:
            return
        self.send_payload({"text": text})

    def send_listings(self, listings: list[Listing]) -> None:
        if not listings:
            return
        if self._can_post_thread_details():
            parent_ts = self._post_message_with_bot(build_new_listings_payload(listings, self._config.site_url))
            if parent_ts and self._config.slack_thread_details:
                self._post_listing_details(parent_ts, listings)
            return

        self.send_payload(build_new_listings_payload(listings, self._config.site_url))

    def _can_post_thread_details(self) -> bool:
        return bool(self._config.slack_bot_token and self._config.slack_channel_id)

    def _post_listing_details(self, parent_ts: str, listings: list[Listing]) -> None:
        for listing in listings:
            self._post_message_with_bot(
                build_listing_details_payload(listing, self._config.site_url),
                thread_ts=parent_ts,
            )

    def _post_message_with_bot(self, payload: dict[str, Any], *, thread_ts: str | None = None) -> str | None:
        if not self._config.slack_bot_token or not self._config.slack_channel_id:
            raise SlackNotificationError("SLACK_BOT_TOKEN and SLACK_CHANNEL_ID are required for thread replies")

        body = {
            "channel": self._config.slack_channel_id,
            "text": payload.get("text") or "",
            "blocks": payload.get("blocks") or [],
            "unfurl_links": payload.get("unfurl_links", True),
            "unfurl_media": payload.get("unfurl_media", True),
        }
        if thread_ts:
            body["thread_ts"] = thread_ts

        request = Request(
            "https://slack.com/api/chat.postMessage",
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self._config.slack_bot_token}",
                "Content-Type": "application/json; charset=utf-8",
                "User-Agent": self._config.user_agent,
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._config.request_timeout_seconds) as response:
                charset = response.headers.get_content_charset() or "utf-8"
                data = json.loads(response.read().decode(charset))
        except HTTPError as exc:
            raise SlackNotificationError(f"Slack Web API returned HTTP {exc.code}") from exc
        except URLError as exc:
            raise SlackNotificationError(f"Failed to connect to Slack Web API: {exc.reason}") from exc
        except json.JSONDecodeError as exc:
            raise SlackNotificationError("Slack Web API returned invalid JSON") from exc

        if not data.get("ok"):
            raise SlackNotificationError(f"Slack Web API error: {data.get('error', 'unknown_error')}")
        ts = data.get("ts")
        return str(ts) if ts else None


def check_once(
    config: Config,
    *,
    dry_run: bool = False,
    client: ShareWelClient | None = None,
    notifier: SlackNotifier | None = None,
) -> CheckResult:
    client = client or ShareWelClient(config)
    notifier = notifier or SlackNotifier(config)

    current = client.fetch_listings()
    state_exists = config.state_file.exists()
    state = load_state(config.state_file)
    current_map = {listing.id: listing.title for listing in current}

    if not state_exists and not config.notify_on_first_run:
        if not dry_run:
            save_state(config.state_file, current_map)
        return CheckResult(
            current_count=len(current),
            new_listings=[],
            seeded=True,
            notified=False,
            state_file=config.state_file,
        )

    new_listings = [listing for listing in current if listing.id not in state.items]

    if dry_run:
        return CheckResult(
            current_count=len(current),
            new_listings=new_listings,
            seeded=False,
            notified=False,
            state_file=config.state_file,
        )

    notified = False
    if new_listings:
        notifier.send_listings(new_listings)
        notified = True

    save_state(config.state_file, current_map)
    return CheckResult(
        current_count=len(current),
        new_listings=new_listings,
        seeded=False,
        notified=notified,
        state_file=config.state_file,
    )


def send_test_notification(
    config: Config,
    *,
    dry_run: bool = False,
    notifier: SlackNotifier | None = None,
) -> CheckResult:
    title = "ShareWel Alert test notification"
    if not dry_run:
        (notifier or SlackNotifier(config)).send_text(title)

    return CheckResult(
        current_count=0,
        new_listings=[Listing(id="test", title=title)],
        seeded=False,
        notified=not dry_run,
        state_file=config.state_file,
    )


def simulate_new_listing(
    config: Config,
    *,
    dry_run: bool = False,
    client: ShareWelClient | None = None,
    notifier: SlackNotifier | None = None,
) -> CheckResult:
    client = client or ShareWelClient(config)
    current = client.fetch_listings()
    if not current:
        return CheckResult(
            current_count=0,
            new_listings=[],
            seeded=False,
            notified=False,
            state_file=config.state_file,
        )

    simulated = current[0]
    if not dry_run:
        (notifier or SlackNotifier(config)).send_listings([simulated])

    return CheckResult(
        current_count=len(current),
        new_listings=[simulated],
        seeded=False,
        notified=not dry_run,
        state_file=config.state_file,
    )


def load_state(path: Path) -> State:
    if not path.exists():
        return State(items={})

    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    items = data.get("items", {})
    if not isinstance(items, dict):
        raise ValueError(f"State file {path} has invalid items")

    return State(items={str(key): str(value) for key, value in items.items()})


def save_state(path: Path, items: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updatedAt": datetime.now(timezone.utc).isoformat(),
        "items": dict(sorted(items.items())),
    }
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    with tmp_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)
        file.write("\n")
    os.replace(tmp_path, path)


def format_new_listings_message(listings: list[Listing], site_url: str) -> str:
    if not listings:
        return ""

    header = "📢新着商品が公開されました‼️"
    if len(listings) > 1:
        header = f"📢新着商品が{len(listings)}件公開されました‼️"

    blocks = [header]
    for listing in listings:
        blocks.append(
            "\n".join(
                [
                    _slack_quote(listing.title),
                    f"<{_listing_url(site_url, listing.id)}|商品ページを開く>",
                ]
            )
        )
    return "\n\n".join(blocks)


def build_new_listings_payload(listings: list[Listing], site_url: str) -> dict[str, Any]:
    text = format_new_listings_message(listings, site_url)
    if not listings:
        return {"text": text}

    blocks: list[dict[str, Any]] = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "📢新着商品が公開されました‼️"
                if len(listings) == 1
                else f"📢新着商品が{len(listings)}件公開されました‼️",
            },
        }
    ]

    for index, listing in enumerate(listings):
        if index > 0:
            blocks.append({"type": "divider"})

        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(
                        [
                            _slack_quote(listing.title),
                            f"<{_listing_url(site_url, listing.id)}|商品ページを開く>",
                        ]
                    ),
                },
            }
        )

        if listing.image_url:
            blocks.append(
                {
                    "type": "image",
                    "image_url": listing.image_url,
                    "alt_text": listing.title[:200] or "ShareWel item image",
                }
            )

    return {
        "text": text,
        "blocks": blocks,
        "unfurl_links": True,
        "unfurl_media": True,
    }


def build_listing_details_payload(listing: Listing, site_url: str) -> dict[str, Any]:
    title_line = "\n".join(
        [
            "*詳細情報*",
            _slack_quote(listing.title),
            f"<{_listing_url(site_url, listing.id)}|商品ページを開く>",
        ]
    )
    blocks: list[dict[str, Any]] = [
        {"type": "section", "text": {"type": "mrkdwn", "text": title_line}}
    ]

    fields = _listing_detail_fields(listing)
    if fields:
        blocks.append({"type": "section", "fields": fields})

    if listing.description:
        blocks.append(
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*説明*\n" + _truncate(_escape_slack_text(listing.description), 2800),
                },
            }
        )

    for image_url in _additional_image_urls(listing):
        blocks.append(
            {
                "type": "image",
                "image_url": image_url,
                "alt_text": listing.title[:200] or "ShareWel item image",
            }
        )

    return {
        "text": f"詳細情報: {listing.title}",
        "blocks": blocks,
        "unfurl_links": True,
        "unfurl_media": True,
    }


def _listing_detail_fields(listing: Listing) -> list[dict[str, str]]:
    raw_fields = [
        ("出品者", listing.owner_name),
        ("掲載期限", listing.expiration),
        ("場所", listing.location),
        ("品目", "\n".join(listing.items)),
    ]
    fields = []
    for label, value in raw_fields:
        if value:
            fields.append(
                {
                    "type": "mrkdwn",
                    "text": f"*{label}*\n{_truncate(_escape_slack_text(value), 1900)}",
                }
            )
    return fields


def _additional_image_urls(listing: Listing) -> tuple[str, ...]:
    if not listing.image_urls:
        return ()
    return tuple(url for url in listing.image_urls if url != listing.image_url)[:5]


def _listing_url(site_url: str, listing_id: str) -> str:
    return f"{site_url.rstrip('/')}/exhibits/{quote(listing_id, safe='')}"


def _slack_quote(text: str) -> str:
    lines = text.splitlines() or [text]
    return "\n".join(f"> {_escape_slack_text(line)}" for line in lines)


def _escape_slack_text(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _truncate(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[: limit - 1] + "…"


def print_current(config: Config) -> None:
    listings = ShareWelClient(config).fetch_listings()
    for listing in listings:
        print(listing.title)


def run_loop(config: Config, *, dry_run: bool = False) -> None:
    LOGGER.info("Starting ShareWel alert loop; interval=%ss state=%s", config.interval_seconds, config.state_file)
    while True:
        try:
            result = check_once(config, dry_run=dry_run)
            _log_result(result, dry_run=dry_run)
        except Exception:
            LOGGER.exception("Check failed")
        time.sleep(config.interval_seconds)


def _log_result(result: CheckResult, *, dry_run: bool) -> None:
    if result.seeded:
        LOGGER.info("Seeded state with %s current listings; no notification sent", result.current_count)
        return

    if result.new_listings:
        action = "would notify" if dry_run else "notified"
        LOGGER.info("%s %s new listing(s)", action, len(result.new_listings))
        for listing in result.new_listings:
            LOGGER.info("new: %s", listing.title)
        return

    LOGGER.info("No new listings; current=%s", result.current_count)


def _listing_from_exhibit(exhibit: Any) -> Listing | None:
    if not isinstance(exhibit, dict):
        return None

    exhibit_id = str(exhibit.get("id") or "").strip()
    title = str(exhibit.get("title") or "").strip()

    if not title:
        items = exhibit.get("items") or []
        if items and isinstance(items, list) and isinstance(items[0], dict):
            title = str(items[0].get("title") or "").strip()

    if not exhibit_id or not title:
        return None

    image_urls = _image_urls_from_exhibit(exhibit)
    return Listing(
        id=exhibit_id,
        title=title,
        image_url=image_urls[0] if image_urls else None,
        image_urls=image_urls,
        description=_clean_text(exhibit.get("description")),
        owner_name=_owner_name_from_exhibit(exhibit),
        location=_location_from_exhibit(exhibit),
        expiration=_expiration_from_exhibit(exhibit),
        items=_items_from_exhibit(exhibit),
    )


def _image_urls_from_exhibit(exhibit: dict[str, Any]) -> tuple[str, ...]:
    items = exhibit.get("items") or []
    if not isinstance(items, list):
        return ()

    image_urls: list[str] = []
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        images = item.get("images") or []
        if not isinstance(images, list):
            continue
        for image in images:
            if not isinstance(image, dict):
                continue
            value = image.get("uri") or image.get("thumbnailUri")
            if isinstance(value, str) and value.strip():
                url = value.strip()
                if url not in seen:
                    image_urls.append(url)
                    seen.add(url)
    return tuple(image_urls)


def _owner_name_from_exhibit(exhibit: dict[str, Any]) -> str:
    owner = exhibit.get("owner")
    if isinstance(owner, dict):
        return _clean_text(owner.get("name"))
    return ""


def _expiration_from_exhibit(exhibit: dict[str, Any]) -> str:
    reuse = exhibit.get("reuse")
    if isinstance(reuse, dict):
        return _clean_text(reuse.get("expiration"))
    return ""


def _location_from_exhibit(exhibit: dict[str, Any]) -> str:
    reuse = exhibit.get("reuse")
    if not isinstance(reuse, dict):
        return ""

    parts: list[str] = []
    building = reuse.get("building")
    if isinstance(building, dict):
        area = building.get("area")
        if isinstance(area, dict):
            parts.append(_clean_text(area.get("nameJa") or area.get("nameEn")))
        parts.append(_clean_text(building.get("nameJa") or building.get("nameEn")))

    place = _clean_text(reuse.get("place"))
    if place:
        parts.append(place)
    return " / ".join(part for part in parts if part)


def _items_from_exhibit(exhibit: dict[str, Any]) -> tuple[str, ...]:
    items = exhibit.get("items") or []
    if not isinstance(items, list):
        return ()

    summaries: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        title = _clean_text(item.get("title"))
        stock = _as_int(item.get("stock"))
        condition = _clean_text(item.get("conditionText") or item.get("condition"))
        parts = [title]
        if stock is not None:
            parts.append(f"在庫: {stock}")
        if condition:
            parts.append(f"状態: {condition}")
        summary = " / ".join(part for part in parts if part)
        if summary:
            summaries.append(summary)
    return tuple(summaries[:10])


def _clean_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


def _bool_param(value: bool) -> str:
    return "true" if value else "false"


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
