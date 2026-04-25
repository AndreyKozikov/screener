---
description: Project coding rules and conventions for BondsScreener. These rules MUST be followed on every code change in this project.
---

# BondsScreener — Project Coding Rules

These rules are always active for the `BondsScreener` workspace. Follow them on **every** code change — no exceptions.

---

## 1. Project Stack Overview

| Layer | Technology | Path |
|-------|-----------|------|
| **Backend** | Python 3, FastAPI, SQLModel, Alembic, SQLite | `backend/` |
| **Frontend** | React 19, TypeScript, Vite, MUI 7, AG Grid, Zustand, TailwindCSS 3, Recharts | `frontend/` |
| **Entry point** | `backend/main.py` | — |

---

## 2. General Architectural Principles

**SOLID Compliance:** All code must strictly adhere to Single Responsibility, Open/Closed, Liskov Substitution, Interface Segregation, and Dependency Inversion principles.

**Layered Architecture (Backend):** Mixing responsibilities between layers is strictly prohibited.

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **API (Routers)** | Incoming requests, schema validation, service calls only | `backend/app/routers/` |
| **Service** | Business logic, coordinating repository operations | `backend/app/services/` |
| **Repository** | Direct database interaction (SQLModel) only | `backend/app/repository/` |
| **Schema / DTO** | Pydantic models for request/response data validation | `backend/app/data/` |
| **Data Models** | SQLModel entities representing database tables | `backend/app/models/` |
| **Core** | Config, exceptions, shared utilities | `backend/app/core/` |
| **Parsers** | External data source parsers | `backend/app/parsers/` |
| **Utils** | Shared utilities | `backend/app/utils/` |

**Frontend Architecture:**

| Layer | Responsibility | Location |
|-------|---------------|----------|
| **Pages** | Top-level route components | `frontend/src/pages/` |
| **Components** | Reusable UI components | `frontend/src/components/` |
| **API** | Backend API call functions (Axios) | `frontend/src/api/` |
| **Stores** | Global state management (Zustand) | `frontend/src/stores/` |
| **Types** | TypeScript type/interface definitions | `frontend/src/types/` |
| **Theme** | MUI theme customization | `frontend/src/theme/` |
| **Utils** | Helper/utility functions | `frontend/src/utils/` |
| **Lib** | Third-party library wrappers/configs | `frontend/src/lib/` |

---

## 3. Backend Coding Standards

### Type Hinting
- **Mandatory** type annotations for all function arguments and return values.
- Use `Optional`, `Union`, `List`, `Dict` from the `typing` module.
- Every function **must** have a return type hint (`-> ReturnType`).

### Naming Conventions
- **Routers:** `backend/app/routers/*.py`
- **Services:** `ClassNameService` in `backend/app/services/*.py`
- **Repositories:** `ClassNameRepository` in `backend/app/repository/*.py`
- **DB Models:** `ClassName` (SQLModel) in `backend/app/models/*.py`
- **Schemas:** `ClassNameCreate`, `ClassNameRead`, `ClassNameUpdate` (Pydantic) in `backend/app/data/*.py`

### Data Handling (SQLModel & SQLite)
- **Repository Pattern:** All database access must go through repository classes exclusively.
- **Unit of Work:** Manage database sessions (`Session`) using FastAPI `Depends`. Pass the session directly into the repository.
- **Model Separation:** NEVER use the same SQLModel class for both DB persistence and API responses. Always use separate Schemas (DTOs).
- **Migrations:** All database schema changes must be handled via Alembic. Generate a migration for every new model or field modification.

### Dependency Injection (DI)
- Use FastAPI's native DI system (`Depends`).
- Inject repositories into services, and services into routers.
- Dependencies must be resolved via DI (abstract or concrete classes) rather than direct instantiation inside functions.

### Error Handling
- **Custom Exceptions:** Define domain-specific exceptions in `backend/app/core/exceptions.py`.
- **HTTP Exceptions:** Convert domain exceptions to `HTTPException` at the router level or via global `exception_handlers`.
- **No Silent Fails:** Empty `except: pass` blocks are strictly forbidden.

### Configuration
- All settings, paths, and environment-specific values must live in `backend/app/core/config.py` or `backend/.env`.
- No hardcoded strings for paths or settings.

---

## 4. Frontend Coding Standards

### TypeScript
- Strict mode enabled. All variables, props, and return types must be properly typed.
- Prefer interfaces over type aliases for object shapes.
- No `any` type unless absolutely unavoidable (and commented why).

### React Conventions
- Functional components only.
- Use hooks (`useState`, `useEffect`, `useMemo`, `useCallback`) appropriately.
- Keep components small and focused — extract reusable logic into custom hooks.

### State Management
- Use **Zustand** stores in `frontend/src/stores/` for global state.
- Avoid prop-drilling deeper than 2 levels — lift state to a store instead.

### Styling
- Use **TailwindCSS 3** and **MUI 7** components.
- Theme customization via `frontend/src/theme/`.

### API Calls
- All backend API interactions go through functions in `frontend/src/api/`.
- Use **Axios** for HTTP requests.
- Never call `fetch()` or `axios` directly from components — always through the API layer.

---

## 5. Critical Prohibitions (STRICT)

These are **absolute rules** — violation is never acceptable.

### Backend
- ❌ **PROHIBITED:** Writing business logic inside routers (endpoints).
- ❌ **PROHIBITED:** Direct database calls (`engine.execute`, `session.query`, etc.) inside services or routers — must go through repository.
- ❌ **PROHIBITED:** Using hardcoded strings for paths or settings (use `backend/app/core/config.py`).
- ❌ **PROHIBITED:** Returning SQLModel objects (DB entities) directly in API responses without converting to a Pydantic schema.
- ❌ **PROHIBITED:** Defining functions without a return type hint (`-> ReturnType`).
- ❌ **PROHIBITED:** Empty `except: pass` blocks.

### Frontend
- ❌ **PROHIBITED:** Using `any` type without an explanatory comment.
- ❌ **PROHIBITED:** Direct `axios`/`fetch` calls from React components (use the API layer).
- ❌ **PROHIBITED:** Inline styles when TailwindCSS classes or MUI `sx` prop can be used.

---

## 6. Workflow Guidelines

### Before Making Changes
1. Understand which layer(s) the change affects.
2. Check existing patterns in the codebase — follow established conventions.
3. For DB changes: always create an Alembic migration.

### When Creating New Endpoints
1. Define the Pydantic schema (DTO) in `backend/app/data/`.
2. Create or update the repository in `backend/app/repository/`.
3. Create or update the service in `backend/app/services/`.
4. Create the router endpoint in `backend/app/routers/`.
5. Register the router in `backend/main.py` if it's a new router.

### When Creating New Frontend Features
1. Define TypeScript types in `frontend/src/types/`.
2. Create API functions in `frontend/src/api/`.
3. Create/update Zustand store if global state is needed in `frontend/src/stores/`.
4. Build UI components in `frontend/src/components/`.
5. Wire everything together in a page component in `frontend/src/pages/`.

---

## 7. Language

- All code comments, variable names, and documentation should be in **English**.
- Communication with the user: respond in the **same language the user uses** (Russian or English).
