# Chat API

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

Real-time chat and instant messaging API with JWT authentication (access + refresh tokens), WebSocket messaging, role-based access control, typing indicators, read receipts, full-text search, chat moderation (mute, kick, ban), and per-user rate limiting. Built with **FastAPI**, **PostgreSQL**, **SQLAlchemy 2.0**, and **Redis** adhering to clean layered architecture.

---

## Features

- **JWT Authentication**: Secure user registration, credential login with bcrypt password hashing, short-lived access tokens, and long-lived refresh tokens.
- **Role-Based Access Control (RBAC)**: Hierarchical privilege system (`admin` > `moderator` > `user`) securing global administration and domain operations.
- **Private & Group Chats**: Support for 1-on-1 direct conversations and multi-user group chat rooms with custom titles and descriptions.
- **Full-Duplex WebSockets**: Real-time message streaming, connection pooling, and multi-client broadcasting.
- **Typing Indicators & Read Receipts**: Live feedback on participant typing activity and delivery/read timestamps per message.
- **Message Search**: Message search across all accessible chats, filtering out soft-deleted content.
- **Message Lifecycle & Soft Delete**: In-place message editing with timestamp history and audit-safe soft deletion masking.
- **Attachment Metadata**: Standardized attachment schema for file URLs, MIME types, and byte sizes.
- **Online Presence Tracking**: Real-time user connectivity tracking and last-seen timestamp updates.
- **Chat Moderation Suite**: Chat-level owner, admin, and member roles with capabilities to mute (timed), kick, or permanently ban malicious users.
- **Sliding-Window Rate Limiting**: Per-user / per-IP rate limiting middleware protecting against abuse.
- **Database Migrations**: Version-controlled asynchronous database migrations with **Alembic**.

---

## Tech Stack

| Component | Technology | Description |
|---|---|---|
| **API Framework** | FastAPI 0.110+ | High-performance asynchronous REST & WebSocket framework |
| **Database** | PostgreSQL 16 | Relational storage for users, chats, participants, messages, and receipts |
| **ORM** | SQLAlchemy 2.0 (Async) | Fully typed asynchronous ORM mapping with `asyncpg` |
| **Cache & Broker** | Redis 7 | High-speed cache and rate limit transport |
| **Authentication** | PyJWT & bcrypt | Cryptographic token issuing, validation, and salted password hashing |
| **Migrations** | Alembic | Asynchronous schema migrations |
| **Validation & Settings** | Pydantic v2 & Pydantic-Settings | Typed schemas, request validation, and environment configuration |
| **Code Quality** | Ruff & Mypy (strict mode) | Linting, formatting, and strict static type checking |
| **Testing** | pytest & pytest-asyncio | Over 80 unit and integration tests with **84% code coverage** |
| **Containerization** | Docker & Docker Compose | Multi-stage Docker image and full stack orchestration |

---

## Architecture & Project Structure

The project strictly follows layered clean architecture. `main.py` is reserved exclusively for application lifecycle and middleware setup without business logic. All business rules are encapsulated in `services/`, security functions live in `security/`, and route definitions in `api/`.

