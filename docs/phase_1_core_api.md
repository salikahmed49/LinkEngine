# Phase 1: Core API & Database Layer

---

## 1. Concepts & Objectives

Phase 1 establishes the fundamental CRUD foundation for the Link Analytics Platform:
1. **URL Shortening**: Generating collision-resistant, compact 7-character base62 tokens ($62^7 \approx 3.52 \text{ trillion}$ combinations) or user-specified custom aliases.
2. **Database Abstraction**: Persisting link records in PostgreSQL (production) or SQLite (testing) via SQLAlchemy 2.0 ORM.
3. **Data Validation**: Enforcing RFC-compliant HTTP/HTTPS URLs and alias constraints using Pydantic v2.
4. **Fast Redirection**: Resolving short codes and issuing `HTTP 307 Temporary Redirect` responses.

---

## 2. Where Each Functionality Lives in the Code

| Functionality | Exact File & Symbols | Description |
|---|---|---|
| **Database Connection & Lifespan** | [`app/core/database.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/core/database.py) (`engine`, `SessionLocal`, `get_db`)<br>[`app/main.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/main.py#L22-L28) (`lifespan`) | Creates the database engine connection pool, manages scoped request sessions, and initializes database tables automatically on startup via `Base.metadata.create_all`. |
| **Relational Data Model** | [`app/models.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/models.py#L7-L18) (`Link`) | Defines the `links` table schema: `id`, `short_code` (unique, indexed), `original_url` (varchar 2048), `click_count` (integer), and `created_at` (timezone-aware UTC). |
| **Pydantic Validation Schemas** | [`app/schemas.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/schemas.py#L9-L40) (`LinkCreate`, `LinkUpdate`, `LinkResponse`) | Validates URL format with `HttpUrl`, enforces custom alias regex (`^[a-zA-Z0-9_-]{3,10}$`), and standardizes API output formats. |
| **Short Code Generation & Collision Retries** | [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L32-L88) (`generate_short_code`, `create_link`) | Generates random base62 tokens using cryptographically secure `secrets.choice`. On database duplicate key collisions, catches `IntegrityError`, rolls back, and retries up to 5 times. |
| **Redirect & CRUD Routes** | [`app/routes/links.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/routes/links.py#L18-L85) (`create_short_link`, `redirect_to_original`, `get_stats`, `update_link`, `delete_link`) | Exposes endpoints: `POST /links`, `GET /{short_code}`, `GET /links/{short_code}/stats`, `PATCH /links/{short_code}`, `DELETE /links/{short_code}`. |

---

## 3. Code Deep Dive

### 3.1 Collision-Resistant Token Generation
In [`app/services/link_service.py`](file:///c:/Users/salik/Documents/link-analytics-platform/app/services/link_service.py#L42-L88):

```python
def create_link(db: Session, link_data: LinkCreate) -> Link:
    if link_data.custom_alias:
        # User specified custom alias -> single-attempt insert
        code = link_data.custom_alias
        new_link = Link(short_code=code, original_url=str(link_data.original_url))
        db.add(new_link)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError(f"short_code '{code}' already exists")
        db.refresh(new_link)
        return new_link

    # Auto-generate with collision retry loop
    for attempt in range(1, MAX_GENERATION_RETRIES + 1):
        code = generate_short_code()
        new_link = Link(short_code=code, original_url=str(link_data.original_url))
        db.add(new_link)
        try:
            db.commit()
            db.refresh(new_link)
            return new_link
        except IntegrityError:
            db.rollback()
            logger.warning(f"Short code collision on '{code}' (attempt {attempt}/{MAX_GENERATION_RETRIES})")

    raise RuntimeError("Failed to generate a unique short code after multiple attempts.")
```

**Why this matters**:
- **Custom Aliases**: If a user requests an alias that is taken, we fail immediately with a `409 Conflict`.
- **Auto-Generated Codes**: If an auto-generated random code collides with an existing record, the application does not crash or return an error to the user; it silently rolls back the transaction and generates a new code.

---

## 4. Key Architectural Takeaways

1. **Why HTTP 307 instead of HTTP 301**:
   - `HTTP 301 Moved Permanently`: Browsers aggressively cache the redirect locally on client machines. If you use 301, subsequent visits from that browser will bypass your server completely, making click tracking impossible.
   - `HTTP 307 Temporary Redirect`: Directs the browser to redirect immediately while guaranteeing that the client will revisit your server on future clicks, preserving analytics accuracy.
2. **Dependency Injection with `get_db`**:
   - Using FastAPI's `Depends(get_db)` ensures every HTTP request receives an isolated database transaction that automatically closes and returns to the connection pool when the request finishes, preventing database connection leaks.
