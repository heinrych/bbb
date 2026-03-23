import os
import subprocess
import time
import random
import urllib.request
from pathlib import Path
import ctypes
from ctypes import wintypes

from .config import *

_LAST_BROWSER = None
_LAST_CONTEXT = None


def _window_columns(default: int = 3) -> int:
    for name in ("WINDOW_COLUMNS", "WINDOW_COLS", "INSTANCES_TOTAL", "TOTAL_INSTANCES"):
        raw = (os.getenv(name) or "").strip()
        if not raw:
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        if value > 0:
            return value
    return default


def _get_work_area():
    try:
        rect = wintypes.RECT()
        SPI_GETWORKAREA = 0x0030
        ok = ctypes.windll.user32.SystemParametersInfoW(SPI_GETWORKAREA, 0, ctypes.byref(rect), 0)
        if ok:
            left = int(rect.left)
            top = int(rect.top)
            width = int(rect.right - rect.left)
            height = int(rect.bottom - rect.top)
            if width > 0 and height > 0:
                return left, top, width, height
    except Exception:
        pass

    try:
        width = int(ctypes.windll.user32.GetSystemMetrics(0))
        height = int(ctypes.windll.user32.GetSystemMetrics(1))
        if width > 0 and height > 0:
            return 0, 0, width, height
    except Exception:
        pass

    return 0, 0, 1920, 1080


