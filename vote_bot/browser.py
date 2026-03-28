import os
import subprocess
import time
import random
import urllib.request
from pathlib import Path
import ctypes
from ctypes import wintypes
from datetime import datetime

from .config import *

_LAST_BROWSER = None
_LAST_CONTEXT = None

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36"

def apply_stealth(page):
    try:
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Aplicação de stealth")

        page.add_init_script("""
            () => {
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['pt-BR', 'pt', 'en-US', 'en']
                });
                
                window.navigator.chrome = {
                    runtime: {},
                    loadTimes: function() {},
                    csi: function() {},
                    app: {}
                };
                
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
                
                Object.defineProperty(navigator, 'hardwareConcurrency', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'deviceMemory', {
                    get: () => 8
                });
                
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
                });
                
                Object.defineProperty(navigator, 'vendor', {
                    get: () => 'Google Inc.'
                });
                
                Object.defineProperty(navigator, 'maxTouchPoints', {
                    get: () => 0
                });
                
                delete navigator.__proto__.webdriver;
                
                const getParameter = WebGLRenderingContext.prototype.getParameter;
                WebGLRenderingContext.prototype.getParameter = function(parameter) {
                    if (parameter === 37445) {
                        return 'Intel Inc.';
                    }
                    if (parameter === 37446) {
                        return 'Intel Iris OpenGL Engine';
                    }
                    return getParameter.call(this, parameter);
                };
                
                const elementDescriptor = Object.getOwnPropertyDescriptor(HTMLElement.prototype, 'offsetHeight');
                Object.defineProperty(HTMLDivElement.prototype, 'offsetHeight', {
                    ...elementDescriptor,
                    get: function() {
                        if (this.id === 'modernizr') {
                            return 1;
                        }
                        return elementDescriptor.get.apply(this);
                    },
                });
                
                const originalToString = Function.prototype.toString;
                Function.prototype.toString = function() {
                    if (this === navigator.permissions.query) {
                        return 'function query() { [native code] }';
                    }
                    return originalToString.call(this);
                };
                
                ['height', 'width'].forEach(property => {
                    const imageDescriptor = Object.getOwnPropertyDescriptor(HTMLImageElement.prototype, property);
                    Object.defineProperty(HTMLImageElement.prototype, property, {
                        ...imageDescriptor,
                        get: function() {
                            if (this.complete && this.naturalHeight == 0) {
                                return 20;
                            }
                            return imageDescriptor.get.apply(this);
                        },
                    });
                });
                
                Object.defineProperty(navigator.connection || {}, 'rtt', {
                    get: () => 100
                });
                
                if (!window.chrome) {
                    window.chrome = {};
                }
                if (!window.chrome.runtime) {
                    window.chrome.runtime = {};
                }
                
                const originalAddEventListener = EventTarget.prototype.addEventListener;
                EventTarget.prototype.addEventListener = function(type, listener, options) {
                    if (type === 'devtoolschange') {
                        return;
                    }
                    return originalAddEventListener.call(this, type, listener, options);
                };
                
                Object.defineProperty(navigator, 'doNotTrack', {
                    get: () => null
                });
                
                const mockPluginArray = {
                    length: 3,
                    0: {
                        name: 'Chrome PDF Plugin',
                        filename: 'internal-pdf-viewer',
                        description: 'Portable Document Format'
                    },
                    1: {
                        name: 'Chrome PDF Viewer',
                        filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai',
                        description: ''
                    },
                    2: {
                        name: 'Native Client',
                        filename: 'internal-nacl-plugin',
                        description: ''
                    }
                };
                
                Object.defineProperty(navigator, 'plugins', {
                    get: () => mockPluginArray
                });
            }
        """)
        
        page.add_init_script("""
            () => {
                try {
                    const hiddenDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'hidden') ||
                                       Object.getOwnPropertyDescriptor(document, 'hidden');
                    if (hiddenDesc && hiddenDesc.configurable) {
                        Object.defineProperty(document, 'hidden', {
                            get: () => false,
                            configurable: true
                        });
                    }
                } catch (e) {}
                try {
                    const visDesc = Object.getOwnPropertyDescriptor(Document.prototype, 'visibilityState') ||
                                    Object.getOwnPropertyDescriptor(document, 'visibilityState');
                    if (visDesc && visDesc.configurable) {
                        Object.defineProperty(document, 'visibilityState', {
                            get: () => 'visible',
                            configurable: true
                        });
                    }
                } catch (e) {}
            }
        """)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Stealth executado com sucesso")
    except Exception as e:
        print(f"Erro ao aplicar stealth scripts: {e}")

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


def _window_rows(default: int = 1) -> int:
    for name in ("WINDOW_ROWS", "INSTANCES_ROWS"):
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


