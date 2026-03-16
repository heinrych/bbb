import os
import subprocess
import time
import random
import urllib.request
from pathlib import Path

from .config import *

_LAST_BROWSER = None
_LAST_CONTEXT = None

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
        cmd.insert(5, "--window-position=0,0")
        cmd.insert(6, "--window-size=1280,800")
    else:
        print("Iniciando Chrome em segundo plano (janela minimizada)...")
        cmd.insert(5, "--start-minimized")
        cmd.insert(6, "--window-position=-32000,-32000")
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

            session.send(
                "Browser.setWindowBounds",
                {"windowId": window_id, "bounds": {"left": -32000, "top": -32000, "width": 800, "height": 600}},
            )
                
    except Exception:
        pass


def safe_close_page(page):
    try:
        ctx = page.context
        if len(ctx.pages) <= 1:
            return False
        page.close()
        return True
    except Exception:
        return False


def close_other_pages(context, keep_page):
    try:
        for pg in list(context.pages):
            if pg != keep_page:
                try:
                    pg.close()
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

    raise FileNotFoundError(
        f"Nenhum perfil encontrado em {user_data_dir}. Esperado: {preferred_profile}"
    )



