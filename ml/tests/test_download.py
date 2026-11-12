from pathlib import Path

import pytest

from cartsense_ml.data.download import download_file


class FakeResponse:
    def __init__(self, body: bytes, content_length: int | None = None, status: int = 200):
        self._body = body
        self.status_code = status
        self.headers = {}
        if content_length is not None:
            self.headers["Content-Length"] = str(content_length)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_content(self, chunk_size):
        for i in range(0, len(self._body), chunk_size):
            yield self._body[i : i + chunk_size]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeSession:
    def __init__(self, response: FakeResponse):
        self.response = response
        self.calls = 0

    def get(self, url, stream, timeout):
        self.calls += 1
        return self.response


def test_downloads_and_writes_file(tmp_path: Path):
    body = b"x" * 3_000_000
    session = FakeSession(FakeResponse(body, content_length=len(body)))
    dest = download_file("http://example/f.gz", tmp_path / "raw" / "f.gz", session=session)
    assert dest.read_bytes() == body
    assert not (tmp_path / "raw" / "f.gz.part").exists()


def test_skips_existing_file_unless_forced(tmp_path: Path):
    dest = tmp_path / "f.gz"
    dest.write_bytes(b"old")
    session = FakeSession(FakeResponse(b"new", content_length=3))

    download_file("http://example/f.gz", dest, session=session)
    assert dest.read_bytes() == b"old" and session.calls == 0

    download_file("http://example/f.gz", dest, session=session, force=True)
    assert dest.read_bytes() == b"new" and session.calls == 1


def test_truncated_download_is_discarded(tmp_path: Path):
    session = FakeSession(FakeResponse(b"abc", content_length=10))
    dest = tmp_path / "f.gz"
    with pytest.raises(IOError):
        download_file("http://example/f.gz", dest, session=session)
    assert not dest.exists()
    assert not (tmp_path / "f.gz.part").exists()


def test_http_error_propagates(tmp_path: Path):
    session = FakeSession(FakeResponse(b"", status=404))
    with pytest.raises(RuntimeError):
        download_file("http://example/missing.gz", tmp_path / "m.gz", session=session)
