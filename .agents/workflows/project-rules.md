---
description: Current BondsScreener development rules: service architecture, coding conventions, and verification.
---

# BondsScreener Development Rules

These rules apply to development of the BondsScreener application. They do not define behavior for user-facing features embedded in the application.

## 1. User Communication and Code Comments

- Communicate with the user only in Russian: questions, explanations, progress reports, and final responses.
- Write all new source-code comments and all new or rewritten docstrings in Russian.
- When modifying code, translate any English comment or docstring that is directly affected, when appropriate. Do not make unrelated bulk edits solely to translate existing comments.
- Keep variable, function, class, module, and API-field names in English unless an existing interface or project convention requires otherwise.
- Do not translate library, protocol, command, external API, or technical identifier names.
- Write documentation in the language of its intended audience and existing document. This does not change the language requirement for comments and docstrings.

## 2. Architecture and Stack

The project has four parts. Before making a change, identify its owner and trace the relevant API boundaries.

| Part | Responsibility | Main paths |
|---|---|---|
| `backend/` | Main HTTP API, application services, authentication, portfolios, and request proxying | `backend/main.py`, `backend/app/`, `backend/config/` |
| `conversion_service/` | External data ingestion, parsing, transformation, scheduled updates, file processing, and imports | `conversion_service/run_conv_service.py`, `conversion_service/app/`, `conversion_service/config/` |
| `db_repository/` | Separate HTTP service for SQLite access, models, repositories, and migrations | `db_repository/main_db.py`, `db_repository/models/`, `db_repository/repository/`, `db_repository/services/`, `db_repository/config/` |
| `frontend/` | React 19, TypeScript, Vite, MUI, AG Grid, Zustand, and charts | `frontend/src/` |

The Python services use FastAPI and Pydantic. Services access data across boundaries through HTTP clients and repository API contracts. Do not connect `backend/` or `conversion_service/` directly to SQLite files or bypass `db_repository` without an established contract.

### Responsibility Boundaries

- Routers handle HTTP input, validation, calls to application logic, and HTTP responses. Put complex domain rules in the appropriate service.
- In `backend/app/repository/` and `conversion_service/app/repository/`, use the existing adapters for the remote repository and file storage. Do not duplicate their transport logic in routers or services.
- Only `db_repository/` is responsible for direct SQLite access. Follow its existing separation between models, repository operations, services, and RPC/API.
- In `conversion_service/`, keep external data retrieval, format parsing, DTO transformation, and persistence distinct. Avoid mixing source-specific behavior into shared models without a clear need.
- In the frontend, place server requests in `frontend/src/api/`, shared types in `frontend/src/types/`, global state in `frontend/src/stores/`, reusable UI in `frontend/src/components/`, and pages in `frontend/src/pages/`.
- Do not create a parallel abstraction when a suitable client, service, repository, DTO, or component already exists nearby.

## 3. API and Model Changes

- Preserve compatibility between HTTP and RPC contracts across services and the frontend. When changing a contract, find and update all its consumers.
- Use Pydantic DTOs to validate input and shape responses. Do not return ORM/SQLModel entities directly when the project API uses DTOs.
- Follow the naming, structure, and style of comparable endpoints. Do not move code between services as part of a small feature change.
- Use the settings and `config/` directory belonging to the relevant service. Do not hardcode secrets or environment-specific values in source code.

## 4. Databases and Migrations

- Represent every persisted SQLite schema change with an Alembic migration; changing only the ORM model is insufficient.
- First identify the affected database and migration directory. `db_repository/` has separate migration trees: `alembic/`, `blog_alembic/`, `history_alembic/`, and `portfolio_alembic/`. Do not mix them.
- Inspect neighboring migrations and the service's database initialization path. Account for SQLite limitations and use a migration approach compatible with this project.
- Update DTOs, RPC allowlists/routing, and consumers when a public repository operation changes.
- Do not delete data or run migrations against a production database without an explicit user request.

## 5. Financial Calculations and Market Data

- Before changing a calculation, study the existing implementation and project conventions. Check `backend/app/portfolio/calculators/` and `frontend/src/utils/` for the relevant calculation.
- Do not change rounding, calendar, day-count, offer, coupon, accrued-interest, or date-handling rules without checking all affected callers.
- In loaders and parsers, preserve handling of missing, malformed, and partially available data. An external-source failure must not silently become a plausible but incorrect value.
- Preserve update idempotency and error traceability. Do not add retries or fallback values that can hide corrupted data.
- For calculation changes, add or update targeted boundary-case checks using the test style already used in the relevant module.

## 6. Frontend Rules

- Use TypeScript and API types. Avoid `any`; if unavoidable, keep it at the integration boundary and explain why in a Russian comment.
- Use Axios through the project's API modules. Do not call `fetch` or Axios directly from React components when a suitable API module exists.
- Follow the existing Zustand stores for global state. Keep component state local unless it must be shared across screens.
- Use the installed MUI, AG Grid, Tailwind, and chart libraries. Do not add a dependency for a task that the existing stack can handle.
- Preserve the existing theme, number/date formatting, navigation, and responsive behavior.

## 7. Configuration, Security, and Errors

- Each service has its own configuration: `backend/config/`, `conversion_service/config/`, and `db_repository/config/`; example files use the `.example` suffix. Keep secrets in local `.env` files or environment variables, not in the repository.
- Do not print secret values in logs, responses, documentation, or reports. Do not weaken API-key, request-signature, or authentication checks to simplify a test.
- Catch only expected exceptions and retain diagnostic information. Do not use empty `except` blocks, `except: pass`, or broad error suppression.
- Before changing public error behavior, check how calling services and the frontend handle it.

## 8. Checks and Project Commands

Choose checks based on the affected part. Never claim a command passed unless it was run.

- Frontend: `npm run lint` and `npm run build` are available from `frontend/`.
- Python: tests use `unittest` and are located in `backend/tests/`, `conversion_service/tests/`, `conversion_service/scheduled_updates/tests/`, and `db_repository/tests/`. Run relevant tests from the repository or service root with the correct `PYTHONPATH`.
- For parsers, calculations, DTOs, RPC, and migrations, check the relevant module and its tests first. Do not treat a build of an unrelated service as verification.
- Do not run production deployments, systemd management commands, or operations on production databases as part of routine verification.
- If a check cannot be run, state the exact reason and what remains unverified.

## 9. Deployment and Repository Hygiene

- Production deployment is documented in `deploy/README.md`. Services run under systemd, external traffic passes through Nginx, and deployment is configured in `.github/workflows/deploy.yml`.
- Do not assume Docker is available; the documented deployment runs without it.
- Before changing deployment behavior, trace the path from GitHub Actions through `deploy/deploy.sh`, then inspect related systemd and Nginx configuration.
- Do not edit generated files, local data, logs, `.venv`, `node_modules`, or configuration files containing secrets.
- Preserve the user's existing work. Do not revert or reformat unrelated files.

## 10. Workflow

1. Identify the service and layer responsible for the change.
2. Study a comparable implementation, its DTOs/contracts, and its direct consumers.
3. Make the smallest coherent change across all affected layers.
4. Update targeted tests and migrations when needed.
5. Run appropriate checks when the task and environment allow it, and report their results accurately.
6. In the final response, use Russian to summarize the changes, checks performed, and any remaining limitations.

### Systematic Debugging Skill

Use the `systematic-debugging` skill only when analyzing a stack trace or error output supplied by the user, or when the user asks to fix an application runtime error or a failure that occurred during testing. Do not invoke it for ordinary feature work, refactoring, code review without a reported error, documentation, or speculative error prevention.
