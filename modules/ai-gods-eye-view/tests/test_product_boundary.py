"""Exercise the bridge against verified sessions rather than supplied headers."""
import importlib.util
from pathlib import Path
import sys

import httpx
import pytest
from fastapi.testclient import TestClient
from starlette.responses import JSONResponse


@pytest.fixture
def bridge(monkeypatch):
    path = Path(__file__).parents[1] / 'server.py'
    spec = importlib.util.spec_from_file_location('product_viewer_bridge', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    monkeypatch.setenv('GODS_EYE_VIEW_ADMIN_URL', 'http://api:8000')
    monkeypatch.setattr(module.native_proxy, 'enabled', lambda: True)

    async def proxy(request, path):
        return JSONResponse({'user': module.principal(request), 'role': await module.viewer_role(request)})

    monkeypatch.setattr(module.native_proxy, 'proxy', proxy)
    return module


def session_response(monkeypatch, bridge, *, status=200, headers=None, unavailable=False):
    calls = []

    class SessionClient:
        def __init__(self, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            pass

        async def get(self, url, **kwargs):
            calls.append((url, kwargs))
            if unavailable:
                raise httpx.ConnectError('unavailable')
            return httpx.Response(status, headers=headers or {})

    monkeypatch.setattr(bridge.httpx, 'AsyncClient', SessionClient)
    return calls


def test_forged_admin_headers_are_replaced_with_verified_reader(monkeypatch, bridge):
    calls = session_response(monkeypatch, bridge, headers={'X-Gods-Eye-View-User': 'viewer:verified', 'X-Gods-Eye-View-Role': 'reader'})
    result = TestClient(bridge.app).get('/api/weather', headers={
        'Cookie': 'session=signed', 'X-Gods-Eye-View-User': 'forged', 'X-Gods-Eye-View-Role': 'admin'})
    assert result.status_code == 200
    assert result.json() == {'user': 'viewer:verified', 'role': 'reader'}
    assert calls == [('http://api:8000/api/gods-eye-view/session', {'headers': {'Cookie': 'session=signed'}})]


@pytest.mark.parametrize('status', [401, 403, 503, 302])
def test_denied_or_redirected_sessions_never_reach_provider(monkeypatch, bridge, status):
    session_response(monkeypatch, bridge, status=status)
    response = TestClient(bridge.app).get('/api/weather', headers={'X-Gods-Eye-View-Role': 'admin'})
    assert response.status_code == (status if status in {401, 403, 503} else 503)


def test_session_outage_fails_closed(monkeypatch, bridge):
    session_response(monkeypatch, bridge, unavailable=True)
    assert TestClient(bridge.app).get('/api/weather').status_code == 503


def test_incomplete_successful_session_is_rejected(monkeypatch, bridge):
    session_response(monkeypatch, bridge, headers={'X-Gods-Eye-View-Role': 'admin'})
    assert TestClient(bridge.app).get('/api/weather').status_code == 503
