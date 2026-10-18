"""Config regression tests for Qwen adoption (no LLM/network needed).

Seams under test (public behavior, not internals):
  1. generate_answer / generate_answer_stream request construction
     (model, budgets, ctx, no think override) — via monkeypatched requests.
  2. benchmark grader model pinning (stays llama3.1:8b after default switch).
  3. request-level failures (timeout/HTTP error) map to the honest
     empty-state instead of crashing (realworld campaign Oct 17 2026).

Run: python test_answer_config.py
"""
import json
import sys
import unittest

sys.stdout.reconfigure(encoding="utf-8")

import answer
import benchmark


class FakeResponse:
    def __init__(self, payload_lines=None, body=None):
        self._lines = payload_lines or []
        self._body = body or {"response": "CORRECT"}
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


class Capture:
    """Monkeypatch for requests.post recording (url, json)."""

    def __init__(self, fake):
        self.fake = fake
        self.calls = []

    def __call__(self, url, json=None, **kwargs):
        self.calls.append({"url": url, "json": json})
        return self.fake


class TestGenerationConfig(unittest.TestCase):
    def setUp(self):
        self._real_post = answer.requests.post
        self._real_bench_post = benchmark.requests.post

    def tearDown(self):
        answer.requests.post = self._real_post
        benchmark.requests.post = self._real_bench_post

    def test_default_model_is_qwen3_8b(self):
        self.assertEqual(answer.OLLAMA_MODEL, "qwen3:8b")

    def test_fallback_model_retained(self):
        self.assertEqual(answer.FALLBACK_MODEL, "llama3.1:8b")
        self.assertNotEqual(answer.FALLBACK_MODEL, answer.OLLAMA_MODEL)

    def test_numerical_budget_4096(self):
        cap = Capture(FakeResponse(body={"response": "ok"}))
        answer.requests.post = cap
        answer.generate_answer("q", "ctx", is_numerical=True)
        payload = cap.calls[0]["json"]
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertEqual(payload["options"]["num_predict"], 4096)
        self.assertEqual(payload["options"]["num_ctx"], 4096)

    def test_theory_budget_4096(self):
        # Theory ceiling is 4096 (raised from 2048 Oct 2026: on the frozen su1
        # context qwen3's thinking consumed the whole 2048 allowance on 7 of 8
        # trials, each done_reason=length at 2048/2048 -> empty answers).
        # Measured 8 trials/arm: 2048 -> 1/8 correct, 4096 -> 5/8 correct.
        cap = Capture(FakeResponse(body={"response": "ok"}))
        answer.requests.post = cap
        answer.generate_answer("q", "ctx", is_numerical=False)
        payload = cap.calls[0]["json"]
        self.assertEqual(payload["model"], "qwen3:8b")
        self.assertEqual(payload["options"]["num_predict"], 4096)
        self.assertEqual(payload["options"]["num_ctx"], 4096)

    def test_budgets_stay_within_request_timeout(self):
        """A budget-exhausting run must still finish inside the HTTP timeout,
        otherwise the honest-empty path would never be reached."""
        self.assertLessEqual(answer.NUM_PREDICT_THEORY, 4096)
        self.assertLessEqual(answer.NUM_PREDICT_NUMERICAL, 4096)

    def test_no_think_override_sent(self):
        """Thinking stays on Ollama's verified default (on for qwen3);
        we must not send think:false (kills the accuracy gain) nor
        think:true (assumes uniform semantics across models)."""
        for isn in (False, True):
            cap = Capture(FakeResponse(body={"response": "ok"}))
            answer.requests.post = cap
            answer.generate_answer("q", "ctx", is_numerical=isn)
            self.assertNotIn("think", cap.calls[0]["json"])

    def test_stream_path_same_budgets(self):
        lines = [json.dumps({"response": "tok ", "done": False}),
                 json.dumps({"response": "ok", "done": True})]
        for isn, expected in ((False, 4096), (True, 4096)):
            cap = Capture(FakeResponse(payload_lines=list(lines)))
            answer.requests.post = cap
            text = "".join(answer.generate_answer_stream(
                "q", "ctx", is_numerical=isn))
            self.assertEqual(text, "tok ok")
            payload = cap.calls[0]["json"]
            self.assertTrue(payload["stream"])
            self.assertEqual(payload["options"]["num_predict"], expected)
            self.assertNotIn("think", payload)

    def test_grader_pinned_to_llama(self):
        cap = Capture(FakeResponse(body={"response": "CORRECT"}))
        benchmark.requests.post = cap
        self.assertTrue(benchmark.grade_answer_llm("q", "a", "gt"))
        self.assertEqual(cap.calls[0]["json"]["model"], "llama3.1:8b")


class TestRequestFailuresMapToHonestEmpty(unittest.TestCase):
    """Regression (measured Oct 17 2026, realworld campaign): an
    RTX-throttled session made generation exceed the 300s client timeout;
    the uncaught ReadTimeout crashed the whole eval run and would surface
    as a raw Streamlit exception in the app. Request-level failures must
    map to the honest empty-state so retry / fallback stays possible."""

    def setUp(self):
        self._real_post = answer.requests.post

    def tearDown(self):
        answer.requests.post = self._real_post

    def test_timeout_maps_to_honest_empty(self):
        def boom(url, json=None, **kwargs):
            raise answer.requests.Timeout("simulated 300s client timeout")

        answer.requests.post = boom
        text, latency = answer.generate_answer("q", "ctx")
        self.assertEqual(text, answer.EMPTY_ANSWER_MESSAGE)
        self.assertGreaterEqual(latency, 0.0)

    def test_server_error_maps_to_honest_empty(self):
        class ErrResp:
            def raise_for_status(self):
                raise answer.requests.HTTPError("simulated watchdog 500")

        answer.requests.post = lambda url, json=None, **kw: ErrResp()
        text, _ = answer.generate_answer("q", "ctx")
        self.assertEqual(text, answer.EMPTY_ANSWER_MESSAGE)

    def test_stream_timeout_before_tokens_yields_honest_empty(self):
        def boom(url, json=None, **kwargs):
            raise answer.requests.Timeout("simulated stream timeout")

        answer.requests.post = boom
        out = list(answer.generate_answer_stream("q", "ctx"))
        self.assertEqual(out, [answer.EMPTY_ANSWER_MESSAGE])

    def test_stream_midway_failure_still_raises(self):
        """After real tokens were delivered, a request exception must not
        masquerade as an empty answer; the caller sees the real error."""
        import json as _json

        lines = [_json.dumps({"response": "partial ", "done": False})]

        class HalfStream:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def raise_for_status(self):
                pass

            def iter_lines(self, decode_unicode=True):
                for l in lines:
                    yield l
                raise answer.requests.ConnectionError("lost mid-stream")

        answer.requests.post = lambda url, json=None, **kw: HalfStream()
        with self.assertRaises(answer.requests.ConnectionError):
            list(answer.generate_answer_stream("q", "ctx"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
