import time
import random
import re
from pathlib import Path
from datetime import datetime

from .config import *
from .users import pick_user_email
from .browser import (
    connect_cdp,
    ensure_devtools_or_launch,
    ensure_page_alive,
    safe_goto,
    minimize_window,
    arrange_window,
    safe_close_page,
    close_other_pages,
    apply_stealth,
)
from .counter import incrementar_contador


class RestartInitialFlow(RuntimeError):
    pass


def _dump_debug_artifacts(page, prefix: str):
    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    except Exception:
        return

    ts = int(time.time() * 1000)
    try:
        url = page.url
    except Exception:
        url = ""

    base = f"{prefix}_{ts}"

    # try:
    #     screenshot_path = Path(ARTIFACTS_DIR) / f"{base}.png"
    #     page.screenshot(path=str(screenshot_path), full_page=True)
    #     print(f"Debug: screenshot salvo: {screenshot_path} (url={url})")
    # except Exception:
    #     pass

    try:
        html_path = Path(ARTIFACTS_DIR) / f"{base}.html"
        html = page.content()
        html_path.write_text(html, encoding="utf-8", errors="ignore")
        print(f"Debug: html salvo: {html_path}")
    except Exception:
        pass


def is_hcaptcha_challenge_visible(page) -> bool:
    """
    Detecta a janela/iframe do desafio do hCaptcha (ex.: frame=challenge).

    Isso não tenta resolver captcha; apenas detecta a UI para voltar ao fluxo inicial.
    """
    selectors = [
        "iframe[src*='hcaptcha'][src*='frame=challenge']",
        "iframe[src*='newassets.hcaptcha.com'][src*='frame=challenge']",
        "iframe[title*='desafio hcaptcha' i]",
        "iframe[title*='hcaptcha' i][src*='frame=challenge']",
    ]
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            if loc.count() > 0 and loc.is_visible():
                return True
        except Exception:
            continue
    return False

def has_entrar(page):
    try:
        # Se encontrar o botão "Entrar" visível, NÃO está logado
        entrar_selectors = [
            "button.codex-login__button:has(span.codex-login__button-label:has-text('Entrar com Conta Globo'))",
            "button.codex-login__button:has-text('Entrar com Conta Globo')",
            "span.codex-login__button-label:has-text('Entrar com Conta Globo')",
            "button:has-text('Entrar com Conta Globo')",
            "a:has-text('Entrar com Conta Globo')",
            "button:has-text('Entrar')",
        ]
        
        for scope in [page] + list(page.frames):
            for sel in entrar_selectors:
                try:
                    loc = scope.locator(sel).first
                    if loc.count() > 0 and loc.is_visible():
                        # Encontrou botão "Entrar" visível -> NÃO está logado
                        return False
                except Exception:
                    continue
        
        # Não encontrou botão "Entrar" visível -> assume que está logado
        return True
        
    except Exception as e:
        print(f"Erro ao verificar status de login: {e}")
        return False



def clear_page_cache(page):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR PAGE CACHE")
    try:
        if page.is_closed():
            return
    except Exception:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR PAGE CACHE - PAGE IS  CLOSED")
        return
    
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR PAGE CACHE - PAGE EVALUATE")
        page.evaluate(
            """() => {
                try { localStorage.clear(); } catch (e) {}
                try { sessionStorage.clear(); } catch (e) {}
            }"""
        )
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao limpar storage/cache da página: {e}")

    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR PAGE CACHE - CLEAN COOKIES")
        page.context.clear_cookies(domain=".hcaptcha.com")
        page.context.clear_cookies(domain=".cloudflare.com")
    except Exception:
        pass


def clear_hcaptcha_cookies(page):
    try:
        if page.is_closed():
            return
    except Exception:
        return

    _CAPTCHA_DOMAINS = {"hcaptcha.com", "newassets.hcaptcha.com", "cloudflare.com", "challenges.cloudflare.com"}

    try:
        cookies = page.context.cookies()
        filtered = [
            c for c in cookies
            if not any(
                (c.get("domain") or "").lower().lstrip(".").endswith(d)
                for d in _CAPTCHA_DOMAINS
            )
        ]

        page.context.clear_cookies()

        if filtered:
            page.context.add_cookies(filtered)

        print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookies de captcha limpos. Mantidos: {len(filtered)}/{len(cookies)}")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}]  Erro ao limpar cookies do hCaptcha: {e}")


