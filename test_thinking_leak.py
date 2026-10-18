"""Regression tests: thinking text must never reach user-visible output.

Thinking stays enabled (accuracy mechanism). These tests pin the OUTPUT
HANDLING contract using mocked Ollama responses (deterministic, no LLM):

 1. thinking-only non-stream response -> honest message, never thinking text
 2. thinking + final response -> only final response returned
 3. stream: thinking-only chunks skipped, response chunks in order
 4. empty final response (no thinking either) -> honest message
 5. missing fields / malformed lines fail safely (no thinking leaked)
 6. transport errors propagate without thinking content
 7. stream + non-stream paths both exclude thinking
 8. citations and physics derivations in RESPONSE text pass through intact

The marker THINKMARKER-7Q2X appears ONLY in mock `thinking` fields; any
appearance in output is a leak.

Run: python test_thinking_leak.py
"""
import json
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import answer

THINK = "THINKMARKER-7Q2X internal chain-of-thought that must stay hidden"


class FakeResponse:
    def __init__(self, payload_lines=None, body=None):
        self._lines = payload_lines or []
        self._body = body or {}
        self.captured = {}

    def raise_for_status(self):
        pass

    def json(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def iter_lines(self, decode_unicode=True):
        return iter(self._lines)


class ExplodingResponse(FakeResponse):
    def raise_for_status(self):
        raise RuntimeError("boom-transport")


class Capture:
    def __init__(self, fake):
        self.fake = fake
        self.calls = []

    def __call__(self, url, json=None, **kwargs):
        self.calls.append({"url": url, "json": json})
        return self.fake


def stream_lines(*chunks):
    return [json.dumps(c) for c in chunks]


class TestThinkingLeak(unittest.TestCase):
    def setUp(self):
        self._real_post = answer.requests.post

    def tearDown(self):
        answer.requests.post = self._real_post

    def test_thinking_only_never_becomes_answer(self):
        cap = Capture(FakeResponse(body={"response": "", "thinking": THINK}))
        answer.requests.post = cap
        text, _ = answer.generate_answer("q", "ctx", is_numerical=True)
        self.assertNotIn("THINKMARKER-7Q2X", text)
        self.assertTrue(text.strip(), "must return an honest message, not ''")

    def test_thinking_plus_response_returns_only_response(self):
        body = {"response": "Final: K = 2 J.", "thinking": THINK}
        cap = Capture(FakeResponse(body=body))
        answer.requests.post = cap
        text, _ = answer.generate_answer("q", "ctx", is_numerical=True)
        self.assertIn("Final: K = 2 J.", text)
        self.assertNotIn("THINKMARKER-7Q2X", text)

    def test_stream_skips_thinking_chunks_preserves_order(self):
        lines = stream_lines(
            {"thinking": THINK, "done": False},
            {"response": "Kf ", "thinking": THINK, "done": False},
            {"response": "- Ki = ", "done": False},
            {"response": "W.", "done": False},
            {"thinking": THINK, "response": "", "done": True},
        )
        cap = Capture(FakeResponse(payload_lines=lines))
        answer.requests.post = cap
        text = "".join(answer.generate_answer_stream("q", "ctx", is_numerical=True))
        self.assertEqual(text, "Kf - Ki = W.")
        self.assertNotIn("THINKMARKER-7Q2X", text)

    def test_stream_thinking_only_yields_nothing_usable(self):
        lines = stream_lines({"thinking": THINK, "done": False},
                             {"thinking": THINK, "done": True})
        cap = Capture(FakeResponse(payload_lines=lines))
        answer.requests.post = cap
        text = "".join(answer.generate_answer_stream("q", "ctx"))
        self.assertNotIn("THINKMARKER-7Q2X", text)
        self.assertEqual(text, "")

    def test_empty_everything_fails_safe(self):
        cap = Capture(FakeResponse(body={"response": "", "thinking": ""}))
        answer.requests.post = cap
        text, _ = answer.generate_answer("q", "ctx")
        self.assertTrue(text.strip())
        self.assertNotIn("THINKMARKER-7Q2X", text)

    def test_missing_fields_fails_safe(self):
        cap = Capture(FakeResponse(body={}))
        answer.requests.post = cap
        text, _ = answer.generate_answer("q", "ctx")
        self.assertTrue(text.strip())

    def test_malformed_stream_lines_skipped(self):
        lines = ["{not json", "", json.dumps({"response": "ok ", "done": False}),
                 json.dumps({"response": "done.", "done": True})]
        cap = Capture(FakeResponse(payload_lines=lines))
        answer.requests.post = cap
        text = "".join(answer.generate_answer_stream("q", "ctx"))
        self.assertEqual(text, "ok done.")

    def test_transport_error_carries_no_thinking(self):
        answer.requests.post = lambda *a, **k: ExplodingResponse()
        with self.assertRaises(RuntimeError) as cm:
            answer.generate_answer("q", "ctx")
        self.assertNotIn("THINKMARKER-7Q2X", str(cm.exception))
        with self.assertRaises(RuntimeError):
            list(answer.generate_answer_stream("q", "ctx"))

    def test_physics_derivations_and_citations_intact(self):
        deriv = ("From $K_f - K_i = \\int F(x)dx$ with $f=\\mu mg$ and "
                 "[Section 5.6], $W = 882\\,\\mathrm{J}$.")
        cap = Capture(FakeResponse(
            body={"response": deriv, "thinking": THINK}))
        answer.requests.post = cap
        text, _ = answer.generate_answer("q", "ctx", is_numerical=True)
        self.assertIn("\\int F(x)dx", text)
        self.assertIn("882", text)
        self.assertIn("[Section 5.6]", text)
        self.assertNotIn("THINKMARKER-7Q2X", text)
        chunks = [{"metadata": {"chapter": "CHAPTER FIVE", "section": "5.6 sculpt",
                                "page": 4, "file": "keph105.pdf"},
                   "text": deriv}]
        cites = answer.format_citations(chunks)
        self.assertTrue(any("5.6" in c and "keph105.pdf" in c for c in cites))


if __name__ == "__main__":
    unittest.main(verbosity=2)