```
chat-api/
├── src/chat_api/
│   ├── __init__.py
│   ├── main.py            # App initialization, CORS, middleware, lifespan
│   ├── config.py          # Settings via pydantic-settings
│   ├── exceptions.py      # Custom domain exception hierarchy
│   ├── api/               # HTTP & WebSocket endpoints
│   │   ├── __init__.py
│   │   ├── router.py      # Root API router assembly
│   │   ├── auth.py        # /register, /login, /refresh, /me
│   │   ├── users.py       # User directory & status
│   │   ├── chats.py       # Rooms, participants, moderation
│   │   ├── messages.py    # Messages CRUD, receipts, search
│   │   └── websocket.py   # WebSocket /ws/{chat_id} endpoint
│   ├── models/            # SQLAlchemy 2.0 ORM models
│   │   ├── __init__.py
│   │   ├── user.py        # User entity
│   │   ├── chat.py        # Chat & ChatParticipant entities
│   │   └── message.py     # Message & MessageReceipt entities
│   ├── schemas/           # Pydantic v2 validation models
│   │   ├── __init__.py
│   │   ├── auth.py        # Auth credentials & token schemas
│   │   ├── user.py        # User profile schemas
│   │   ├── chat.py        # Chat & moderation schemas
│   │   └── message.py     # Message, receipts, & websocket schemas
│   ├── services/          # Business logic layer
│   │   ├── __init__.py
│   │   ├── auth.py        # Auth & token services
│   │   ├── user.py        # User management services
│   │   ├── chat.py        # Room & moderation logic
│   │   └── message.py     # Message persistence, search, WS manager
│   ├── security/          # Security & authorization
│   │   ├── __init__.py
│   │   ├── jwt.py         # Token creation & decoding
│   │   ├── hashing.py     # Bcrypt password hashing
│   │   └── permissions.py # Role-based access control
│   ├── middleware/        # HTTP Middleware
│   │   ├── __init__.py
│   │   └── rate_limit.py  # Sliding-window rate limiter
│   └── db/                # Database engine & session
│       ├── __init__.py
│       └── session.py     # Async session factory & get_db dependency
├── tests/                 # Automated test suite (80+ tests)
│   ├── __init__.py
│   ├── conftest.py        # Async SQLite fixtures & TestClient setup
│   ├── test_api/          # API endpoint integration tests
│   ├── test_services/     # Service unit tests
│   ├── test_security/     # JWT & hashing unit tests
│   └── test_middleware/   # Rate limiting tests
├── alembic/               # Async database migrations
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
├── docker-compose.yml     # Multi-container stack (App + PostgreSQL + Redis)
├── Dockerfile             # Multi-stage production container build
├── Makefile               # Development task commands
├── pyproject.toml         # Dependencies and tool configurations
├── .env.example           # Documented environment variables
├── README.md              # English documentation
└── README_RU.md           # Russian documentation
```

---

## WebSocket Protocol

Clients connect to the real-time endpoint by providing an access token query parameter:

```
ws://localhost:8000/api/v1/ws/{chat_id}?token={access_token}
```

### Supported Client Frames (Send)

#### 1. Ping / Keepalive
```json
{
  "type": "ping"
}
```

#### 2. Typing Indicator
```json
{
  "type": "typing",
  "is_typing": true
}
```

#### 3. Send Message
```json
{
  "type": "message",
  "content": "Hello everyone!",
  "attachments": [
    {
      "filename": "diagram.png",
      "file_size": 10240,
      "content_type": "image/png",
      "file_url": "https://storage.example.com/diagram.png"
    }
  ]
}
```

#### 4. Read Receipt Acknowledgment
```json
{
  "type": "read",
  "message_id": 42
}
```

### Server Broadcast Frames (Receive)

| Frame Type | Trigger | Payload Summary |
|---|---|---|
| `pong` | In response to client `ping` | `{"type": "pong"}` |
| `presence` | Client connects or disconnects | `{"type": "presence", "data": {"user_id": 1, "username": "alice", "is_online": true}}` |
| `typing` | Participant begins/stops typing | `{"type": "typing", "data": {"chat_id": 1, "user_id": 1, "username": "alice", "is_typing": true}}` |
| `new_message` | New message sent to room | `{"type": "new_message", "data": {"id": 10, "content": "Hello", ...}}` |
| `message_edited` | Message edited | `{"type": "message_edited", "data": {"id": 10, "content": "Edited", ...}}` |
| `message_deleted`| Message soft-deleted | `{"type": "message_deleted", "data": {"id": 10, "content": "[Message deleted]", ...}}` |
| `read_receipt` | Participant marked message read | `{"type": "read_receipt", "data": {"message_id": 10, "user_id": 2, "read_at": "..."}}` |

---

## REST API Reference