def _bounds_for_instance(columns: int | None = None):
    if INSTANCE_ID <= 0:
        return None
    if columns is None:
        columns = _window_columns(default=3)
    if INSTANCE_ID > columns:
        return None

    work_left, work_top, work_width, work_height = _get_work_area()
    col_width = max(1, work_width // columns)
    left = work_left + (INSTANCE_ID - 1) * col_width
    width = col_width if INSTANCE_ID < columns else (work_left + work_width - left)
    return {"left": int(left), "top": int(work_top), "width": int(width), "height": int(work_height)}


def arrange_window(page, columns: int | None = None):
    if not BRING_TO_FRONT:
        return
    bounds = _bounds_for_instance(columns=columns)
    if not bounds:
        return

    try:
        session = page.context.new_cdp_session(page)
        info = session.send("Browser.getWindowForTarget")
        window_id = info.get("windowId")
        if window_id is None:
            return
        try:
            session.send(
                "Browser.setWindowBounds",
                {"windowId": window_id, "bounds": {"windowState": "normal"}},
            )
        except Exception:
            pass
        session.send("Browser.setWindowBounds", {"windowId": window_id, "bounds": bounds})
    except Exception:
        pass

def find_chrome_exe():
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for path in candidates:
        if os.path.isfile(path):
            return path
    raise FileNotFoundError("chrome.exe nao encontrado.")


def launch_chrome_debug(user_data_dir, profile_dir=None):
    chrome_exe = find_chrome_exe()
    cmd = [
        chrome_exe,
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-debugging-address=127.0.0.1",
        f"--user-data-dir={user_data_dir}",
        "--new-window",
        SITE_URL,
    ]
    if BRING_TO_FRONT:
        bounds = _bounds_for_instance()
        if bounds:
            cmd.insert(5, f"--window-position={bounds['left']},{bounds['top']}")
            cmd.insert(6, f"--window-size={bounds['width']},{bounds['height']}")
        else:
            cmd.insert(5, "--window-position=0,0")
            cmd.insert(6, "--window-size=1280,800")
    else:
        print("Iniciando Chrome em segundo plano (janela minimizada)...")
        cmd.insert(5, "--start-minimized")
        # Evita forçar window-position aqui: em Windows + Áreas de Trabalho Virtuais,
        # manipular bounds/posição pode fazer a janela "voltar" para a área original.
        cmd.insert(6, "--window-size=800,600")
    if profile_dir:
        cmd.insert(4, f"--profile-directory={profile_dir}")
    subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def close_all_chrome():
    subprocess.run(
        ["taskkill", "/F", "/IM", "chrome.exe"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )


def wait_devtools(port, timeout=25):
    end = time.time() + timeout
    url = f"http://127.0.0.1:{port}/json/version"
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=0.8) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def connect_cdp(playwright):
    global _LAST_BROWSER, _LAST_CONTEXT
    browser = playwright.chromium.connect_over_cdp(f"http://127.0.0.1:{DEBUG_PORT}")
    context = browser.contexts[0] if browser.contexts else browser.new_context()
    _LAST_BROWSER = browser
    _LAST_CONTEXT = context
    return browser, context


def ensure_devtools_or_launch(profile_to_use=None, timeout=25):
    if wait_devtools(DEBUG_PORT, timeout=timeout):
        return True
    if KILL_CHROME_ON_RETRY:
        close_all_chrome()
        time.sleep(1.5)
    launch_chrome_debug(MAIN_USER_DATA_DIR, profile_to_use or PROFILE_DIR)
    return wait_devtools(DEBUG_PORT, timeout=timeout)


def ensure_page_alive(page, playwright):
    try:
        if page is not None and not page.is_closed():
            _ = page.context.pages
            return page
    except Exception:
        pass

    try:
        if _LAST_CONTEXT is not None:
            _ = _LAST_CONTEXT.pages
            page = _LAST_CONTEXT.new_page()
            minimize_window(page)
            return page
    except Exception:
        pass

    try:
        _, context = connect_cdp(playwright)
        page = context.new_page()
        minimize_window(page)
        return page
    except Exception as e:
        msg = str(e)
        if "ECONNREFUSED" in msg or "connect_over_cdp" in msg:
            if ensure_devtools_or_launch(timeout=20):
                _, context = connect_cdp(playwright)
                page = context.new_page()
                minimize_window(page)
                return page
        raise


def minimize_window(page):
    if BRING_TO_FRONT:
        return
    try:
        session = page.context.new_cdp_session(page)
        info = session.send("Browser.getWindowForTarget")
        window_id = info.get("windowId")
        if window_id is not None:
            try:
                session.send(
                    "Browser.setWindowBounds",
                    {"windowId": window_id, "bounds": {"windowState": "minimized"}},
                )
            except Exception:
                pass
                 
    except Exception:
        pass


def safe_close_page(page):
    try:
        ctx = page.context
        if len(ctx.pages) <= 1:
            return False
        page.close(timeout=3000)
        return True
    except Exception:
        return False


def _same_page(a, b) -> bool:
    if a is b:
        return True
    try:
        a_impl = getattr(a, "_impl_obj", None)
        b_impl = getattr(b, "_impl_obj", None)
        return a_impl is not None and a_impl == b_impl
    except Exception:
        return False


def _close_page_via_cdp(page) -> bool:
    try:
        session = page.context.new_cdp_session(page)
    except Exception:
        return False

    try:
        info = session.send("Target.getTargetInfo")
        target_id = (info.get("targetInfo") or {}).get("targetId")
        if not target_id:
            return False
        session.send("Target.closeTarget", {"targetId": target_id})
        return True
    except Exception:
        return False


def close_other_pages(context, keep_page, timeout_ms: int = 3000):
    try:
        for pg in list(context.pages):
            if _same_page(pg, keep_page):
                continue
            if pg.is_closed():
                continue
            try:
                pg_url = pg.url
            except Exception:
                pg_url = ""

            if not pg_url:
                pg_url = "<sem-url>"
            try:
                try:
                    # Em alguns casos (captcha/tracking pesado), fechar uma guia pode travar.
                    # Timeout curto evita bloquear o loop principal indefinidamente.
                    pg.close(timeout=timeout_ms)
                except Exception:
                    # fallback para CDP, útil quando o Playwright não consegue encerrar a guia
                    if not _close_page_via_cdp(pg):
                        try:
                            print(f"Aviso: nao consegui fechar a guia: {pg_url}")
                        except Exception:
                            pass
            except Exception:
                pass
    except Exception:
        pass


def safe_goto(page, url, max_attempts=4, base_wait=2.0):
    current_page = page
    attempt = 0
    while attempt < max_attempts:
        try:
            wait_mode = "domcontentloaded" if attempt < 2 else "commit"
            timeout_ms = 60000 + (attempt * 15000)
            if current_page.is_closed():
                raise RuntimeError("Page closed before navigation")
            current_page.goto(url, wait_until=wait_mode, timeout=timeout_ms)
            if wait_mode == "commit":
                try:
                    current_page.wait_for_load_state("domcontentloaded", timeout=20000)
                except Exception:
                    pass
            return current_page
        except Exception as e:
            msg = str(e)
            print(f"goto tentativa {attempt+1}/{max_attempts} falhou: {msg}")
            if "Frame has been detached" in msg or "Target page, context or browser has been closed" in msg:
                wait = base_wait + random.uniform(0.5, 1.5)
                time.sleep(wait)
                attempt += 1
                continue
            if "ERR_BLOCKED_BY_RESPONSE" in msg or "blocked" in msg.lower():
                wait = base_wait * (2 ** attempt) + random.uniform(1, 3)
                print(f"Navegacao bloqueada pelo servidor; aguardando {wait:.1f}s antes de tentar novamente.")
                time.sleep(wait)
                attempt += 1
                continue
            if "Timeout" in msg:
                wait = base_wait * (2 ** attempt) + random.uniform(1.0, 2.5)
            else:
                wait = base_wait * (2 ** attempt) + random.uniform(0.5, 1.5)
            time.sleep(wait)
            attempt += 1
    raise RuntimeError(f"safe_goto: falhou ao navegar para {url} apos {max_attempts} tentativas")


def resolve_profile_dir(user_data_dir, preferred_profile):
    Path(user_data_dir).mkdir(parents=True, exist_ok=True)
    preferred_path = Path(user_data_dir) / preferred_profile
    if preferred_path.exists():
        return preferred_profile

    candidates = []
    root = Path(user_data_dir)
    if root.exists():
        for p in root.iterdir():
            if not p.is_dir():
                continue
            name = p.name
            if name == "Default" or name.startswith("Profile "):
                candidates.append(name)

    if candidates:
        if "Default" in candidates:
            return "Default"
        return sorted(candidates)[0]

    # Primeiro uso (VM/maquina nova): deixar o Chrome criar o profile solicitado.
    return preferred_profile



