from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

import yaml

try:
    import truststore
except ImportError:
    truststore = None
else:
    truststore.inject_into_ssl()


EVENTS_API_URL = "https://v.juhe.cn/todayOnhistory/queryEvent"
BING_WALLPAPER_API_URL = "https://cn.bing.com/HPImageArchive.aspx?format=js&idx=0&n=1&mkt=zh-CN"
SHANGHAI_TIMEZONE = ZoneInfo("Asia/Shanghai")
EVENT_COUNT = 5


class HistoryPushError(RuntimeError):
    pass


def load_config(config_path: Path) -> dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as config_file:
        config = yaml.safe_load(config_file) or {}
    if not isinstance(config, dict):
        raise HistoryPushError(f"配置文件格式无效: {config_path}")
    return config


def get_setting(
    env_name: str,
    config: dict[str, Any],
    section: str,
    key: str,
) -> str | None:
    env_value = os.getenv(env_name)
    if env_value:
        return env_value

    section_value = config.get(section, {})
    if isinstance(section_value, dict):
        value = section_value.get(key)
        if value is not None:
            return str(value).strip()
    return None


def request_json(request: Request, *, timeout: int = 15) -> dict[str, Any]:
    try:
        with urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as error:
        raise HistoryPushError(f"HTTP 请求失败: {error.code} {error.reason}") from error
    except URLError as error:
        raise HistoryPushError(f"网络请求失败: {error.reason}") from error
    except (json.JSONDecodeError, UnicodeDecodeError) as error:
        raise HistoryPushError("接口返回了无效的 JSON") from error

    if not isinstance(payload, dict):
        raise HistoryPushError("接口返回格式无效")
    return payload


def fetch_events(api_key: str, target_date: date) -> list[dict[str, Any]]:
    query = urlencode({"key": api_key, "date": f"{target_date.month}/{target_date.day}"})
    request = Request(f"{EVENTS_API_URL}?{query}", headers={"User-Agent": "today-in-history/1.0"})
    payload = request_json(request)

    if payload.get("error_code") != 0:
        reason = payload.get("reason", "未知错误")
        raise HistoryPushError(f"历史事件接口失败: {reason} (error_code={payload.get('error_code')})")

    events = payload.get("result")
    if not isinstance(events, list):
        raise HistoryPushError("历史事件接口未返回事件列表")
    return [event for event in events if isinstance(event, dict)]


def event_year(event: dict[str, Any]) -> int | None:
    value = str(event.get("date", ""))
    match = re.search(r"(前\s*)?(\d+)年", value)
    if not match:
        return None
    year = int(match.group(2))
    return -year if match.group(1) else year


def events_in_period(
    events: list[dict[str, Any]], minimum: int | None, maximum: int | None
) -> list[dict[str, Any]]:
    period_events = []
    for event in events:
        year = event_year(event)
        if year is not None and (minimum is None or year >= minimum) and (
            maximum is None or year < maximum
        ):
            period_events.append(event)
    return period_events


def select_events(events: list[dict[str, Any]], count: int = EVENT_COUNT) -> list[dict[str, Any]]:
    # 公元475年之前：原始社会以及奴隶社会；475年至1840年：封建社会；1840年之后：近现代。
    target_count = min(count, len(events))
    periods = (
        events_in_period(events, None, 475),
        events_in_period(events, 475, 1840),
        events_in_period(events, 1840, None),
    )
    quotas = [2, 2, 1]
    selected: list[dict[str, Any]] = []
    remaining = [list(period) for period in periods]

    for index, quota in enumerate(quotas):
        quota = min(quota, target_count - len(selected))
        picked = random.sample(remaining[index], min(quota, len(remaining[index]))) if quota else []
        selected.extend(picked)
        for event in picked:
            remaining[index].remove(event)
        shortage = quota - len(picked)
        next_index = index + 1
        while shortage and next_index < len(remaining):
            extra = random.sample(remaining[next_index], min(shortage, len(remaining[next_index])))
            selected.extend(extra)
            for event in extra:
                remaining[next_index].remove(event)
            shortage -= len(extra)
            next_index += 1

    if len(selected) < target_count:
        classified = {id(event) for period in periods for event in period}
        leftovers = [event for event in events if id(event) not in classified and event not in selected]
        leftovers.extend(event for period in remaining for event in period)
        fill_count = min(len(leftovers), target_count - len(selected))
        if fill_count:
            selected.extend(random.sample(leftovers, fill_count))

    return sorted(selected, key=lambda event: (event_year(event) is None, event_year(event) or 0))


