from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, insert, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_async_session
from .models import links
from .schemas import ShortLinkCreate, LinkTopItem
from fastapi_cache import FastAPICache
from fastapi_cache.decorator import cache
import random
from datetime import datetime, timedelta, timezone
from fastapi.responses import RedirectResponse
from auth.users import current_optional_user, current_active_user
from auth.db import User


router = APIRouter(
    prefix="/links",
    tags=["Links"]
)


def generate_short_code(length: int = 7) -> str:
    chars = "abcdefghijklmnopqrstuvwxyz0123456789"
    result = ""

    for _ in range(length):
        result += random.choice(chars)

    return result

# Обязательные функции:
# Создание / удаление / изменение / получение информации по короткой ссылке:
'''POST /links/shorten – создает короткую ссылку.'''

'''Создание кастомных ссылок (уникальный alias):
POST /links/shorten (с передачей custom_alias).
Важно проверить уникальность alias.'''

'''Указание времени жизни ссылки:
POST /links/shorten (создается с параметром expires_at в формате даты с точностью до минуты).
После указанного времени короткая ссылка автоматически удаляется.'''

@router.post("/shorten", status_code=201)
async def create_short_link(new_link: ShortLinkCreate, 
    session: AsyncSession = Depends(get_async_session), 
    user: Optional[User] = Depends(current_optional_user)):
    if user:
        owner_id = user.id
        default_expires = datetime.utcnow() + timedelta(days=30) # Месяц для залогиненных
    else:
        owner_id = None
        default_expires = datetime.utcnow() + timedelta(days=3) # Всего 3 дня для незарегистрированных пользователей
    expires_at = new_link.expires_at if new_link.expires_at is not None else default_expires

    if new_link.custom_alias:
        query = select(links).where(links.c.short_code == new_link.custom_alias)
        result = await session.execute(query)
        existing_link = result.mappings().first()
        if existing_link:
            raise HTTPException(status_code=400, detail="Custom alias already exists")
        short_code = new_link.custom_alias
    else:
        while True: # Или все же encode(id) для перемешанных символов?
            short_code = generate_short_code()

            query = select(links).where(links.c.short_code == short_code)
            result = await session.execute(query)
            existing_link = result.mappings().first()

            if not existing_link:
                break

    statement = insert(links).values(
        original_url=str(new_link.original_url),
        short_code=short_code,
        created_at=datetime.utcnow(),
        last_used_at=None,
        expires_at=expires_at,
        owner_id=owner_id,
        num_of_clicks=0,
    )
    await session.execute(statement)
    await session.commit()
    return {
        "status": "success",
        "short_code": short_code,
        "original_url": str(new_link.original_url),
    }


''' Топ-10 ссылок по числу переходов'''

TOP_CACHE_NAMESPACE = "top_links"

async def clear_top_cache():
    await FastAPICache.clear(namespace=TOP_CACHE_NAMESPACE)

@router.get("/top", response_model=List[LinkTopItem])
@cache(expire=300, namespace=TOP_CACHE_NAMESPACE)
async def get_top_links(session: AsyncSession = Depends(get_async_session)):
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    result = await session.execute(
        select(
            links.c.short_code,
            links.c.original_url,
            links.c.num_of_clicks,
            links.c.last_used_at,
        )
        .where(links.c.last_used_at.is_not(None))
        .where(links.c.last_used_at >= week_ago)
        .order_by(desc(links.c.num_of_clicks))
        .limit(10)
    )

    rows = result.mappings().all()

    top_links = []

    for row in rows:
        top_links.append(
            LinkTopItem(
                short_code=row["short_code"],
                original_url=row["original_url"],
                num_clicks=row["num_of_clicks"],
                last_used_at=row["last_used_at"],
            )
        )

    return top_links

'''DELETE /links/{short_code} – удаляет связь.'''

