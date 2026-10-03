from pathlib import Path


def test_schema_contains_long_term_memory_tables():
    sql = (Path(__file__).parents[1] / "app" / "db" / "database.py").read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS conversations" in sql
    assert "CREATE TABLE IF NOT EXISTS chat_messages" in sql
    assert "CREATE TABLE IF NOT EXISTS conversation_memory" in sql
