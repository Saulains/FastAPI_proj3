import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

os.environ.setdefault("USE_REDIS_CACHE", "false")

import fastapi_cache.decorator as _cache_decorator


def _no_cache_decorator(*_args, **_kwargs):
    def _wrap(func):
        return func

    return _wrap


_cache_decorator.cache = _no_cache_decorator

import main as app_main
from links import router as links_router


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def db_session():
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.add = AsyncMock()
    session.delete = AsyncMock()
    return session


# Неавторизованный пользователь
@pytest.fixture
def unauthorized_client(db_session):
    async def override_get_async_session():
        yield db_session

    async def override_current_optional_user():
        return None

    app_main.aioredis.from_url = lambda *_a, **_kw: object()
    app_main.FastAPICache.init = lambda *_a, **_kw: None
    links_router.clear_top_cache = AsyncMock()

    app_main.app.dependency_overrides[links_router.get_async_session] = override_get_async_session
    app_main.app.dependency_overrides[links_router.current_optional_user] = override_current_optional_user

    with TestClient(app_main.app) as client:
        yield client

    app_main.app.dependency_overrides.clear()


# Авторизованный
@pytest.fixture
def auth_client(db_session, user_id):
    async def override_get_async_session():
        yield db_session

    async def override_current_optional_user():
        return SimpleNamespace(id=user_id)

    async def override_current_active_user():
        return SimpleNamespace(id=user_id)

    app_main.aioredis.from_url = lambda *_a, **_kw: object()
    app_main.FastAPICache.init = lambda *_a, **_kw: None
    links_router.clear_top_cache = AsyncMock()

    app_main.app.dependency_overrides[links_router.get_async_session] = override_get_async_session
    app_main.app.dependency_overrides[links_router.current_optional_user] = override_current_optional_user
    app_main.app.dependency_overrides[links_router.current_active_user] = override_current_active_user

    with TestClient(app_main.app) as client:
        yield client

    app_main.app.dependency_overrides.clear()