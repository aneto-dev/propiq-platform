from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """
    Root SQLAlchemy declarative base.

    Every ORM model in the system inherits from this class.
    """
