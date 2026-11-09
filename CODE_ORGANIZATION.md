# 5.4. Code Organization

The backend is a feature-oriented FastAPI application. Each package under `app/features/` groups a domain area—such as `me`, `dashboard`, `reading`, and `comprehension`—and keeps its API and data-access code together. Shared configuration, authentication dependencies, health routes, and common helpers live outside those feature packages.

```text
app/
├── main.py                 # App creation, middleware, and router registration
├── config.py               # Environment-backed settings
├── dependencies/           # Authentication, API-key, and Supabase clients
├── routers/                # Cross-cutting routes such as health checks
├── features/<feature>/     # Feature-specific API and business logic
│   ├── controller.py       # HTTP routes, validation, and response mapping
│   ├── service.py          # Use-case and business rules
│   ├── repository.py       # Supabase persistence operations
│   └── models.py           # Request, response, and data models
└── utils/                  # Shared utilities
```

The typical request flows from a **controller** to a **service**, then to a **repository** for persistence. Controllers handle HTTP concerns; services coordinate rules and workflows; repositories isolate Supabase queries. Feature modules may include additional files for integrations, such as `mai/client.py` and `me/storage.py`. Database migrations are in `supabase/migrations/`, and automated tests are in `tests/`.

Packages and Python modules use lowercase `snake_case`; classes use `PascalCase`; functions and variables use `snake_case`; constants use `UPPER_SNAKE_CASE`. API models use descriptive names, commonly ending in `Request` or `Response`, and test modules use the `test_*.py` pattern.