def recreate_page_after_captcha(page, playwright=None):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Recriando página para evitar lentidão do hCaptcha...")

    for attempt in range(3):
        try:
            if playwright is not None:
                page = ensure_page_alive(page, playwright)

            browser = page.context.browser
            try:
                if hasattr(browser, "is_connected") and not browser.is_connected():
                    raise RuntimeError("Browser desconectado")
            except Exception:
                pass

            try:
                clear_hcaptcha_cookies(page)
            except Exception:
                pass

            try:
                context = browser.contexts[0] if browser.contexts else browser.new_context()
            except Exception as e:
                print(f"Falha ao recriar pagina apos captcha: {e}")

                if playwright is not None and ensure_devtools_or_launch(timeout=20):
                    try:
                        _, context = connect_cdp(playwright)
                    except Exception as e2:
                        print(f"Falha ao reconectar via CDP: {e2}")
                        context = page.context
                else:
                    context = page.context

            new_page = context.new_page()
            apply_stealth(new_page)
            minimize_window(new_page)
            new_page = safe_goto(
                new_page,
                SITE_URL,
                max_attempts=HCAPTCHA_FAST_GOTO_MAX_ATTEMPTS,
                base_wait=1.5,
                timeout_ms_base=HCAPTCHA_FAST_GOTO_TIMEOUT_MS_BASE,
                timeout_ms_step=HCAPTCHA_FAST_GOTO_TIMEOUT_MS_STEP,
            )

            try:
                if not page.is_closed():
                    page.close()
            except Exception:
                pass

            try:
                close_other_pages(context, new_page)
            except Exception:
                pass

            return new_page
        except Exception as e:
            print(f"Falha ao abrir nova pagina apos captcha: {e}")
            # try:
            #     _dump_debug_artifacts(page, "captcha_recreate_fail")
            # except Exception:
            #     pass
            time.sleep(1.5 + attempt)

    try:
        return hard_reset_browser(page)
    except Exception as e:
        print(f"Falha no hard_reset_browser apos captcha: {e}")
        return page


def clear_browser_state(page):
    try:
        if page.is_closed():
            return
    except Exception:
        return
    print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR BROSWER STATE")
    clear_page_cache(page)

    session = None
    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR BROSER STATE - CLEAN CONTEXT")
        session = page.context.new_cdp_session(page)
        session.send("Network.enable")
        session.send("Network.clearBrowserCache")
        session.send("Network.clearBrowserCookies")
        print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR BROSER STATE - CLEAN CONTEXT OK")
    except Exception as e:
        print(f"Nao consegui limpar cache/cookies via CDP: {e}")
    finally:
        try:
            if session is not None:
                session.detach()
        except Exception:
            pass

    print(f"[{datetime.now().strftime('%H:%M:%S')}] CLEAR BROSWER STATE FINALY")


def goto_login_from_site(page):
    """Entra no fluxo de login a partir do Gshow para evitar endpoints authx desatualizados."""
    apply_stealth(page)
    time.sleep(random.uniform(1.5, 3.0))
    page = safe_goto(page, SITE_URL)

    login_selectors = [
        "button.codex-login__button:has-text('Entrar com Conta Globo')",
        "button:has-text('Entrar com Conta Globo')",
        "a:has-text('Entrar com Conta Globo')",
        "button:has-text('Entrar')",
        "a:has-text('Entrar')",
    ]

    hover_candidates = [
        "div.codex-login",
        "li.codex-header__item--login",
        "[class*='login']",
        "header",
    ]
    for hover_sel in hover_candidates:
        try:
            el = page.locator(hover_sel).first
            if el.count() > 0:
                el.hover(timeout=2000)
                break
        except Exception:
            continue

    for sel in login_selectors:
        try:
            btn = page.locator(sel).first
            btn.wait_for(state="visible", timeout=3500)
            btn.click(timeout=3500)
            return page
        except Exception:
            continue

    try:
        target_login_url = page.evaluate(
            """() => {
                const links = Array.from(document.querySelectorAll("a[href]"));
                const direct = links.find((a) => {
                    const href = (a.getAttribute("href") || "").toLowerCase();
                    return href.includes("login.globo.com/login/");
                });
                if (direct) return direct.href;

                const authLink = links.find((a) => {
                    const href = (a.getAttribute("href") || "").toLowerCase();
                    return href.includes("authx.globoid.globo.com") || href.includes("goidc.globo.com");
                });
                return authLink ? authLink.href : "";
            }"""
        )
        if target_login_url:
            page = safe_goto(page, target_login_url)
            if "not-found" in (page.url or "").lower():
                page = safe_goto(page, SITE_URL)
    except Exception:
        pass

    return page


def handle_optional_defer_prompt(page, timeout_ms=8000):

    selectors = [
        "button.secondary-button[aria-label*='Prefiro deixar para depois']",
        "button[ng-click='skipIntervention(true)']",
        "button:has-text('Prefiro deixar para depois')",
        "a:has-text('Prefiro deixar para depois')",
        "[role='button']:has-text('Prefiro deixar para depois')",
    ]
    deadline = time.time() + (timeout_ms / 1000.0)
    while time.time() < deadline:
        for scope in [page] + list(page.frames):
            for sel in selectors:
                try:
                    btn = scope.locator(sel).first
                    if btn.count() == 0:
                        continue
                    btn.wait_for(state="visible", timeout=900)
                    btn.click(timeout=2000)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Opcional detectado: cliquei em 'Prefiro deixar para depois'.")
                    return True
                except Exception:
                    continue
        time.sleep(0.25)
    return False

