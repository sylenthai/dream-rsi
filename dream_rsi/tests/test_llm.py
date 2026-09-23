from dream_rsi.llm.client import extract_json


def test_extract_json_plain():
    assert extract_json('{"name":"x","beta":0.5}')['beta'] == 0.5


def test_extract_json_fenced():
    assert extract_json('```json\n{"ok":true}\n```')['ok'] is True


def test_gemini_client_uses_header_auth(monkeypatch):
    from dream_rsi.llm.providers import GeminiClient
    client = GeminiClient("gemini-1.5-flash", api_key="secret-gemini-key")
    captured = {}

    def mock_post(url, payload, headers, timeout, retries):
        captured["url"] = url
        captured["headers"] = headers
        return {"candidates": [{"content": {"parts": [{"text": "hello"}]}}]}

    monkeypatch.setattr("dream_rsi.llm.providers._post", mock_post)
    resp = client.generate([{"role": "user", "content": "hi"}])
    assert resp.text == "hello"
    assert "key=" not in captured["url"]
    assert captured["headers"].get("x-goog-api-key") == "secret-gemini-key"