### Authentication (`/api/v1/auth`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/auth/register` | Register new user account | No |
| `POST` | `/api/v1/auth/login` | Authenticate and obtain JWT token pair | No |
| `POST` | `/api/v1/auth/refresh` | Refresh access token using refresh token | No |
| `GET` | `/api/v1/auth/me` | Fetch currently authenticated user profile | Bearer Token |

### Users (`/api/v1/users`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/v1/users` | List users with pagination and search | Bearer Token |
| `GET` | `/api/v1/users/{id}` | Get user profile details | Bearer Token |
| `PATCH`| `/api/v1/users/{id}` | Update profile (self or admin role reassignment) | Bearer Token |
| `PUT` | `/api/v1/users/me/status` | Update online presence status | Bearer Token |

### Chats (`/api/v1/chats`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/chats` | Create direct (1-on-1) or group chat | Bearer Token |
| `GET` | `/api/v1/chats` | List caller's active chats | Bearer Token |
| `GET` | `/api/v1/chats/{id}` | Get chat room details and roster | Bearer Token |
| `PATCH`| `/api/v1/chats/{id}` | Update chat name or description (owner/admin) | Bearer Token |
| `POST` | `/api/v1/chats/{id}/participants` | Add member to group chat | Bearer Token |
| `DELETE`| `/api/v1/chats/{id}/participants/{id}` | Leave chat or kick participant | Bearer Token |

### Chat Moderation (`/api/v1/chats/{id}/moderation`)

| Method | Endpoint | Description | Min Role |
|---|---|---|---|
| `POST` | `/api/v1/chats/{id}/moderation/mute` | Mute participant for N minutes | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/unmute/{uid}` | Lift mute restriction | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/kick` | Kick participant from chat | Chat Admin / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/ban` | Ban user permanently from room | Chat Owner / Mod |
| `POST` | `/api/v1/chats/{id}/moderation/unban/{uid}` | Remove ban from user | Chat Owner / Mod |

### Messages (`/api/v1/messages` & `/api/v1/chats/{id}/messages`)

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `POST` | `/api/v1/chats/{id}/messages` | Send message with attachments | Bearer Token |
| `GET` | `/api/v1/chats/{id}/messages` | Paginated message history | Bearer Token |
| `PATCH`| `/api/v1/messages/{id}` | Edit message content (author only) | Bearer Token |
| `DELETE`| `/api/v1/messages/{id}` | Soft delete message (author/mod/admin) | Bearer Token |
| `GET` | `/api/v1/messages/search` | Full-text message search | Bearer Token |
| `POST` | `/api/v1/messages/{id}/read` | Mark message as read | Bearer Token |

---

## Getting Started

### Prerequisites

- **Python 3.11+**
- **Docker & Docker Compose** (for containerized setup)
- **PostgreSQL 16+** & **Redis 7+** (for manual local execution)

### Quick Start with Docker Compose

1. Clone the repository:
   ```bash
   git clone https://github.com/CHUKEPC/chat-api.git
   cd chat-api
   ```

2. Configure environment:
   ```bash
   cp .env.example .env
   ```

3. Launch all services (FastAPI app, PostgreSQL, Redis):
   ```bash
   docker compose up -d
   ```

4. The API and Swagger documentation will be available at:
   - **Interactive API Docs (Swagger)**: [http://localhost:8000/docs](http://localhost:8000/docs)
   - **Alternative Docs (ReDoc)**: [http://localhost:8000/redoc](http://localhost:8000/redoc)
   - **Health Check**: [http://localhost:8000/health](http://localhost:8000/health)

### Local Development Setup

1. Create a virtual environment and install dependencies:
   ```bash
   make install
   ```

2. Start dependencies using Docker:
   ```bash
   docker compose up -d db redis
   ```

3. Apply database migrations:
   ```bash
   .venv/bin/alembic upgrade head
   ```

4. Run the development server with live reload:
   ```bash
   make run
   ```

---

## Testing & Quality Assurance

Run the complete verification suite using `make`:

```bash
# Run linting (Ruff)
make lint

# Run strict type checking (Mypy)
make type-check

# Run test suite with code coverage report
make test

# Run all checks at once
make all
```

---

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.