def fetch_bing_wallpaper() -> str:
    request = Request(BING_WALLPAPER_API_URL, headers={"User-Agent": "today-in-history/1.0"})
    payload = request_json(request)
    images = payload.get("images")
    if not isinstance(images, list) or not images or not isinstance(images[0], dict):
        raise HistoryPushError("必应壁纸接口未返回图片")

    url_base = images[0].get("urlbase")
    if not isinstance(url_base, str) or not url_base:
        raise HistoryPushError("必应壁纸接口未返回图片地址")
    return f"https://cn.bing.com{url_base}_1920x1080.jpg"


def truncate(value: Any, limit: int) -> str:
    text = " ".join(str(value).split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 1]}…"


def build_template_card(
    events: list[dict[str, Any]],
    target_date: date,
    wallpaper_url: str,
) -> dict[str, Any]:
    vertical_content_list = []
    for event in events:
        vertical_content_list.append(
            {
                "title": truncate(event.get("date") or "日期不详", 38),
                "desc": truncate(event.get("title") or "未命名事件", 64),
            }
        )

    return {
        "msgtype": "template_card",
        "template_card": {
            "card_type": "news_notice",
            "source": {
                "icon_url": "http://picturebucket4md.oss-cn-shenzhen.aliyuncs.com/ossbrs/White-OE-Square%20Background.png",
                "desc": "Excellent Everyday",
                "desc_color": 0,
            },
            "main_title": {
                "title": f"历史上的今天",
                "desc": f"{target_date.month}月{target_date.day}日历史事件",
            },
            "card_image": {
                "url": wallpaper_url,
                "aspect_ratio": 1.8,
            },
            "vertical_content_list": vertical_content_list,
            "card_action": {
                "type": 1,
                "url": "https://baike.baidu.com/calendar/",
            },
        },
    }


def send_to_wecom(webhook_url: str, message: dict[str, Any]) -> None:
    body = json.dumps(message, ensure_ascii=False).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    payload = request_json(request)
    if payload.get("errcode") != 0:
        raise HistoryPushError(
            f"企业微信推送失败: {payload.get('errmsg', '未知错误')} "
            f"(errcode={payload.get('errcode')})"
        )


def parse_date(value: str | None) -> date:
    if value is None:
        return datetime.now(SHANGHAI_TIMEZONE).date()
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise HistoryPushError("--date 必须使用 YYYY-MM-DD 格式") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="获取历史上的今天并推送到企业微信机器人")
    parser.add_argument("--date", help="指定日期，格式为 YYYY-MM-DD；默认使用上海时区的今天")
    parser.add_argument("--dry-run", action="store_true", help="只输出消息，不推送到企业微信")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path(__file__).with_name("credentials.yaml"),
        help="本地凭据文件路径",
    )
    parser.add_argument(
        "--webhook-name",
        default=os.getenv("WECOM_WEBHOOK_NAME", "testkey"),
        help="credentials.yaml 中的 webhook 名称，默认 testkey",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        config = load_config(args.config)
        api_key = get_setting("TODAY_IN_HISTORY_API_KEY", config, "apisite", "key")
        if not api_key:
            raise HistoryPushError("缺少 TODAY_IN_HISTORY_API_KEY 或 credentials.yaml 中的 apisite.key")

        target_date = parse_date(args.date)
        events = fetch_events(api_key, target_date)
        selected_events = select_events(events)
        wallpaper_url = fetch_bing_wallpaper()
        message = build_template_card(selected_events, target_date, wallpaper_url)

        if args.dry_run:
            print(json.dumps(message, ensure_ascii=False, indent=2))
            return 0

        webhook_url = get_setting(
            "WECOM_WEBHOOK_URL",
            config,
            "WECOM_webhook",
            args.webhook_name,
        )
        if not webhook_url:
            raise HistoryPushError(
                f"缺少 WECOM_WEBHOOK_URL 或 credentials.yaml 中的 WECOM_webhook.{args.webhook_name}"
            )
        send_to_wecom(webhook_url, message)
        print(f"已推送 {len(selected_events)} 条 {target_date.month}月{target_date.day}日的历史事件。")
        return 0
    except HistoryPushError as error:
        print(f"错误: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())