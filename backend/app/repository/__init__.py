"""Репозиторий для работы с базой данных и файлами.

Пакет содержит:
    db: модули, работающие только с базой данных SQLite
        (bonds_repository, db_coupon, db_kbd, constants)
    files: модули, работающие с JSON файлами (file_storage)
    db_orchestrator: оркестратор миграций данных (использует db и files)
"""
