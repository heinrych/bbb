import re
import time
from pathlib import Path

from .config import *

def click_candidato(page, nome):
    nome_lower = nome.lower()
    seletores = [
        f"css=button[aria-label*='{nome}']",
        f"xpath=//*[normalize-space(text())='{nome}']/ancestor::*[self::button or self::label or self::article or self::div][1]",
        f"xpath=//*[contains(translate(normalize-space(text()), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{nome_lower}')]/ancestor::*[self::button or self::label or self::article or self::div][1]",
        f"text={nome}",
    ]

    for sel in seletores:
        try:
            alvo = page.locator(sel).first
            alvo.wait_for(state="visible", timeout=8000)
            try:
                alvo.scroll_into_view_if_needed()
            except Exception:
                pass
            alvo.click(timeout=5000)
            return True
        except Exception:
            try:
                # fallback quando algum elemento intercepta ponteiro
                alvo = page.locator(sel).first
                alvo.click(timeout=3000, force=True)
                return True
            except Exception:
                pass

    clicked = page.evaluate(
        """([nome]) => {
            const n = nome.toLowerCase().trim();
            const nodes = Array.from(document.querySelectorAll("*"));
            for (const node of nodes) {
                const txt = (node.textContent || "").toLowerCase().trim();
                if (!txt || !txt.includes(n)) continue;
                let el = node;
                for (let i = 0; i < 6 && el; i++) {
                    const tag = (el.tagName || "").toLowerCase();
                    const role = (el.getAttribute && el.getAttribute("role")) || "";
                    if (tag == "button" || tag == "label" || role == "button" || el.onclick) {
                        el.click();
                        return true;
                    }
                    el = el.parentElement;
                }
            }
            return false;
        }""",
        [nome],
    )
    return bool(clicked)


def click_votar_novamente(page):
    def try_click_in_scope(scope, label):
        try:
            btn = scope.get_by_role("button", name=re.compile(r"votar novamente", re.I)).first
            if btn.count() > 0:
                btn.wait_for(state="visible", timeout=600000)
                btn.scroll_into_view_if_needed()
                btn.click(timeout=400000, force=True)
                print(f"Cliquei em 'Votar Novamente' ({label}/role).")
                return True
        except Exception:
            pass

        text_selectors = [
            "button:visible",
            "[role='button']:visible",
            "a:visible",
        ]
        aria_selectors = [
            "button[aria-label*='votar novamente' i]:visible",
            "[role='button'][aria-label*='votar novamente' i]:visible",
        ]
        for sel in text_selectors:
            try:
                btn = scope.locator(sel, has_text=re.compile(r"votar novamente", re.I)).first
                btn.wait_for(state="visible", timeout=600000)
                btn.scroll_into_view_if_needed()
                btn.click(timeout=400000, force=True)
                print(f"Cliquei em 'Votar Novamente' ({label}).")
                return True
            except Exception:
                continue
        for sel in aria_selectors:
            try:
                btn = scope.locator(sel).first
                btn.wait_for(state="visible", timeout=600000)
                btn.scroll_into_view_if_needed()
                btn.click(timeout=400000, force=True)
                print(f"Cliquei em 'Votar Novamente' ({label}/aria-label).")
                return True
            except Exception:
                continue
        return False

    try:
        if try_click_in_scope(page, "pagina principal"):
            return True
    except Exception:
        pass

    try:
        clicked = bool(
            page.evaluate(
                """() => {
                    const nodes = Array.from(document.querySelectorAll("button, a, [role='button'], div"));
                    for (const n of nodes) {
                        const txt = (n.textContent || "").trim().toLowerCase();
                        if (txt.includes("votar novamente")) {
                            n.click();
                            return true;
                        }
                    }
                    return false;
                }"""
            )
        )
        if clicked:
            print("Cliquei em 'Votar Novamente' (pagina principal/js).")
            return True
    except Exception:
        pass

    for i, frame in enumerate(page.frames):
        try:
            if try_click_in_scope(frame, f"frame {i}"):
                return True
        except Exception:
            continue

    for i, frame in enumerate(page.frames):
        try:
            clicked = bool(
                frame.evaluate(
                    """() => {
                        const nodes = Array.from(document.querySelectorAll("button, a, [role='button'], div"));
                        for (const n of nodes) {
                            const txt = (n.textContent || "").trim().toLowerCase();
                            if (txt.includes("votar novamente")) {
                                n.click();
                                return true;
                            }
                        }
                        return false;
                    }"""
                )
            )
            if clicked:
                print(f"Cliquei em 'Votar Novamente' (frame {i}/js).")
                return True
        except Exception:
            continue

    try:
        time.sleep(0.5)
        if try_click_in_scope(page, "pagina principal retry"):
            return True
    except Exception:
        pass

    try:
        page.keyboard.press("Escape")
    except Exception:
        pass

    try:
        time.sleep(0.4)
        if try_click_in_scope(page, "pagina principal after escape"):
            return True
    except Exception:
        pass

    return False


def setup_network_logging(page, logfile_path=None):
    if logfile_path is None:
        logfile_path = ARTIFACTS_DIR / "network.log"
    logfile_path.parent.mkdir(parents=True, exist_ok=True)

    def log_line(line: str):
        try:
            with open(logfile_path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception:
            pass

    def on_response(r):
        try:
            log_line(f"RESP {r.status()} {r.url}")
        except Exception:
            pass

    def on_request(req):
        try:
            log_line(f"REQ  {req.method} {req.url}")
        except Exception:
            pass

    def on_failed(req):
        try:
            failure = req.failure() or {}
            log_line(f"FAIL {req.url} - {failure}")
        except Exception:
            pass

    try:
        page.on("response", on_response)
        page.on("request", on_request)
        page.on("requestfailed", on_failed)
    except Exception as e:
        print(f"Nao consegui registrar network listeners: {e}")