def handle_captcha_and_refresh(page, playwright=None):
    """Tenta resolver captcha e recria a página se necessário"""
    try:
        overall_deadline = time.time() + max(10.0, float(HCAPTCHA_STUCK_MAX_S))
        if is_hcaptcha_challenge_visible(page):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Janela do desafio do hCaptcha detectada. Voltando ao fluxo inicial...")
            raise RestartInitialFlow("hCaptcha challenge visível")

        found_votar_novamente = False
        captcha_clicked = False
        votar_novamente_selectors = [
            "button:has-text('Votar Novamente')",
            "button[aria-label*='votar novamente' i]",
            "[role='button']:has-text('Votar Novamente')",
            "[role='button'][aria-label*='votar novamente' i]",
        ]

        def detect_votar_novamente_button():
            try:
                # acessible name inclui aria-label e texto visível
                loc = page.get_by_role("button", name=re.compile(r"votar novamente", re.I)).first
                if loc.count() > 0:
                    try:
                        if loc.is_visible():
                            return True
                    except Exception:
                        return True
            except Exception:
                pass
            for scope in [page] + list(page.frames):
                for sel in votar_novamente_selectors:
                    try:
                        loc = scope.locator(sel).first
                        if loc.count() == 0:
                            continue
                        try:
                            if loc.is_visible():
                                return True
                        except Exception:
                            return True
                    except Exception:
                        continue
            return False
        
        for i in range(VOTAR_NOVAMENTE_RETRY):

            if time.time() > overall_deadline:
                raise RestartInitialFlow("hCaptcha carregando por muito tempo (antes do click)")
                 
            try:
                frame = page.frame_locator("iframe[src*='hcaptcha.com']").first
                cb = frame.locator("div[role='checkbox']").first

                if cb.count() > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] hCaptcha detectado. Clicando para abrir...")
                    cb.wait_for(state="visible", timeout=5000)
                    cb.scroll_into_view_if_needed()
                    time.sleep(random.uniform(2.5, 5))
                    cb.click(timeout=5000, force=True)
                    captcha_clicked = True

                    # Se isso abrir a janela de desafio, não tentamos resolver: reinicia o fluxo.
                    deadline = time.time() + 4.0
                    while time.time() < deadline:
                        if is_hcaptcha_challenge_visible(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Desafio do hCaptcha abriu. Voltando ao fluxo inicial...")
                            raise RestartInitialFlow("hCaptcha challenge abriu após click")
                        time.sleep(0.25)
                    break
            except RestartInitialFlow:
                raise
            except Exception:
                # iframe/elemento pode ainda não estar pronto; tenta novamente
                pass
            
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Tentativa ({i+1}/{VOTAR_NOVAMENTE_RETRY}) para detectar hCaptcha...")
            time.sleep(random.uniform(2,4))
            
            if i + 1 >= VOTAR_NOVAMENTE_RETRY:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] hCaptcha não detectado após várias tentativas. Reiniciando fluxo inicial...")
                raise RestartInitialFlow("hCaptcha não detectado após várias tentativas")

        if not captcha_clicked:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Não consegui clicar no hCaptcha. Reiniciando fluxo inicial...")
            raise RestartInitialFlow("hCaptcha não foi clicado")
     
        for i in range(VOTAR_NOVAMENTE_RETRY):

            print(f"Tentativa ({i+1}/{VOTAR_NOVAMENTE_RETRY}) para detectar resolução do hCaptcha...")

            if time.time() > overall_deadline:
                raise RestartInitialFlow("hCaptcha carregando por muito tempo (apos click)")

            if is_hcaptcha_challenge_visible(page):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Janela do desafio do hCaptcha detectada durante espera. Voltando ao fluxo inicial...")
                raise RestartInitialFlow("hCaptcha challenge visível durante espera")

            # Se não abriu janela de desafio, aguardar um pouco para o fluxo "invisible" completar.
            wait_s = 6.0
            start = time.time()
            while time.time() - start < wait_s:
                if is_hcaptcha_challenge_visible(page):
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Janela do desafio do hCaptcha detectada. Voltando ao fluxo inicial...")
                    raise RestartInitialFlow("hCaptcha challenge visível durante espera curta")
                time.sleep(0.5)

            try:
                # verifica botão votar novamente (pode aparecer junto/antes da confirmação)
                if detect_votar_novamente_button():
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Botão 'Votar Novamente' detectado!")
                    found_votar_novamente = True
                    break

                # verifica se apareceu a tela de voto confirmado
                if page.locator("text=Seu voto").count() > 0:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Página de confirmação detectada!")

                    # às vezes o botão aparece logo após a confirmação; dá uma pequena janela pra ele renderizar
                    deadline = time.time() + 4.0
                    while time.time() < deadline and not found_votar_novamente:
                        if detect_votar_novamente_button():
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Botão 'Votar Novamente' detectado!")
                            found_votar_novamente = True
                            break
                        time.sleep(0.25)

                    if found_votar_novamente:
                        break
                    if i + 1 < VOTAR_NOVAMENTE_RETRY:
                        continue

                print(f"[{datetime.now().strftime('%H:%M:%S')}] hCaptcha ainda parece presente...")

            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Erro ao verificar página:", e)

            if i + 1 >= VOTAR_NOVAMENTE_RETRY:
                raise Exception(f"[{datetime.now().strftime('%H:%M:%S')}] Captcha ainda presente após várias tentativas.")
        
        if found_votar_novamente:
            total_interacoes = incrementar_contador(COUNTER_FILE)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Contador salvo em {COUNTER_FILE}: {total_interacoes}")
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Botão 'Votar Novamente' não foi detectado; contador não foi incrementado.")
                          
        # Após resolver, recria a página para evitar lentidão
        return recreate_page_after_captcha(page, playwright)

    except RestartInitialFlow:
        raise
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Sem hCaptcha visível ou erro: {e}")
        
        # Fallback para o método antigo (manter compatibilidade)
        try:
            frame = page.frame(url=re.compile(r"hcaptcha\.com"))
            if frame:
                frame.evaluate("""
                    () => {
                        const el = document.querySelector("div[role='checkbox']");
                        if (el) {
                            el.scrollIntoView({block: 'center'});
                            el.click();
                        }
                    }
                """)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Cliquei no hCaptcha via evaluate (fallback). Aguardando resolução...")
                time.sleep(20)

                # Recria a página
                return recreate_page_after_captcha(page, playwright)
        except:
            raise Exception("hCaptcha não detectado e fallback falhou. Continuando sem clicar.")

    return page


