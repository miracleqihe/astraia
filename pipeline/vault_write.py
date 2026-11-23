"""Serialize vault writes and write card files atomically."""

from collections.abc import Iterator
from contextlib import contextmanager
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from pipeline.vault import VaultError


@contextmanager
def vault_writer(vault: Path) -> Iterator[None]:
    if not vault.is_dir():
        raise VaultError(f"知识库目录不存在：{vault}")
    with (vault / ".astraia.lock").open("a+b") as lock:
        if os.name == "nt":
            import msvcrt

            if lock.tell() == 0:
                lock.write(b"\0")
                lock.flush()
            lock.seek(0)
            msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl

            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        yield


def create_card(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix=".astraia-card-", dir=path.parent) as directory:
        temporary = Path(directory) / "card.tmp"
        temporary.write_bytes(content)
        try:
            os.link(temporary, path)
        except FileExistsError as error:
            raise VaultError(f"卡片已存在，保留现有内容。{path}") from error


def replace_card(path: Path, content: bytes) -> None:
    with TemporaryDirectory(prefix=".astraia-card-", dir=path.parent) as directory:
        temporary = Path(directory) / "card.tmp"
        temporary.write_bytes(content)
        temporary.replace(path)
