import pytest

from app.config import normalize_database_url, redact_database_url


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("postgres://u:p@host:5432/db", "postgresql+psycopg://u:p@host:5432/db"),
        ("postgresql://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ("postgresql+psycopg://u:p@host/db", "postgresql+psycopg://u:p@host/db"),
        ('  "postgres://u:p@host/db"\n', "postgresql+psycopg://u:p@host/db"),
        ("sqlite:///./cartsense.db", "sqlite:///./cartsense.db"),
    ],
)
def test_normalize_database_url(raw, expected):
    assert normalize_database_url(raw) == expected


def test_redact_database_url_hides_password():
    assert redact_database_url("postgresql+psycopg://user:s3cr3t@host/db") == "postgresql+psycopg://user:***@host/db"
    assert redact_database_url("sqlite:///./cartsense.db") == "sqlite:///./cartsense.db"


def test_startup_reports_unreachable_database(monkeypatch, caplog):
    import asyncio

    from sqlalchemy.exc import OperationalError

    import app.main as main

    def failing_init_db():
        raise OperationalError("SELECT 1", {}, Exception("could not translate host name"))

    monkeypatch.setattr(main, "init_db", failing_init_db)
    monkeypatch.setattr(main, "STARTUP_DELAY_SECONDS", 0)
    with pytest.raises(RuntimeError):
        asyncio.run(main.connect_with_retry())
    assert "could not translate host name" in caplog.text
    assert "External URL" in caplog.text


@pytest.mark.parametrize("url", ["postgresql+psycopg://", "postgres://", "postgresql:///"])
def test_startup_rejects_url_without_host(monkeypatch, caplog, url):
    import asyncio

    import app.main as main
    from app.config import Settings

    monkeypatch.setattr(main, "get_settings", lambda: Settings(database_url=url))
    monkeypatch.setattr(main, "init_db", lambda: pytest.fail("must not try to connect"))
    with pytest.raises(RuntimeError, match="incomplete"):
        asyncio.run(main.connect_with_retry())
    assert "copy button" in caplog.text


def test_cors_origins_tolerate_trailing_slashes_and_quotes():
    from app.config import Settings

    s = Settings(cors_origins=' "https://shop.vercel.app/" , http://localhost:3000/,, ')
    assert s.cors_origin_list == ["https://shop.vercel.app", "http://localhost:3000"]