def perform_login(page, max_attempts=3, clear_cache=True):
    url_lower = (page.url or "").lower()
    on_auth_page = "authx.globoid.globo.com" in url_lower or "goidc.globo.com" in url_lower

    if not on_auth_page and has_entrar(page):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Ja autenticado, ignorando perform_login.")
        return True

    apply_stealth(page)
    time.sleep(random.uniform(2.0, 4.0))
    
    if clear_cache:
        try:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando limpeza de estado")
            clear_browser_state(page)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache/cookies limpos antes do perform_login.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Falha ao limpar cache antes do perform_login: {e}")

    for attempt in range(max_attempts):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Iniciando tentativa {attempt} de login")
        login_stage = "inicio"
        try:
            login_stage = "check_page_state"
            if page.is_closed():
                page = page.context.new_page()
                page = safe_goto(page, SITE_URL)

            if "not-found" in page.url.lower():
                page = safe_goto(page, SITE_URL)

            def has_password_now():
                try:
                    return any(
                        page.locator(sel).count() > 0
                        for sel in [
                            "input[name='password']",
                            "input[type='password']",
                            "input[placeholder*='senha' i]",
                        ]
                    )
                except Exception:
                    return False

            current_url = (page.url or "").lower()
            on_auth_page = ("authx.globoid.globo.com" in current_url) or ("goidc.globo.com" in current_url)

            if (
                not on_auth_page
                and page.locator("input[name='email'], input[type='email'], input[name='login']").count() == 0
                and not has_password_now()
            ):
                login_stage = "click_entrar_com_conta_globo"
                clicked_login = False

                hover_candidates = [
                    "div.codex-login",
                    "li.codex-header__item--login",
                    "[class*='login']",
                    "header",
                ]
                for hover_sel in hover_candidates:
                    try:
                        el = page.locator(hover_sel).first
                        if el.count() > 0:
                            el.hover(timeout=2000)
                            break
                    except Exception:
                        continue

                login_candidates = [
                    "button.codex-login__button:has(span.codex-login__button-label:has-text('Entrar com Conta Globo'))",
                    "button.codex-login__button:has-text('Entrar com Conta Globo')",
                    "button:has-text('Entrar com Conta Globo')",
                ]
                for sel in login_candidates:
                    try:
                        btn = page.locator(sel).first
                        btn.wait_for(state="visible", timeout=5000)
                        btn.click(timeout=5000)

                        if has_entrar(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Menu exibiu 'Minha conta': sessao ja ativa.")
                            return True
                        clicked_login = True
                        break
                    except Exception:
                        continue
                if not clicked_login:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Botao 'Entrar com Conta Globo' nao encontrado; tentando abrir login pelo site.")
                    page = goto_login_from_site(page)

            login_stage = "wait_login_context"
            if page.locator("input[name='email'], input[type='email'], input[name='login']").count() == 0:
                page.wait_for_function(
                    """() => {
                        const href = (window.location && window.location.href ? window.location.href : "").toLowerCase();
                        return !!document.querySelector("input[name='email'], input[type='email'], input[name='login']") ||
                               href.includes("authx.globoid.globo.com") || href.includes("goidc.globo.com") ||
                               !!document.querySelector("div.codex-dropdown__dialog.codex-dialog--open");
                    }""",
                    timeout=12000,
                )

            if page.locator("input[name='email'], input[type='email'], input[name='login']").count() == 0:
                login_stage = "click_dropdown_entrar"
                primary_btn = page.locator(
                    "div.codex-dropdown__dialog.codex-dialog--open button.globoid-login__list-button--primary:visible"
                ).first
                try:
                    primary_btn.wait_for(state="visible", timeout=12000)
                    primary_btn.scroll_into_view_if_needed(timeout=2000)
                    primary_btn.click(timeout=5000)
                except Exception:
                    clicked = bool(
                        page.evaluate(
                            """() => {
                                const btn = document.querySelector(
                                  "div.codex-dropdown__dialog.codex-dialog--open button.globoid-login__list-button--primary"
                                );
                                if (!btn) return false;
                                btn.scrollIntoView({ block: "center", inline: "center" });
                                btn.click();
                                return true;
                            }"""
                        )
                    )
                    if not clicked:
                        if has_entrar(page):
                            handle_optional_defer_prompt(page, timeout_ms=7000)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Botao primario 'Entrar' nao encontrado; sessao ja autenticada (Minha conta visivel).")
                            return True

                        href_now = (page.url or "").lower()
                        if "authx.globoid.globo.com" not in href_now and "goidc.globo.com" not in href_now:
                            handle_optional_defer_prompt(page, timeout_ms=7000)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Botao primario 'Entrar' nao encontrado/clicavel; fora do auth, assumindo login ativo.")
                            return True

                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Botao primario 'Entrar' nao encontrado/clicavel; tentando seguir para o campo de email.")

            email_step_done = False
            email_input = None
            email_scope = page
            login_stage = "find_email_input_optional"
            email_selectors = [
                "input[name='email']:visible",
                "input[type='email']:visible",
                "input[name='login']:visible",
                "input[name='email']",
                "input[type='email']",
                "input[name='login']",
            ]
            for scope in [page] + list(page.frames):
                found = False
                for sel in email_selectors:
                    try:
                        candidate = scope.locator(sel).first
                        candidate.wait_for(state="attached", timeout=4000)
                        candidate.wait_for(state="visible", timeout=6000)
                        email_input = candidate
                        email_scope = scope
                        found = True
                        break
                    except Exception:
                        continue
                if found:
                    break

            if email_input is not None:
                login_stage = "fill_email"
                time.sleep(random.uniform(0.8, 1.5))
                email_input.click(timeout=5000)
                time.sleep(random.uniform(0.3, 0.7))
                email_value = pick_user_email()
                for char in email_value:
                    email_input.type(char, delay=random.randint(50, 150))
                    time.sleep(random.uniform(0.01, 0.05))
                time.sleep(random.uniform(0.5, 1.0))
                email_scope.locator("button:has-text('Continuar'), button[type='submit']").first.click(timeout=6000)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Etapa de email detectada e preenchida.")
                email_step_done = True
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Etapa de email nao apareceu; seguindo direto para senha.")

            pwd = None
            pwd_scope = page
            login_stage = "find_password_input"
            pwd_selectors = [
                "input[name='password']",
                "input[type='password']",
                "input[placeholder*='senha' i]",
            ]
            wait_deadline = time.time() + 25
            while time.time() < wait_deadline and pwd is None:
                for scope in [page] + list(page.frames):
                    found = False
                    for sel in pwd_selectors:
                        try:
                            nodes = scope.locator(sel)
                            count = nodes.count()
                            if count == 0:
                                continue
                            for idx in range(count):
                                candidate = nodes.nth(idx)
                                if not candidate.is_visible():
                                    continue
                                if not candidate.is_editable():
                                    continue
                                pwd = candidate
                                pwd_scope = scope
                                found = True
                                break
                            if found:
                                break
                        except Exception:
                            continue
                    if found:
                        break
                if pwd is None:
                    time.sleep(0.3)

            if pwd is None:
                raise RuntimeError(f"[{datetime.now().strftime('%H:%M:%S')}] Campo de senha visivel nao encontrado.")

            login_stage = "fill_password"
            time.sleep(random.uniform(1.0, 2.0))
            pwd.click(timeout=5000)
            time.sleep(random.uniform(0.3, 0.7))
            try:
                pwd.press("Control+A", timeout=1500)
                time.sleep(random.uniform(0.1, 0.3))
                pwd.press("Backspace", timeout=1500)
                time.sleep(random.uniform(0.2, 0.4))
            except Exception:
                pass
            try:
                for char in USER_PASSWORD:
                    pwd.type(char, delay=random.randint(80, 180))
                    time.sleep(random.uniform(0.02, 0.08))
            except Exception:
                pwd.fill(USER_PASSWORD, timeout=5000)

            pwd_filled = False
            try:
                pwd_filled = bool(
                    pwd.evaluate("(el) => !!el && typeof el.value === 'string' && el.value.length > 0")
                )
            except Exception:
                pwd_filled = False

            if not pwd_filled:
                try:
                    pwd.evaluate(
                        """(el, password) => {
                            if (!el) return false;
                            el.focus();
                            el.value = password;
                            el.dispatchEvent(new Event("input", { bubbles: true }));
                            el.dispatchEvent(new Event("change", { bubbles: true }));
                            return !!el.value;
                        }""",
                        USER_PASSWORD,
                    )
                    pwd_filled = True
                except Exception:
                    pwd_filled = False

            if not pwd_filled:
                raise RuntimeError("Nao foi possivel preencher o campo de senha.")

            time.sleep(random.uniform(0.6, 1.4))

            def has_password_anywhere():
                checks = [
                    "input[name='password']",
                    "input[type='password']",
                    "input[placeholder*='senha' i]",
                ]
                for scope in [page] + list(page.frames):
                    for sel in checks:
                        try:
                            if scope.locator(sel).count() > 0:
                                return True
                        except Exception:
                            continue
                return False

            def login_effect_observed():
                href = (page.url or "").lower()
                if ("authx.globoid.globo.com" not in href) and ("goidc.globo.com" not in href):
                    return True
                return not has_password_anywhere()

            def has_auth_error():
                error_selectors = [
                    "[aria-invalid='true']",
                    "[id$='-error']",
                    "p:has-text('incorreta')",
                    "p:has-text('inválida')",
                    "p:has-text('invalida')",
                    "span:has-text('incorreta')",
                ]
                for scope in [page] + list(page.frames):
                    for sel in error_selectors:
                        try:
                            loc = scope.locator(sel).first
                            if loc.count() > 0 and loc.is_visible():
                                txt = (loc.inner_text(timeout=800) or "").strip().lower()
                                if txt:
                                    return True
                        except Exception:
                            continue
                return False

            submit_selectors = [
                "button.Button__BaseButton-sc-1dl9u2w-0.Button__PrimaryButton-sc-1dl9u2w-1[type='submit']:has-text('Entrar')",
                "button[type='submit'][aria-disabled='false']:has-text('Entrar')",
                "button[type='submit']:has-text('Entrar')",
            ]

            got_403 = [False]

            def _on_response_403(response):
                try:
                    if "authx-api.globoid.globo.com" in response.url and response.status == 403:
                        got_403[0] = True
                except Exception:
                    pass

            try:
                page.on("response", _on_response_403)
            except Exception:
                pass

            login_submitted = False
            clicked_at_least_once = False
            login_stage = "click_submit_entrar"
            try:
                for submit_try in range(6):
                    submit = None
                    submit_scope = None
                    for scope in [pwd_scope, page] + list(page.frames):
                        if submit is not None:
                            break
                        for sel in submit_selectors:
                            try:
                                btn = scope.locator(sel).first
                                btn.wait_for(state="visible", timeout=1500)
                                submit = btn
                                submit_scope = scope
                                break
                            except Exception:
                                continue

                    if submit is None:
                        time.sleep(0.5)
                        continue

                    try:
                        page.wait_for_function(
                            """(el) => {
                                if (!el) return false;
                                const aria = (el.getAttribute("aria-disabled") || "").toLowerCase();
                                return !el.disabled && aria !== "true";
                            }""",
                            arg=submit.element_handle(),
                            timeout=3000,
                        )
                    except Exception:
                        pass

                    try:
                        submit.scroll_into_view_if_needed(timeout=1500)
                    except Exception:
                        pass

                    try:
                        box = submit.bounding_box()
                        if box:
                            x = box["x"] + random.uniform(box["width"] * 0.3, box["width"] * 0.7)
                            y = box["y"] + random.uniform(box["height"] * 0.3, box["height"] * 0.7)
                            page.mouse.move(x, y, steps=random.randint(8, 15))
                            time.sleep(random.uniform(0.3, 0.8))
                    except Exception:
                        pass

                    try:
                        submit.click(timeout=4000)
                        clicked_at_least_once = True
                    except Exception:
                        try:
                            box = submit.bounding_box()
                            if box:
                                x = box["x"] + (box["width"] / 2)
                                y = box["y"] + (box["height"] / 2)
                                page.mouse.move(x, y, steps=random.randint(6, 14))
                                page.mouse.down()
                                time.sleep(random.uniform(0.03, 0.12))
                                page.mouse.up()
                                clicked_at_least_once = True
                        except Exception:
                            pass

                    if has_auth_error():
                        raise RuntimeError("Login recusado pela pagina (senha/credencial invalida ou validacao bloqueada).")

                    try:
                        if not clicked_at_least_once:
                            submit.click(timeout=4000, force=True)
                            clicked_at_least_once = True
                    except Exception:
                        pass

                    for _ in range(12):
                        if login_effect_observed():
                            login_submitted = True
                            break
                        if is_hcaptcha_challenge_visible(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Captcha detectado durante login. Reiniciando tentativa...")
                            page = hard_reset_browser(page)
                            raise RestartInitialFlow("Captcha apareceu durante login")
                        if got_403[0]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 403 recebido do authx. Executando hard reset...")
                            got_403[0] = False
                            page = hard_reset_browser(page)
                            raise RestartInitialFlow("403 Forbidden durante login")
                        time.sleep(0.25)
                    if login_submitted:
                        break

                    try:
                        pwd.press("Enter", timeout=2000)
                        clicked_at_least_once = True
                    except Exception:
                        pass

                    for _ in range(10):
                        if login_effect_observed():
                            login_submitted = True
                            break
                        if is_hcaptcha_challenge_visible(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Captcha detectado durante login. Reiniciando tentativa...")
                            raise RestartInitialFlow("Captcha apareceu durante login")
                        if got_403[0]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 403 recebido do authx. Executando hard reset...")
                            got_403[0] = False
                            page = hard_reset_browser(page)
                            raise RestartInitialFlow("403 Forbidden durante login")
                        time.sleep(0.25)
                    if login_submitted:
                        break

                    try:
                        clicked_js = bool(
                            submit_scope.evaluate(
                                """() => {
                                    const btn = document.querySelector("button[type='submit'][aria-disabled='false'], button[type='submit']");
                                    if (!btn) return false;
                                    btn.click();
                                    return true;
                                }"""
                            )
                        )
                        if clicked_js:
                            clicked_at_least_once = True
                    except Exception:
                        pass

                    for _ in range(10):
                        if login_effect_observed():
                            login_submitted = True
                            break
                        if is_hcaptcha_challenge_visible(page):
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Captcha detectado durante login. Reiniciando tentativa...")
                            raise RestartInitialFlow("Captcha apareceu durante login")
                        if got_403[0]:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] 403 recebido do authx. Executando hard reset...")
                            got_403[0] = False
                            page = hard_reset_browser(page)
                            raise RestartInitialFlow("403 Forbidden durante login")
                        time.sleep(0.25)
                    if has_auth_error():
                        raise RuntimeError("Login recusado pela pagina apos submit.")
                    if login_submitted:
                        break

            finally:
                try:
                    page.remove_listener("response", _on_response_403)
                except Exception:
                    pass

            if not login_submitted:
                raise RuntimeError(
                    f"Clique em 'Entrar' nao teve efeito apos preencher senha (tentativas={submit_try+1}, clicou={clicked_at_least_once})."
                )

            if not email_step_done:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Senha preenchida sem etapa de email; confirmei 'Entrar' antes do redirecionamento.")

            # AGORA sim, após o login ser submetido, verificamos se apareceu a tela "Prefiro deixar para depois"
            # e clicamos nela para FINALIZAR o login
            handle_optional_defer_prompt(page, timeout_ms=9000)

            # Verifica se está logado ANTES de voltar para a página principal
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Verificando se login foi bem-sucedido...")
            
            # Aguarda um pouco para os cookies serem estabelecidos
            time.sleep(3)
            
            # Tenta verificar se já está logado pelo menu "Minha conta"
            if has_entrar(page):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Menu 'Minha conta' visível - login confirmado!")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Menu 'Minha conta' não detectado, mas login foi submetido - considerando logado.")


            return True
            
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Tentativa {attempt+1}/{max_attempts} de login falhou em '{login_stage}': {e}")
            if attempt < max_attempts - 1:
                wait_time = random.uniform(2, 4)
                print(f"Aguardando {wait_time:.1f}s antes de tentar novamente...")
                time.sleep(wait_time)

    print(f"Falha no login automatico apos {max_attempts} tentativas")
    return False


def perform_login_legacy(page, max_attempts=2, clear_cache=True):
    """Fallback simples de login (estilo antigo)."""
    if clear_cache:
        try:
            clear_browser_state(page)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cache/cookies limpos antes do perform_login_legacy.")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Falha ao limpar cache antes do perform_login_legacy: {e}")

    for attempt in range(max_attempts):
        try:
            if page.is_closed():
                page = page.context.new_page()

            href = (page.url or "").lower()
            if "authx.globoid.globo.com" not in href:
                page = goto_login_from_site(page)
                href = (page.url or "").lower()
                if "authx.globoid.globo.com" not in href and "goidc.globo.com" not in href:
                    page = safe_goto(page, LOGIN_URL)
                    if "not-found" in (page.url or "").lower():
                        page = safe_goto(page, SITE_URL)

            # Email opcional.
            try:
                email = page.locator("input[name='email'], input[type='email'], input[name='login']").first
                if email.count() > 0:
                    email.wait_for(state="visible", timeout=9000)
                    email.fill(pick_user_email(), timeout=5000)
                    page.locator("button:has-text('Continuar'), button[type='submit']").first.click(timeout=5000)
            except Exception:
                pass

            pwd = page.locator("input[name='password'], input[type='password'], input[placeholder*='senha' i]").first
            pwd.wait_for(state="visible", timeout=15000)
            pwd.fill(USER_PASSWORD, timeout=5000)
            page.locator("button[type='submit']:has-text('Entrar')").first.click(timeout=5000)

            page.wait_for_function(
                """() => {
                    const hrefNow = (window.location && window.location.href ? window.location.href : "").toLowerCase();
                    const hasPwd = !!document.querySelector("input[name='password'], input[type='password']");
                    return (!hrefNow.includes("authx.globoid.globo.com") && !hrefNow.includes("goidc.globo.com")) || !hasPwd;
                }""",
                timeout=20000,
            )
            handle_optional_defer_prompt(page, timeout_ms=9000)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Login legacy preenchido automaticamente.")
            return True
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Tentativa legacy {attempt + 1}/{max_attempts} falhou: {e}")
            if attempt < max_attempts - 1:
                time.sleep(random.uniform(1.5, 3.0))
    return False


