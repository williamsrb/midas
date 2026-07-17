# Development Guidelines

## Background Tasks

**Never import `lib-portal` in Enonic background tasks.**

The `lib-portal` library depends on a live HTTP request context. Background tasks run outside of any request, so calling portal functions (e.g. `portal.getContent()`, `portal.getSite()`, `portal.url()`) will throw at runtime. Use `lib-content` or `lib-node` directly for data access inside background tasks.
