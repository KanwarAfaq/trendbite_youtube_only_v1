from datetime import datetime, timezone
from unittest.mock import patch

import youtube_discovery as yd


def test_live_query_rotation():
    fixed = datetime(2026, 9, 24, 8, 0, tzinfo=timezone.utc)
    q1 = yd.build_live_queries(1, now=fixed)
    q2 = yd.build_live_queries(2, now=fixed)
    assert len(q1) == 6
    assert len(q2) == 6
    assert q1 != q2
    joined = " ".join(q1 + q2).lower()
    for concept in ("cat", "dog", "baby", "monkey"):
        assert concept in joined


def test_three_api_key_round_robin():
    class Resp:
        ok = True
        status_code = 200
        text = ""
        def json(self):
            return {"items": []}

    fake_settings = type("S", (), {"youtube_api_keys": ("k1", "k2", "k3")})()
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["key"])
        return Resp()

    yd._key_cursor = 0
    with patch.object(yd, "settings", fake_settings), patch.object(yd.requests, "get", side_effect=fake_get):
        yd._api_get("https://example.test", {})
        yd._api_get("https://example.test", {})
        yd._api_get("https://example.test", {})
    assert calls == ["k1", "k2", "k3"]


def test_key_failover():
    class BadResp:
        ok = False
        status_code = 403
        text = ""
        def json(self):
            return {"error": {"errors": [{"reason": "quotaExceeded"}]}}

    class GoodResp:
        ok = True
        status_code = 200
        text = ""
        def json(self):
            return {"items": [{"ok": True}]}

    fake_settings = type("S", (), {"youtube_api_keys": ("k1", "k2", "k3")})()
    calls = []

    def fake_get(url, params, timeout):
        calls.append(params["key"])
        return BadResp() if params["key"] == "k1" else GoodResp()

    yd._key_cursor = 0
    with patch.object(yd, "settings", fake_settings), patch.object(yd.requests, "get", side_effect=fake_get):
        result = yd._api_get("https://example.test", {})
    assert result["items"][0]["ok"] is True
    assert calls == ["k1", "k2"]


if __name__ == "__main__":
    test_live_query_rotation()
    test_three_api_key_round_robin()
    test_key_failover()
    print("ALL LOCAL LIVE-DISCOVERY TESTS PASSED")
