import json
import unittest
from datetime import date
from unittest.mock import MagicMock, patch

from today_in_history import build_template_card, fetch_events, select_events


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

    def test_selects_four_random_events(self) -> None:
        events = [{"e_id": str(index)} for index in range(10)]

        with patch("today_in_history.random.sample", return_value=events[2:6]) as sample:
            selected = select_events(events)

        self.assertEqual(selected, events[2:6])
        sample.assert_called_once_with(events, 4)

    def test_builds_template_card_with_four_events(self) -> None:
        events = [
            {"date": f"{1900 + index}年8月31日", "title": f"历史事件 {index}"}
            for index in range(4)
        ]

        message = build_template_card(events, date(2026, 8, 31))

        self.assertEqual(message["msgtype"], "template_card")
        card = message["template_card"]
        self.assertEqual(card["card_type"], "news_notice")
        self.assertEqual(card["card_image"]["aspect_ratio"], 1.8)
        self.assertEqual(len(card["vertical_content_list"]), 4)
        self.assertEqual(card["vertical_content_list"][0]["desc"], "历史事件 0")


if __name__ == "__main__":
    unittest.main()