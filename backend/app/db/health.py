from sqlalchemy import text

from app.db.session import engine


async def database_is_healthy() -> bool:
    """
    Verify database connectivity.

    Returns:
        True if SELECT 1 succeeds.
        False otherwise.
    """

    try:
        async with engine.begin() as connection:
            await connection.execute(text("SELECT 1"))

        return True

    except Exception:
        return False