@router.delete("/{short_code}")
async def delete_short_link(short_code: str, 
    session: AsyncSession = Depends(get_async_session), 
    user: User = Depends(current_active_user)):
    owner_id = user.id
    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()

    if not link:
        raise HTTPException(status_code=404, detail="Short link not found")
    if link["owner_id"] != owner_id:
        raise HTTPException(status_code=403, detail="You are not the owner of this link")
    statement = delete(links).where(links.c.short_code == short_code).where(links.c.owner_id == owner_id)
    await session.execute(statement)
    await session.commit()
    await clear_top_cache()
    return {
        "status": "success",
    }


'''PUT /links/{short_code} – обновляет URL'''

@router.put("/{short_code}")
async def put_short_link(short_code: str,
    session: AsyncSession = Depends(get_async_session),
    user: User = Depends(current_active_user)):

    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    existing_link = result.mappings().first()

    if not existing_link:
        raise HTTPException(status_code=404, detail="Short link not found")
    if existing_link["owner_id"] != user.id:
        raise HTTPException(status_code=403, detail="You are not the owner of this link")
    if existing_link["expires_at"] is not None and existing_link["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Short link has expired")
    while True:
        new_short_code = generate_short_code()

        query = select(links).where(links.c.short_code == new_short_code)
        result = await session.execute(query)
        existing_link = result.mappings().first()

        if not existing_link:
            break

    statement = update(links).where(links.c.short_code == short_code).values(short_code=new_short_code)
    await session.execute(statement)
    await session.commit()
    await clear_top_cache()
    return {
        "status": "success",
        "old_short_code": short_code,
        "new_short_code": new_short_code,
    }


'''Статистика по ссылке:
GET /links/{short_code}/stats
Отображает оригинальный URL, возвращает дату создания, количество переходов, дату последнего использования.'''

@router.get("/{short_code}/stats")
async def get_short_link_stats(short_code: str, session: AsyncSession = Depends(get_async_session)):
    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()
    if not link:
        raise HTTPException(status_code=404, detail="Short link not found")
    if link["expires_at"] is not None and link["expires_at"] < datetime.utcnow():
        raise HTTPException(status_code=410, detail="Short link has expired")

    return {
        "status": "success",
        "original_url": link["original_url"],
        "created_at": link["created_at"],
        "num_of_clicks": link["num_of_clicks"],
        "last_used_at": link["last_used_at"],
    }


'''Поиск ссылки по оригинальному URL:
GET /links/search?original_url={url}'''

@router.get("/search")
async def search_by_original_url(original_url: str, session: AsyncSession = Depends(get_async_session)):
    query = select(links).where(links.c.original_url == original_url)
    result = await session.execute(query)
    found_links = result.mappings().all()
    now = datetime.utcnow()
    # Исключаем истекшие ссылки из результата
    found_links = [row for row in found_links if row["expires_at"] is None or row["expires_at"] >= now]

    return {
        "status": "success",
        "data": found_links,
    }


'''GET /links/{short_code} – перенаправляет на оригинальный URL.'''
# Обновить num_of_clicks и last_used_at
@router.get("/{short_code}")
async def get_original_url(short_code: str, session: AsyncSession = Depends(get_async_session)):
    query = select(links).where(links.c.short_code == short_code)
    result = await session.execute(query)
    link = result.mappings().first()
    if not link:
        raise HTTPException(status_code=404, detail="Short link not found")

    if link["expires_at"] is not None and link["expires_at"] < datetime.utcnow():
        statement = delete(links).where(links.c.short_code == short_code) # Есть еще удаление по расписанию, но как будто при определенных условиях такой подход также не повредит (если, например, автоудаление запускать редко)
        await session.execute(statement) # Раз уж наткнулись на истекшую ссылку, сразу и удалим ее
        await session.commit()
        raise HTTPException(status_code=410, detail="Short link has expired")

    statement = update(links).where(links.c.short_code == short_code).values(num_of_clicks=link["num_of_clicks"] + 1, last_used_at=datetime.utcnow())
    await session.execute(statement)
    await session.commit()
    return RedirectResponse(url=link["original_url"], status_code=307)