# Chat API (Сервис обмена сообщениями в реальном времени)

[![CI](https://github.com/CHUKEPC/chat-api/actions/workflows/ci.yml/badge.svg)](https://github.com/CHUKEPC/chat-api/actions/workflows/ci.yml)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat&logo=FastAPI&logoColor=white)](https://fastapi.tiangolo.com)
[![WebSocket](https://img.shields.io/badge/WebSocket-Real--Time-orange.svg)](https://websockets.readthedocs.io/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16+-4169E1.svg?style=flat&logo=PostgreSQL&logoColor=white)](https://www.postgresql.org/)
[![SQLAlchemy 2.0](https://img.shields.io/badge/SQLAlchemy-2.0+-red.svg)](https://www.sqlalchemy.org/)
[![JWT](https://img.shields.io/badge/JWT-PyJWT-black.svg?logo=JSON%20web%20tokens)](https://jwt.io/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)
[![Checked with mypy](https://www.mypy-lang.org/static/mypy_badge.svg)](https://mypy-lang.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Полнофункциональный API для обмена сообщениями в реальном времени с JWT-аутентификацией (access + refresh токены), протоколом WebSocket, ролевым управлением доступом (RBAC), индикаторами набора текста (typing indicators), статусами прочтения (read receipts), поиском сообщений, модерацией комнат (mute, kick, ban) и rate limiting per user. Разработан на **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0** и **Redis** в соответствии с принципами чистой слоистой архитектуры.

---

## Возможности

- **JWT-аутентификация**: Регистрация пользователей, вход по логину/email с хешированием паролей bcrypt, короткоживущие access-токены и долгоживущие refresh-токены.
- **Ролевая модель доступа (RBAC)**: Иерархия системных ролей (`admin` > `moderator` > `user`) для защиты эндпоинтов и администрирования.
- **Приватные и групповые чаты**: Поддержка личной переписки 1-на-1 и групповых чатов с названиями и описаниями.
- **Полнодуплексный WebSocket**: Потоковая передача сообщений в реальном времени, управление пулом соединений и рассылка событий участникам.
- **Индикаторы набора и статусы прочтения**: Уведомления о том, что собеседник пишет сообщение, и фиксация времени прочтения каждого сообщения.
- **Полнотекстовый поиск**: Быстрый поиск сообщений по ключевым словам по всем доступным пользователю чатам с фильтрацией удаленных сообщений.
- **Редактирование и Soft Delete**: Редактирование сообщений с фиксацией времени изменения и безопасное мягкое удаление (soft delete) без разрушения истории.
- **Вложения файлов (Metadata)**: Структурированные метаданные файлов (URL, MIME-тип, размер в байтах).
- **Статус присутствия (Онлайн / Оффлайн)**: Отслеживание активности подключений пользователей и времени последнего посещения (`last_seen_at`).
- **Модерация чатов**: Роли на уровне чата (владелец, администратор, участник) с возможностью временного заглушения (`mute`), исключения (`kick`) или постоянной блокировки (`ban`).
- **Ограничение частоты запросов (Rate Limiting)**: Middleware скользящего окна (sliding window) для защиты API от перегрузок по пользователям и IP.
- **Миграции базы данных**: Асинхронные миграции схемы БД через **Alembic**.

---

## Стек технологий

| Компонент | Технология | Назначение |
|---|---|---|
| **API Framework** | FastAPI 0.110+ | Асинхронный веб-фреймворк REST и WebSocket |
| **База данных** | PostgreSQL 16 | Реляционная БД для хранения пользователей, чатов, сообщений и статусов |
| **ORM** | SQLAlchemy 2.0 (Async) | Строго типизированный асинхронный ORM через `asyncpg` |
| **Кеш и брокер** | Redis 7 | Быстрый кеш и хранилище счетчиков rate limit |
| **Аутентификация** | PyJWT и bcrypt | Выпуск и валидация JWT-токенов, хеширование паролей |
| **Миграции** | Alembic | Версионирование и накат схемы базы данных |
| **Валидация и настройки** | Pydantic v2 и Pydantic-Settings | Строгая типизация запросов/ответов, валидация конфигурации |
| **Контроль качества** | Ruff и Mypy (strict mode) | Линтер, форматтер и строгий статический анализ типов |
| **Тестирование** | pytest и pytest-asyncio | Более 80 модульных и интеграционных тестов с **покрытием 84%** |
| **Контейнеризация** | Docker и Docker Compose | Multi-stage сборка образа и запуск всех сервисов в контейнерах |

---

## Архитектура и структура проекта

Проект строго следует принципам чистой слоистой архитектуры:
- `main.py` предназначен исключительно для инициализации приложения и подключения middleware — никакой бизнес-логики.
- Вся бизнес-логика вынесена в `services/`.
- Механизмы безопасности, хэширование и RBAC находятся в `security/`.
- Роуты и обработчики HTTP/WebSocket находятся в `api/`.

```
chat-api/
├── src/chat_api/
│   ├── __init__.py
│   ├── main.py            # Точка входа, CORS, middleware, lifespan
│   ├── config.py          # Настройки через pydantic-settings
│   ├── exceptions.py      # Иерархия доменных исключений
│   ├── api/               # HTTP и WebSocket эндпоинты
│   │   ├── __init__.py
│   │   ├── router.py      # Сборка роутеров
│   │   ├── auth.py        # /register, /login, /refresh, /me
│   │   ├── users.py       # Каталог пользователей и статусы
│   │   ├── chats.py       # Комнаты, участники, модерация
│   │   ├── messages.py    # CRUD сообщений, статусы прочтения, поиск
│   │   └── websocket.py   # Эндпоинт WebSocket /ws/{chat_id}
│   ├── models/            # SQLAlchemy 2.0 ORM модели
│   │   ├── __init__.py
│   │   ├── user.py        # Модель User
│   │   ├── chat.py        # Модели Chat и ChatParticipant
│   │   └── message.py     # Модели Message и MessageReceipt
│   ├── schemas/           # Pydantic v2 схемы
│   │   ├── __init__.py
│   │   ├── auth.py        # Схемы авторизации и токенов
│   │   ├── user.py        # Схемы профилей
│   │   ├── chat.py        # Схемы чатов и модерации
│   │   └── message.py     # Схемы сообщений и WebSocket
│   ├── services/          # Слой бизнес-логики
│   │   ├── __init__.py
│   │   ├── auth.py        # Логика регистрации и аутентификации
│   │   ├── user.py        # Логика пользователей
│   │   ├── chat.py        # Логика чатов и модерации
│   │   └── message.py     # Сообщения, поиск, менеджер WebSocket
│   ├── security/          # Безопасность и авторизация
│   │   ├── __init__.py
│   │   ├── jwt.py         # Создание и декодирование JWT
│   │   ├── hashing.py     # Хеширование bcrypt
│   │   └── permissions.py # Ролевой доступ (RBAC)
│   ├── middleware/        # HTTP Middleware
│   │   ├── __init__.py
│   │   └── rate_limit.py  # Rate limiter скользящего окна
│   └── db/                # База данных
│       ├── __init__.py
│       └── session.py     # Фабрика сессий и зависимость get_db
├── tests/                 # Тесты (80+ тестов, coverage 84%)
│   ├── __init__.py
│   ├── conftest.py        # Фикстуры SQLite и TestClient
│   ├── test_api/          # Интеграционные тесты API
│   ├── test_services/     # Юнит-тесты сервисов
│   ├── test_security/     # Тесты JWT и bcrypt
│   └── test_middleware/   # Тесты rate limit
├── alembic/               # Миграции базы данных
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── docker-compose.yml     # Стек сервисов (App + PostgreSQL + Redis)
├── Dockerfile             # Multi-stage образ
├── Makefile               # Команды сборки и проверки
├── pyproject.toml         # Зависимости и конфигурация инструментов
├── .env.example           # Пример переменных окружения
├── README.md              # Документация на английском
└── README_RU.md           # Документация на русском
```

---

## Протокол WebSocket

Клиент подключается к эндпоинту, передавая access-токен в query-параметре:

```
ws://localhost:8000/api/v1/ws/{chat_id}?token={access_token}
```

### Фреймы от клиента к серверу (Send)

#### 1. Проверка связи (Ping)
```json
{
  "type": "ping"
}
```

#### 2. Индикатор набора текста
```json
{
  "type": "typing",
  "is_typing": true
}
```

#### 3. Отправка сообщения
```json
{
  "type": "message",
  "content": "Привет всем!",
  "attachments": [
    {
      "filename": "document.pdf",
      "file_size": 10240,
      "content_type": "application/pdf",
      "file_url": "https://storage.example.com/document.pdf"
    }
  ]
}
```

#### 4. Подтверждение прочтения
```json
{
  "type": "read",
  "message_id": 42
}
```

### Фреймы от сервера к клиентам (Receive)

| Тип фрейма | Причина отправки | Пример содержимого |
|---|---|---|
| `pong` | Ответ на `ping` клиента | `{"type": "pong"}` |
| `presence` | Подключение или отключение пользователя | `{"type": "presence", "data": {"user_id": 1, "username": "alice", "is_online": true}}` |
| `typing` | Участник начал/перестал печатать | `{"type": "typing", "data": {"chat_id": 1, "user_id": 1, "username": "alice", "is_typing": true}}` |
| `new_message` | Новое сообщение в чате | `{"type": "new_message", "data": {"id": 10, "content": "Привет", ...}}` |
| `message_edited` | Сообщение отредактировано | `{"type": "message_edited", "data": {"id": 10, "content": "Отредактировано", ...}}` |
| `message_deleted`| Сообщение удалено (soft delete) | `{"type": "message_deleted", "data": {"id": 10, "content": "[Message deleted]", ...}}` |
| `read_receipt` | Сообщение прочитано участником | `{"type": "read_receipt", "data": {"message_id": 10, "user_id": 2, "read_at": "..."}}` |

---

## Справочник REST API

### Аутентификация (`/api/v1/auth`)

| Метод | Эндпоинт | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Регистрация нового аккаунта | Не требуется |
| `POST` | `/api/v1/auth/login` | Вход и получение пары токенов (access + refresh) | Не требуется |
| `POST` | `/api/v1/auth/refresh` | Обновление токена доступа по refresh-токену | Не требуется |
| `GET` | `/api/v1/auth/me` | Получение профиля текущего пользователя | Bearer Token |

### Пользователи (`/api/v1/users`)

| Метод | Эндпоинт | Описание | Авторизация |
|---|---|---|---|
| `GET` | `/api/v1/users` | Каталог пользователей с пагинацией и поиском | Bearer Token |
| `GET` | `/api/v1/users/{id}` | Детальная информация о пользователе | Bearer Token |
| `PATCH`| `/api/v1/users/{id}` | Обновление профиля или смена роли (админ) | Bearer Token |
| `PUT` | `/api/v1/users/me/status` | Обновление статуса присутствия (онлайн/оффлайн) | Bearer Token |

### Чаты (`/api/v1/chats`)

| Метод | Эндпоинт | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/api/v1/chats` | Создание личного (1-на-1) или группового чата | Bearer Token |
| `GET` | `/api/v1/chats` | Список активных чатов пользователя | Bearer Token |
| `GET` | `/api/v1/chats/{id}` | Детальная информация о комнате и участниках | Bearer Token |
| `PATCH`| `/api/v1/chats/{id}` | Изменение названия или описания чата | Bearer Token |
| `POST` | `/api/v1/chats/{id}/participants` | Добавление участника в групповой чат | Bearer Token |
| `DELETE`| `/api/v1/chats/{id}/participants/{id}` | Выход из чата или удаление участника | Bearer Token |

### Модерация комнат (`/api/v1/chats/{id}/moderation`)

| Метод | Эндпоинт | Описание | Мин. Роль |
|---|---|---|---|
| `POST` | `/api/v1/chats/{id}/moderation/mute` | Заглушить пользователя на N минут | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/unmute/{uid}` | Снять заглушение с пользователя | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/kick` | Выгнать участника из чата | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/ban` | Навсегда заблокировать пользователя | Chat Owner / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/unban/{uid}` | Разблокировать пользователя | Chat Owner / Mod |

### Сообщения (`/api/v1/messages` и `/api/v1/chats/{id}/messages`)

| Метод | Эндпоинт | Описание | Авторизация |
|---|---|---|---|
| `POST` | `/api/v1/chats/{id}/messages` | Отправка сообщения с вложениями | Bearer Token |
| `GET` | `/api/v1/chats/{id}/messages` | История сообщений с пагинацией | Bearer Token |
| `PATCH`| `/api/v1/messages/{id}` | Редактирование текста (только автор) | Bearer Token |
| `DELETE`| `/api/v1/messages/{id}` | Мягкое удаление сообщения (автор/модератор) | Bearer Token |
| `GET` | `/api/v1/messages/search` | Поиск сообщений по тексту | Bearer Token |
| `POST` | `/api/v1/messages/{id}/read` | Отметка сообщения как прочитанного | Bearer Token |

---

## Запуск и развертывание

### Требования

- **Python 3.11+**
- **Docker и Docker Compose**
- **PostgreSQL 16+** и **Redis 7+** (при локальном запуске без Docker)

### Быстрый старт через Docker Compose

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/CHUKEPC/chat-api.git
   cd chat-api
   ```

2. Настройте файл окружения:
   ```bash
   cp .env.example .env
   ```

3. Запустите сервисы (FastAPI, PostgreSQL, Redis):
   ```bash
   docker compose up -d
   ```

4. Документация API будет доступна по адресам:
   - **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **ReDoc**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - **Health check**: [http://localhost:8000/health](http://localhost:8000/health)

### Локальная разработка

1. Создайте виртуальное окружение и установите зависимости:
   ```bash
   make install
   ```

2. Запустите базу данных и Redis в Docker:
   ```bash
   docker compose up -d db redis
   ```

3. Примените миграции базы данных:
   ```bash
   .venv/bin/alembic upgrade head
   ```

4. Запустите сервер разработки с автоперезагрузкой:
   ```bash
   make run
   ```

---

## Тестирование и контроль качества

Все проверки запускаются через единый `Makefile`:

```bash
# Проверка стиля и форматирования (Ruff)
make lint

# Строгая проверка типов (Mypy)
make type-check

# Запуск тестов с отчетом о покрытии (Coverage 84%)
make test

# Запуск всех проверок
make all
```

---

## Лицензия

Проект распространяется под лицензией MIT — подробности в файле [LICENSE](LICENSE).
