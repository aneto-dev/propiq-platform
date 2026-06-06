"""
Repository integration tests use the shared fixtures from
`tests/integration/conftest.py`.

Database setup, `async_session`, and `sdlt_version_id` are intentionally defined
once at the integration-test root so Alembic runs only once per test session.
"""
