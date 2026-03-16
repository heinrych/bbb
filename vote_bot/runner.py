import time
import random
from pathlib import Path
from playwright.sync_api import sync_playwright

from .config import *
from .browser import (
    resolve_profile_dir,
    ensure_devtools_or_launch,
    close_all_chrome,
    launch_chrome_debug,
    wait_devtools,
    connect_cdp,
    safe_goto,
    minimize_window,
    ensure_page_alive,
    close_other_pages,
)
from .actions import click_candidato
from .counter import interacao_atual
from .auth import ensure_authenticated, clean_cache_and_login, handle_captcha_and_refresh, hard_reset_browser

def main():
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    profile_to_use = resolve_profile_dir(MAIN_USER_DATA_DIR, PROFILE_DIR)
    print(f"Usando user-data-dir: {MAIN_USER_DATA_DIR}")
    print(f"Usando profile-directory: {profile_to_use}")

    if not ensure_devtools_or_launch(profile_to_use, timeout=20):
        for tentativa in range(1, 4):
            try:
                print(f"DevTools nao encontrado em 127.0.0.1:{DEBUG_PORT}. Tentativa {tentativa}/3...")
                if KILL_CHROME_ON_RETRY:
                    close_all_chrome()
                    time.sleep(1.5)
                launch_chrome_debug(MAIN_USER_DATA_DIR, profile_to_use)
                if wait_devtools(DEBUG_PORT, timeout=20):
                    print("DevTools ativo. Conectando via Playwright...")
                    break
                print("Chrome abriu, mas sem endpoint DevTools na porta esperada.")
            except Exception as e:
                print(f"Erro ao tentar abrir o Chrome: {e}")
                time.sleep(2)
        else:
            raise RuntimeError(
                "Nao consegui subir o Chrome com Profile 5 em modo debug remoto.\n"
                "O Chrome pode estar ignorando a flag --remote-debugging-port por politica/atalho."
            )

    with sync_playwright() as p:

        time.sleep(2)

        browser, context = connect_cdp(p)

        page = None
        for pg in context.pages:
            if pg.url.startswith("https://gshow.globo.com/"):
                page = pg
                break

        if page is None:
            page = context.pages[0] if context.pages else context.new_page()
            page = safe_goto(page, SITE_URL)
            minimize_window(page)

        if BRING_TO_FRONT:
            page.bring_to_front()
        else:
            minimize_window(page)
        print("URL atual:", page.url)

        print("Abrindo pagina...")
        try:
            page = safe_goto(page, SITE_URL)
        except Exception as e:
            print(f"Erro ao navegar: {e}")
            time.sleep(random.uniform(10, 30))
            raise

        page = ensure_page_alive(page, p)
        page = ensure_authenticated(page)

        while True:

            try:
                # caso a limpeza de cache nos tenha levado direto para a tela de login,
                # preenchê-la automaticamente antes de prosseguir
                page = ensure_page_alive(page, p)
                if "authx.globoid.globo.com" in page.url or page.locator("input[name=email]").count() > 0:
                    print("Tela de login detectada, preenchendo credenciais...")
                    if not clean_cache_and_login(page):
                        raise RuntimeError("Falha no login detectado dentro do loop principal.")
                    # após login é esperado redirecionamento; vamos forçar ir novamente ao SITE_URL
                    try:
                        page = safe_goto(page, SITE_URL)
                    except Exception as e:
                        print(f"Erro ao retornar ao site após login: {e}")
                        # continuar mesmo assim
                print("Pagina carregada.")

                # pequeno atraso randômico antes de interagir para simular comportamento humano
                time.sleep(random.uniform(1.2, 3.5))
                print(f"Clicando no candidato: {CANDIDATO}...")
                if not click_candidato(page, CANDIDATO):
                    print("Aviso: nao consegui clicar no candidato (nenhum seletor funcionou).")

                screenshot_path = ARTIFACTS_DIR / "01_card_selecionado.png"
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"Screenshot salvo: {screenshot_path}")

                # tentar interagir com hCaptcha checkbox se presente
                page = handle_captcha_and_refresh(page)
                try:
                    print(f"Estado apos captcha. URL atual: {page.url}")
                except Exception:
                    pass

                wait_after_captcha = random.uniform(3, 6)
                print(f"Pos-captcha: aguardando {wait_after_captcha:.1f}s...")
                time.sleep(wait_after_captcha)
                total_interacoes = interacao_atual()
                # a cada 3 interações recria a página para evitar acúmulo de estado
                if total_interacoes % MAX_INTERATIONS_NOW == 0:
                    print("Recriando página para evitar acúmulo de estado...")
                    page = ensure_page_alive(page, p)
                    context = page.context
                    new_page = context.new_page()
                    close_other_pages(context, new_page)
                    minimize_window(new_page)

                    page = safe_goto(new_page, SITE_URL)
                    page = ensure_authenticated(page)

                # pequena espera randômica antes da proxima iteracao
                wait_next_iter = random.uniform(2.5, 6.5)
                print(f"Aguardando {wait_next_iter:.1f}s antes da proxima iteracao...")
                time.sleep(wait_next_iter)

            except KeyboardInterrupt:
                raise
            except Exception as loop_err:
                print(f"Erro no loop principal, recuperando pagina: {loop_err}")
                try:
                    page = ensure_page_alive(page, p)
                    page = safe_goto(page, SITE_URL)
                except:
                    # Se falhar completamente, tenta um reset agressivo
                    try:
                        page = ensure_page_alive(page, p)
                        page = hard_reset_browser(page)
                    except:
                        pass

        browser.close()


def run_forever():
    failure_count = 0
    while True:
        try:
            main()
            # se main retornar sem excecao, resetar contador de falhas
            failure_count = 0
        except KeyboardInterrupt:
            print("Execucao interrompida pelo usuario.")
            break
        except Exception as e:
            failure_count += 1
            print(f"Erro inesperado: {e}")
            wait = min(60, 5 * (2 ** (failure_count - 1))) + random.uniform(0, 3)
            print(
                f"Reiniciando o processo... (falhas consecutivas: {failure_count}). Aguardando {wait:.1f}s antes de tentar novamente.")
            time.sleep(wait)
            continue

