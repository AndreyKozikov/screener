"""Compatibility import for the database microservice client."""

from app.repository.db.remote_repository import DescribeRepository as DescribeRepository

__all__ = ["DescribeRepository"]
