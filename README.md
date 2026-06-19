# CP-Hub Project Structure

CP-Hub is a Discord bot project for competitive programming practice.
It provides features such as problem recommendation, account linking, user profiles, stage progression, achievements, and AI-assisted chat responses.

This document gives a high-level overview of the project structure for new developers.

---

## Project Overview

```text
CP-Hub
├── bot/
│   ├── main.py
│   └── cogs/
│
├── backend/
│   └── app/
│       ├── core/
│       ├── models/
│       ├── crud/
│       └── services/
│
├── alembic/
├── tests/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
└── pyproject.toml
```

---

## Main Architecture

The project is divided into four main layers:

```text
bot/cogs
= Discord command layer

backend/app/services
= Business logic layer

backend/app/crud
= Database access layer

backend/app/models
= Database model layer
```

---

## `bot/`

The `bot` directory contains the Discord bot entry point and all Discord-related commands.

```text
bot/
├── main.py
└── cogs/
```

### `bot/main.py`

This is the main entry point of the Discord bot.

It is responsible for:

* creating the Discord bot instance
* loading all cogs from `bot/cogs`
* syncing slash commands
* starting the bot

In most cases, new Discord commands should be added as new files under `bot/cogs`.

---

## `bot/cogs/`

This directory contains Discord command modules.

Each file usually represents one feature area.

```text
bot/cogs/
├── account.py
├── leetcode.py
├── mention_chat.py
├── profile.py
└── stage.py
```

### Current Cogs

| File              | Purpose                                                                         |
| ----------------- | ------------------------------------------------------------------------------- |
| `account.py`      | Handles account linking for platforms such as LeetCode, Codeforces, and AtCoder |
| `leetcode.py`     | Handles LeetCode problem drawing commands                                       |
| `profile.py`      | Displays user profile, stats, EXP, coins, and linked accounts                   |
| `stage.py`        | Handles the stage system, problem progression, verification, and achievements   |
| `mention_chat.py` | Handles AI chat responses when the bot is mentioned                             |

The cog layer should mainly handle Discord interactions, such as:

* slash command parameters
* embeds
* buttons
* interaction responses
* user-facing messages

Complex logic should usually be placed in `backend/app/services`.

---

## `backend/app/`

The `backend/app` directory contains the core backend logic.

```text
backend/app/
├── core/
├── models/
├── crud/
└── services/
```

---

## `backend/app/core/`

This directory contains shared core configuration.

Typical responsibilities include:

* environment variable loading
* application settings
* database session setup

Common files:

```text
backend/app/core/config.py
backend/app/core/db.py
```

---

## `backend/app/models/`

This directory contains SQLAlchemy database models.

Use this directory when adding or modifying database tables.

Examples of things that belong here:

* user model
* user stats model
* stage model
* progress model
* achievement model

If a feature requires persistent data, it will usually need a model here.

---

## `backend/app/crud/`

This directory contains database access functions.

CRUD files should handle operations such as:

* create
* read
* update
* delete
* upsert

The CRUD layer should focus on database operations only.
Feature logic should be placed in `services`, not inside CRUD files.

---

## `backend/app/services/`

This directory contains the main business logic of the project.

Examples of logic that belongs here:

* fetching LeetCode problems
* verifying solved problems
* calculating user level and EXP
* handling stage progression
* calling external APIs
* processing platform statistics

For example:

```text
backend/app/services/leetcode/
backend/app/services/stage/
```

If a feature requires non-trivial logic, it should usually be implemented in `services` and called from a cog.

---

## `alembic/`

This directory is used for database migrations.

When modifying files under `backend/app/models`, a database migration may also be required.

---

## `tests/`

This directory contains project tests.

New features should ideally include corresponding tests, especially for service-layer logic.

---

## Adding a New Feature

When adding a new feature, follow this general rule:

```text
Discord command / UI
→ bot/cogs/

Business logic
→ backend/app/services/

Database operations
→ backend/app/crud/

Database schema
→ backend/app/models/
```

For example, if you want to add a daily problem recommendation feature:

```text
bot/cogs/daily.py
backend/app/services/daily/service.py
backend/app/crud/daily.py
backend/app/models/daily_history.py
```

The cog should handle the Discord command.
The service should decide which problem to recommend.
The CRUD layer should read or write database records.
The model should define any required database tables.

---

## Development Guideline

Keep each layer focused:

```text
Cogs
= Discord interaction only

Services
= feature logic

CRUD
= database queries

Models
= database schema
```

Avoid putting too much logic directly inside Discord cogs.
A cog should usually receive a command, call a service, and return a response.

---

## Pre-commit Hooks

This project provides a pre-commit configuration to run Ruff formatting and lint checks before each commit.

To enable it locally, run:

```bash
uvx pre-commit install
```

To run all hooks manually:

```bash
uvx pre-commit run --all-files
```

The hooks currently run:

```bash
uvx ruff format .
uvx ruff check .
```

Installing the hooks is recommended so formatting and lint issues can be caught before pushing and waiting for CI to fail.

---

## Quick Reference

| Task                                   | Where to Modify                  |
| -------------------------------------- | -------------------------------- |
| Add a new slash command                | `bot/cogs/`                      |
| Change command response or embed       | `bot/cogs/`                      |
| Change LeetCode problem fetching logic | `backend/app/services/leetcode/` |
| Change stage progression logic         | `backend/app/services/stage/`    |
| Add or update database queries         | `backend/app/crud/`              |
| Add or update database tables          | `backend/app/models/`            |
| Add a database migration               | `alembic/`                       |
| Change environment settings            | `backend/app/core/`              |

---

## Summary

CP-Hub follows a layered structure:

```text
Discord commands call services.
Services contain feature logic.
CRUD functions access the database.
Models define the database schema.
```

New developers should usually start by reading:

```text
bot/main.py
bot/cogs/
backend/app/services/
```

For most new features, begin with a new cog under `bot/cogs`, then move the actual logic into `backend/app/services`.
