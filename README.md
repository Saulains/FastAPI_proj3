# Сервис для сокращения длинных ссылок

Сервис для создания коротких ссылок с поддержкой авторизации, кастомных алиасов и автоматическим удалением истекших и неиспользуемых ссылок.

---

## Описание API

### Авторизация
- `POST /auth/register` — регистрация
- `POST /auth/jwt/login` — вход
- `POST /auth/jwt/logout` — выход

### Ссылки
- `POST /links/shorten` — создать короткую ссылку
- `GET /links/top` — топ-10 ссылок по числу переходов
- `GET /links/{short_code}/stats` — статистика по ссылке
- `GET /links/search?original_url=...` — поиск по оригинальной ссылке
- `PUT /links/{short_code}` — обновить короткую ссылку (Только для владельца ссылки)
- `DELETE /links/{short_code}` — удалить ссылку (Только для владельца ссылки)
- `GET /{short_code}` — перейти по короткой ссылке

-> Для гостей срок жизни ссылки по умолчанию — 3 дня, для авторизованных — 30 дней

-> Истекшие ссылки удаляются по расписанию (Celery Beat), неиспользуемые (без переходов дольше N дней) — раз в сутки

---

## Примеры запросов

### Создание короткой ссылки

```bash
# Без авторизации (гость)
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{"original_url": "https://example.com/page"}'

# С кастомным алиасом и сроком жизни
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -d '{
    "original_url": "https://example.com/page",
    "custom_alias": "mylink",
    "expires_at": "2025-12-31T23:59:00"
  }'

# С авторизацией
curl -X POST "http://localhost:8000/links/shorten" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -d '{"original_url": "https://example.com/page"}'
```

Пример ответа (201):

```json
{
  "status": "success",
  "short_code": "abc12xy",
  "original_url": "https://example.com/page"
}
```

### Топ-10 ссылок

```bash
curl "http://localhost:8000/links/top"
```

Ответ: `short_code`, `original_url`, `num_clicks`, `last_used_at`

### Переход по короткой ссылке

```bash
curl -L "http://localhost:8000/abc12xy"
```

Происходит редирект на исходный URL, увеличивается счетчик переходов и обновляется last_used_at

### Статистика по ссылке

```bash
curl "http://localhost:8000/links/abc12xy/stats"
```

Пример ответа:

```json
{
  "status": "success",
  "original_url": "https://example.com/page",
  "created_at": "2025-03-14T12:00:00",
  "num_of_clicks": 1,
  "last_used_at": "2025-03-14T14:30:00"
}
```

### Поиск по оригинальному URL

```bash
curl "http://localhost:8000/links/search?original_url=https://example.com/page"
```

### Удаление и обновление

```bash
# Удалить ссылку
curl -X DELETE "http://localhost:8000/links/abc12xy" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"

# Обновить короткую ссылку (новая определяется случайным образом)
curl -X PUT "http://localhost:8000/links/abc12xy" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Ответ PUT: 
```json
{
  "status": "success",
  "old_short_code": "abc12xy",
  "new_short_code": "xyz98ab"
}
```

---

## Запуск

### Через Docker

1. В корне проекта создайте файл `.env`.

2. Запустите сервисы:
```bash
docker compose up -d
```

3. Примените миграции:

```bash
DB_HOST=localhost DB_PORT=5433 python -m alembic upgrade head
```

4. Доступ:
   - API: http://localhost:8000  
   - Swagger: http://localhost:8000/docs  
   - Flower: http://localhost:8888  

### Локально

1. Установите и запустите PostgreSQL и Redis.

2. Создайте виртуальное окружение и установите зависимости:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

3. Создайте `.env`

4. Примените миграции:

```bash
PYTHONPATH=.:src python -m alembic upgrade head
```

5. Запустите приложение:

```bash
PYTHONPATH=.:src uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

После этого API будет доступен по адресу http://localhost:8000

---

## Описание БД

Используется PostgreSQL, миграции лежат в `migrations/`.

В таблице `user` хранятся пользователи: id, email, пароль и поля статуса пользователя

В таблице `links` хранятся сами короткие ссылки:
- `id` — id ссылки
- `original_url` — исходная длинная ссылка
- `short_code` — короткий код (Не ссылка, тк хранится без домена)
- `created_at` — когда ссылка создана
- `last_used_at` — когда по ней последний раз переходили
- `expires_at` — срок жизни ссылки
- `owner_id` — id владельца, если ссылка создана авторизованным пользователем
- `num_of_clicks` — число переходов

Фоновые задачи (Celery) удаляют записи с истекшим `expires_at` и записи, у которых `last_used_at` старше заданного числа дней (`UNUSED_LINKS_DAYS`, по умолчанию 10).