def _grid_for_instances(total: int, default_columns: int = 3) -> tuple[int, int]:
    """
    Retorna (columns, rows). Para 4 instancias, padrao = 2x2.
    Se total nao for informado, cai no default_columns x 1.
    """
    if total <= 0:
        return default_columns, 1

    if total == 4:
        return 2, 2

    # aproximacao simples: tenta deixar o grid mais "quadrado"
    cols = max(1, int((total ** 0.5) + 0.9999))  # ceil(sqrt(total)) sem importar math
    rows = max(1, (total + cols - 1) // cols)
    return cols, rows


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


def _bounds_for_instance(columns: int | None = None, rows: int | None = None):
    if INSTANCE_ID <= 0:
        return None
    instances_total = 0
    raw_total = (os.getenv("INSTANCES_TOTAL") or os.getenv("TOTAL_INSTANCES") or "").strip()
    if raw_total:
        try:
            instances_total = int(raw_total)
        except ValueError:
            instances_total = 0

    default_cols, default_rows = _grid_for_instances(instances_total, default_columns=3)
    if columns is None:
        columns = _window_columns(default=default_cols)
    if rows is None:
        rows = _window_rows(default=default_rows)
    if columns <= 0 or rows <= 0:
        return None
    if INSTANCE_ID > (columns * rows):
        return None

    work_left, work_top, work_width, work_height = _get_work_area()
    col_width = max(1, work_width // columns)
    row_height = max(1, work_height // rows)

    idx = INSTANCE_ID - 1
    col = idx % columns
    row = idx // columns

    left = work_left + col * col_width
    top = work_top + row * row_height
    width = col_width if col < (columns - 1) else (work_left + work_width - left)
    height = row_height if row < (rows - 1) else (work_top + work_height - top)
    return {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}


def arrange_window(page, columns: int | None = None):
    if not BRING_TO_FRONT:
        return
    bounds = _bounds_for_instance(columns=columns, rows=None)
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
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-infobars",
        "--disable-notifications",
        "--disable-popup-blocking",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
        f"--user-agent={USER_AGENT}",
        "--disable-blink-features=AutomationControlled",
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-web-security",
        "--disable-features=IsolateOrigins,site-per-process",
        "--allow-running-insecure-content",
        "--disable-background-timer-throttling",
        "--disable-backgrounding-occluded-windows",
        "--disable-renderer-backgrounding",
        "--disable-hang-monitor",
        "--disable-ipc-flooding-protection",
        "--disable-client-side-phishing-detection",
        "--disable-default-apps",
        "--disable-domain-reliability",
        "--disable-component-extensions-with-background-pages",
        "--disable-breakpad",
        "--disable-sync",
        SITE_URL,
    ]

    disable_features = [
        "IsolateOrigins",
        "site-per-process",
        "ChromeWhatsNewUI",
        "OptimizationGuideModelDownloading",
        "InterestFeedContentSuggestions",
        "Translate",
        "AutomationControlled",
    ]
    
    cmd.append(f"--disable-features={','.join(disable_features)}")

    # Comportamento da janela
    if BRING_TO_FRONT:
        bounds = _bounds_for_instance()
        if bounds:
            cmd.extend([
                f"--window-position={bounds['left']},{bounds['top']}",
                f"--window-size={bounds['width']},{bounds['height']}",
            ])
        else:
            cmd.extend(["--window-position=0,0", "--window-size=1366,768"])
    else:
        print("Iniciando Chrome minimizado...")
        cmd.extend([
            "--start-minimized",
            "--window-size=800,600",
        ])

    if profile_dir:
        cmd.insert(4, f"--profile-directory={profile_dir}")

    # Debug útil (mostra só os flags principais)
    print("Lançando Chrome com flags anti-detecção:")
    print("   --user-agent=...", f"--disable-features={','.join(disable_features)}")
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
    context = browser.contexts[0] if browser.contexts else browser.new_context(
        viewport={"width": 1366, "height": 768},
        user_agent=USER_AGENT,
        locale="pt-BR",
        timezone_id="America/Sao_Paulo",
        java_script_enabled=True,
        bypass_csp=True,
        ignore_https_errors=True,
    )
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
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Aplicação de ensure page alive")
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
            apply_stealth(page)
            return page
    except Exception:
        pass

    try:
        _, context = connect_cdp(playwright)
        page = context.new_page()
        minimize_window(page)
        apply_stealth(page)
        return page
    except Exception as e:
        msg = str(e)
        if "ECONNREFUSED" in msg or "connect_over_cdp" in msg:
            if ensure_devtools_or_launch(timeout=20):
                _, context = connect_cdp(playwright)
                page = context.new_page()
                minimize_window(page)
                apply_stealth(page)
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


def safe_goto(
    page,
    url,
    max_attempts=4,
    base_wait=2.0,
    timeout_ms_base: int = 60000,
    timeout_ms_step: int = 15000,
):
    current_page = page
    attempt = 0
    while attempt < max_attempts:
        try:
            wait_mode = "domcontentloaded" if attempt < 2 else "commit"
            timeout_ms = timeout_ms_base + (attempt * timeout_ms_step)
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



