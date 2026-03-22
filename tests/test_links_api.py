from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest


def make_result(first_value=None, all_value=None): # Имитируем результат запроса к бд
    result = Mock()
    result.mappings.return_value = result
    result.first.return_value = first_value
    result.all.return_value = all_value or []
    return result


def test_create_short_link_success(unauthorized_client, db_session):
    db_session.execute.side_effect = [
        make_result(None),
        make_result(None),
    ]

    response = unauthorized_client.post(
        "/links/shorten",
        json={"original_url": "https://example.com"},
    )
    assert response.status_code == 201
    assert response.json()["status"] == "success"


def test_create_short_link_invalid_payload_returns_422(unauthorized_client): # Невалидный url
    response = unauthorized_client.post(
        "/links/shorten",
        json={"original_url": "not_a_url"},
    )
    assert response.status_code == 422


def test_create_short_link_custom_alias_conflict(unauthorized_client, db_session): # Уже существует такой alias
    db_session.execute.return_value = make_result({"id": 1})

    response = unauthorized_client.post(
        "/links/shorten",
        json={
            "original_url": "https://example.com",
            "custom_alias": "taken",
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Custom alias already exists"


def test_get_top_links_success(unauthorized_client, db_session): # Топ ссылок
    now = datetime.utcnow()
    db_session.execute.return_value = make_result(
        all_value=[
            {
                "short_code": "asdfg11",
                "original_url": "https://example.com/1",
                "num_of_clicks": 10,
                "last_used_at": now,
            },
            {
                "short_code": "zxcvb22",
                "original_url": "https://example.com/2",
                "num_of_clicks": 9,
                "last_used_at": now - timedelta(minutes=5),
            },
        ]
    )

    response = unauthorized_client.get("/links/top")

    assert response.status_code == 200
    assert len(response.json()) == 2


def test_delete_short_link_not_found(auth_client, db_session): # Удаление несуществующей ссылки (мб уже удаленной)
    db_session.execute.return_value = make_result(None)
    response = auth_client.delete("/links/qwertyu")
    assert response.status_code == 404


def test_delete_short_link_success(auth_client, db_session, user_id): # Удаление ссылки, которая существует и принадлежит удаляющему
    db_session.execute.side_effect = [
        make_result({"owner_id": user_id}),
        make_result(None),
    ]

    response = auth_client.delete("/links/abc1234")
    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_put_short_link_expired(auth_client, db_session, user_id): # Если ссылка уже просрочена и просто ее не успели удалить, обновить ее нельзя
    db_session.execute.return_value = make_result(
        {
            "owner_id": user_id,
            "expires_at": datetime.utcnow() - timedelta(minutes=1),
        }
    )

    response = auth_client.put("/links/abc1234")
    assert response.status_code == 410


def test_put_short_link_success(auth_client, db_session, user_id):
    db_session.execute.side_effect = [
        make_result(
            {
                "owner_id": user_id,
                "expires_at": datetime.utcnow() + timedelta(days=1),
            }
        ),
        make_result(None),
        make_result(None),
    ]

    with patch("links.router.generate_short_code", return_value="newcode1"):
        response = auth_client.put("/links/abc1234")
    assert response.status_code == 200
    assert response.json()["new_short_code"] == "newcode1"


def test_get_stats_not_found(unauthorized_client, db_session): # Статистика несуществующей ссылки (мб уже удаленной)
    db_session.execute.return_value = make_result(None)
    response = unauthorized_client.get("/links/abc1234/stats")
    assert response.status_code == 404


def test_get_stats_success(unauthorized_client, db_session): # Успешная статистика
    db_session.execute.return_value = make_result(
        {
            "short_code": "abc1234",
            "original_url": "https://example.com",
            "created_at": datetime.utcnow() - timedelta(days=1),
            "last_used_at": datetime.utcnow() - timedelta(hours=1),
            "expires_at": datetime.utcnow() + timedelta(days=2),
            "owner_id": None,
            "num_of_clicks": 5,
        }
    )

    response = unauthorized_client.get("/links/abc1234/stats")
    assert response.status_code == 200
    assert response.json()["original_url"] == "https://example.com"



def test_redirect_not_found(unauthorized_client, db_session): # Переход по неизвестной короткой ссылке (Мб удаленная)
    db_session.execute.return_value = make_result(None)
    response = unauthorized_client.get("/links/unknown", follow_redirects=False)
    assert response.status_code == 404


def test_redirect_expired_410(unauthorized_client, db_session): # Переход по просроченной ссылке
    db_session.execute.side_effect = [
        make_result(
            {
                "short_code": "old1234",
                "original_url": "https://example.com",
                "created_at": datetime.utcnow() - timedelta(days=10),
                "last_used_at": datetime.utcnow() - timedelta(days=9),
                "expires_at": datetime.utcnow() - timedelta(minutes=1),
                "owner_id": None,
                "num_of_clicks": 3,
            }
        ),
        make_result(None),
    ]

    response = unauthorized_client.get("/links/old1234", follow_redirects=False)
    assert response.status_code == 410


def test_redirect_success(unauthorized_client, db_session):
    db_session.execute.side_effect = [
        make_result(
            {
                "short_code": "ex12345",
                "original_url": "https://example.com",
                "created_at": datetime.utcnow() - timedelta(days=1),
                "last_used_at": datetime.utcnow() - timedelta(hours=1),
                "expires_at": datetime.utcnow() + timedelta(days=2),
                "owner_id": None,
                "num_of_clicks": 5,
            }
        ),
        make_result(None),
    ]

    response = unauthorized_client.get("/links/ex12345", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "https://example.com"