def ensure_authenticated(page):
    """Garante autenticacao no inicio do fluxo, antes do loop principal."""
    for hover_sel in ["div.codex-login", "li.codex-header__item--login", "[class*='login']", "header"]:
        try:
            el = page.locator(hover_sel).first
            if el.count() > 0:
                el.hover(timeout=2000)
                break
        except Exception:
            continue

    try:
        url_lower = page.url.lower()
        on_auth_page = "authx.globoid.globo.com" in url_lower or "goidc.globo.com" in url_lower
        must_login = (
                on_auth_page
                or page.locator("input[name='email']").count() > 0
                or page.locator("button:has-text('Entrar com Conta Globo'):visible").count() > 0
        )
        if not on_auth_page and has_entrar(page):
            must_login = False
        print(f"[{datetime.now().strftime('%H:%M:%S')}] ensure_authenticated: must_login={must_login}")
    except Exception:
        must_login = True

    if not must_login:
        return page

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Autenticacao inicial detectada. Executando login antes do loop...")
    if not perform_login(page):
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Login principal falhou na autenticacao inicial. Tentando fallback legacy...")
        if not perform_login_legacy(page):
            raise RuntimeError("Falha na autenticacao inicial.")
    return safe_goto(page, SITE_URL)


def clean_cache_and_login(page):
    """Limpando cache e recriando página para evitar lentidão do captcha"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Limpando cache/contexto...")

    # Salva o contexto antes de fechar a página
    context = page.context
    try:
        if hasattr(context, "is_closed") and context.is_closed():
            raise RuntimeError("Contexto fechado antes da limpeza.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Contexto inválido: {e}")
        return page

    try:
        if not page.is_closed():
            try:
                page.close(timeout=3000)
            except Exception:
                safe_close_page(page)
    except Exception:
        pass

    # Cria uma nova página completamente nova
    try:
        page = context.new_page()
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Nao consegui abrir nova pagina no contexto: {e}")
        return page
    close_other_pages(context, page)
    minimize_window(page)

    try:
        # Limpa o estado do navegador
        clear_browser_state(page)
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Falha ao limpar cache: {e}")

    # Força uma nova sessão
    try:
        context.clear_cookies()
    except Exception:
        pass

    for i in range(2):
        try:
            page = safe_goto(page, SITE_URL)
            if "not-found" in page.url.lower():
                page = safe_goto(page, SITE_URL)
            if not perform_login(page):
                print(f"[{datetime.now().strftime('%H:%M:%S')}] perform_login falhou apos limpar cache. Tentando fallback legacy...")
                if not perform_login_legacy(page):
                    raise RuntimeError("perform_login e fallback legacy falharam apos limpar cache.")
            return page
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Nao consegui executar login automatico apos limpar cache (tentativa {i + 1}/2): {e}")
            # Se falhar, cria outra página nova
            page = context.new_page()

    return page


def hard_reset_browser(page):
    """Reset mais agressivo - recria contexto inteiro"""
    old_context = page.context
    browser = old_context.browser

    new_context = browser.new_context()
    new_context.clear_cookies()

    new_page = new_context.new_page()
    apply_stealth(new_page)
    if BRING_TO_FRONT:
        arrange_window(new_page)
    else:
        minimize_window(new_page)
    new_page = safe_goto(new_page, SITE_URL)

    try:
        old_context.close()
    except Exception:
        pass

    return new_page
