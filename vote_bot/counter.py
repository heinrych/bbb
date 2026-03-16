from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import time

from .config import COUNTER_FILE

try:
    import msvcrt  # type: ignore
except Exception:  # pragma: no cover
    msvcrt = None

try:
    import fcntl  # type: ignore
except Exception:  # pragma: no cover
    fcntl = None


@contextmanager
def _locked_text_file(path: Path, timeout_s: float = 5.0, poll_s: float = 0.05):
    path.parent.mkdir(parents=True, exist_ok=True)
    file_obj = path.open("a+", encoding="utf-8")
    start = time.time()
    locked = False
    try:
        while not locked:
            try:
                if msvcrt is not None:
                    file_obj.seek(0)
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_NBLCK, 1)
                    locked = True
                elif fcntl is not None:
                    fcntl.flock(file_obj.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    locked = True
                else:
                    locked = True
            except Exception:
                if time.time() - start >= timeout_s:
                    raise TimeoutError(f"Timeout ao tentar lock do contador: {path}")
                time.sleep(poll_s)

        file_obj.seek(0)
        yield file_obj
    finally:
        try:
            if locked:
                if msvcrt is not None:
                    file_obj.seek(0)
                    msvcrt.locking(file_obj.fileno(), msvcrt.LK_UNLCK, 1)
                elif fcntl is not None:
                    fcntl.flock(file_obj.fileno(), fcntl.LOCK_UN)
        finally:
            file_obj.close()


def interacao_atual() -> int:
    try:
        with _locked_text_file(COUNTER_FILE) as file_obj:
            value = (file_obj.read() or "").strip() or "0"
            return int(value)
    except Exception:
        return 0


def incrementar_contador(path_arquivo: Path) -> int:
    try:
        with _locked_text_file(path_arquivo) as file_obj:
            current_value = (file_obj.read() or "").strip() or "0"
            try:
                valor_atual = int(current_value)
            except Exception:
                valor_atual = 0

            novo_valor = valor_atual + 1
            file_obj.seek(0)
            file_obj.truncate()
            file_obj.write(str(novo_valor))
            file_obj.flush()
            return novo_valor
    except Exception:
        # Fallback: mantém comportamento anterior se algo der errado com lock.
        valor_atual = 0
        if path_arquivo.exists():
            try:
                valor_atual = int(path_arquivo.read_text(encoding="utf-8").strip() or "0")
            except Exception:
                valor_atual = 0
        novo_valor = valor_atual + 1
        path_arquivo.write_text(str(novo_valor), encoding="utf-8")
        return novo_valor

