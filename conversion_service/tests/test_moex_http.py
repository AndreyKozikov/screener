"""Тесты общего HTTP-клиента MOEX: лимит частоты и ретраи."""

import unittest

import httpx

from conversion_service.app.utils.moex_http import MoexHttpClient, RateLimiter


class RateLimiterTests(unittest.TestCase):
    def test_paces_requests_by_interval(self) -> None:
        now = [0.0]
        sleeps = []

        def clock() -> float:
            return now[0]

        def sleep(delay: float) -> None:
            sleeps.append(delay)
            now[0] += delay

        limiter = RateLimiter(2.0, clock=clock, sleep=sleep)
        limiter.wait()
        limiter.wait()
        limiter.wait()

        self.assertEqual(len(sleeps), 2)
        self.assertAlmostEqual(sleeps[0], 0.5)
        self.assertAlmostEqual(sleeps[1], 0.5)


class MoexHttpClientRetryTests(unittest.TestCase):
    def _make_client(self, handler) -> MoexHttpClient:
        limiter = RateLimiter(1000.0, sleep=lambda _: None)
        return MoexHttpClient(
            transport=httpx.MockTransport(handler),
            rate_limiter=limiter,
            sleep=lambda _: None,
        )

    def test_retries_server_error_then_returns_json(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url)
            if len(calls) < 3:
                return httpx.Response(503)
            return httpx.Response(200, json={"ok": True})

        client = self._make_client(handler)
        try:
            self.assertEqual(client.get_json("https://iss.moex.com/test"), {"ok": True})
        finally:
            client.close()
        self.assertEqual(len(calls), 3)

    def test_retries_connect_timeout(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url)
            if len(calls) == 1:
                raise httpx.ConnectTimeout("timeout", request=request)
            return httpx.Response(200, json={"ok": True})

        client = self._make_client(handler)
        try:
            self.assertEqual(client.get_json("https://iss.moex.com/test"), {"ok": True})
        finally:
            client.close()
        self.assertEqual(len(calls), 2)

    def test_does_not_retry_client_error(self) -> None:
        calls = []

        def handler(request: httpx.Request) -> httpx.Response:
            calls.append(request.url)
            return httpx.Response(404, json={"detail": "not found"})

        client = self._make_client(handler)
        try:
            with self.assertRaises(RuntimeError):
                client.get_json("https://iss.moex.com/missing")
        finally:
            client.close()
        self.assertEqual(len(calls), 1)


if __name__ == "__main__":
    unittest.main()
