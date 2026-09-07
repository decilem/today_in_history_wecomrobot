import json
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from today_in_history import build_template_card, fetch_bing_wallpaper, fetch_events, select_events


class TodayInHistoryTests(unittest.TestCase):
    @patch("today_in_history.urlopen")
    def test_fetch_events_uses_month_and_day(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {
                "reason": "success",
                "result": [{"date": "1997年7月1日", "title": "测试事件", "e_id": "1"}],
                "error_code": 0,
            }
        ).encode("utf-8")
        mock_urlopen.return_value = response

        events = fetch_events("secret", date(2026, 7, 1))

        self.assertEqual(events[0]["title"], "测试事件")
        request = mock_urlopen.call_args.args[0]
        self.assertIn("date=7%2F1", request.full_url)
        self.assertNotIn("2026", request.full_url)

    @patch("today_in_history.random.sample")
    def test_selects_five_events_by_period_and_sorts_them(self, sample: MagicMock) -> None:
        events = [
            {"date": "前200年", "e_id": "ancient-1"},
            {"date": "300年", "e_id": "ancient-2"},
            {"date": "800年", "e_id": "feudal-1"},
            {"date": "1200年", "e_id": "feudal-2"},
            {"date": "2020年", "e_id": "modern-1"},
        ]
        sample.side_effect = lambda values, count: list(values)[:count]

        selected = select_events(events)

        self.assertEqual([event["e_id"] for event in selected], ["ancient-1", "ancient-2", "feudal-1", "feudal-2", "modern-1"])

    def test_short_period_is_filled_by_next_period(self) -> None:
        events = [
            {"date": "300年", "e_id": "ancient"},
            {"date": "800年", "e_id": "feudal-1"},
            {"date": "1200年", "e_id": "feudal-2"},
            {"date": "1500年", "e_id": "feudal-3"},
            {"date": "2020年", "e_id": "modern"},
        ]

        selected = select_events(events)

        self.assertEqual(len(selected), 5)
        self.assertEqual([event["e_id"] for event in selected], ["ancient", "feudal-1", "feudal-2", "feudal-3", "modern"])

    @patch("today_in_history.urlopen")
    def test_fetch_bing_wallpaper_uses_1920x1080(self, mock_urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value = response
        response.read.return_value = json.dumps(
            {"images": [{"urlbase": "/th?id=OHR.Test"}]}
        ).encode("utf-8")
        mock_urlopen.return_value = response

        self.assertEqual(
            fetch_bing_wallpaper(),
            "https://cn.bing.com/th?id=OHR.Test_1920x1080.jpg",
        )

    def test_builds_template_card_with_four_events(self) -> None:
        events = [
            {"date": f"{1900 + index}年8月31日", "title": f"历史事件 {index}"}
            for index in range(4)
        ]

        wallpaper_url = "https://cn.bing.com/th?id=OHR.Test_1920x1080.jpg"
        message = build_template_card(events, date(2026, 8, 31), wallpaper_url)

        self.assertEqual(message["msgtype"], "template_card")
        card = message["template_card"]
        self.assertEqual(card["card_type"], "news_notice")
        self.assertEqual(card["card_image"]["url"], wallpaper_url)
        self.assertEqual(card["card_image"]["aspect_ratio"], 1.8)
        self.assertEqual(len(card["vertical_content_list"]), 4)
        self.assertEqual(card["vertical_content_list"][0]["desc"], "历史事件 0")


if __name__ == "__main__":
    unittest.main()