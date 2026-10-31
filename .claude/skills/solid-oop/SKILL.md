---
name: solid-oop
description: >
  Keep ReadRight Python code modular with clear ownership and narrow interfaces.
  Use when designing or reviewing application classes and services.
---

# Object-oriented guidelines

- Give each class one clear responsibility.
- Depend on a protocol only when an implementation must be replaceable or
  isolated in tests. Do not add protocols for every class by default.
- Keep constructors explicit and inject external dependencies.
- Keep HTTP parsing in routers, persistence in repositories, and domain rules
  in focused functions or services.
- Prefer simple composition over inheritance. Use inheritance only when
  substitutable implementations share stable behavior.
- Keep state local to the request or owning object. Do not load models or create
  external clients in request handlers.
- Avoid utility classes that only wrap a stateless function.
