import os
import sys
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC_ROOT = os.path.join(PROJECT_ROOT, "src")

if SRC_ROOT not in sys.path:
    sys.path.insert(0, SRC_ROOT)

from links.router import create_short_link, generate_short_code
from links.schemas import ShortLinkCreate

# По умолчанию длина ссылки = 7
def test_generate_short_code_default_length():
    code = generate_short_code()
    assert len(code) == 7


def test_generate_short_code_custom_length(): #n Но можно задать и  иную длину
    code = generate_short_code(10)
    assert len(code) == 10


@pytest.mark.asyncio
async def test_create_short_link_success():
    session = AsyncMock()
    result_mock = Mock()
    result_mock.mappings.return_value.first.return_value = None

    session.execute = AsyncMock(side_effect=[result_mock, result_mock])
    session.commit = AsyncMock()

    link_data = ShortLinkCreate(original_url="https://example.com")

    with patch("links.router.generate_short_code", return_value="abc1234"):
        result = await create_short_link(link_data, session=session, user=None)

    assert result["short_code"] == "abc1234"
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_short_link_custom_alias_conflict():  # Уже существует такой alias
    session = AsyncMock()
    result_mock = Mock()
    result_mock.mappings.return_value.first.return_value = {"id": 1}

    session.execute = AsyncMock(return_value=result_mock)
    session.commit = AsyncMock()

    link_data = ShortLinkCreate(
        original_url="https://example.com",
        custom_alias="taken-alias",
    )

    with pytest.raises(HTTPException):
        await create_short_link(link_data, session=session, user=None)

    session.commit.assert_not_awaited()


@pytest.mark.asyncio
# Так как в данных момент короткая ссылка подбирается через рандом, то проверка, что
# такая ссылка еще не существует (иначе - повторная генерация)
async def test_create_short_link_retry_if_code_exists():
    session = AsyncMock()

    busy_code = Mock()
    busy_code.mappings.return_value.first.return_value = {"id": 1}

    free_code = Mock()
    free_code.mappings.return_value.first.return_value = None

    session.execute = AsyncMock(side_effect=[busy_code, free_code, free_code])
    session.commit = AsyncMock()

    link_data = ShortLinkCreate(original_url="https://example.com")

    with patch(
        "links.router.generate_short_code",
        side_effect=["dup1111", "ok22222"],
    ):
        result = await create_short_link(link_data, session=session, user=None)

    assert result["short_code"] == "ok22222"
    session.commit.assert_awaited_once()