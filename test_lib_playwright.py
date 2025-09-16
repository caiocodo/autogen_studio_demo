
#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
playwright_diagnose.py
Pequeno utilitário para testar Playwright isoladamente no Windows (funciona em outros SOs também).

Uso típico:
  python playwright_diagnose.py --browser chromium --headed
  python playwright_diagnose.py --browser all
  python playwright_diagnose.py --browser chromium --executable-path "C:\Playwright\ms-playwright\chromium-1181\chrome-win\chrome.exe"

Saída:
  - Informações do ambiente
  - Verificação de caminhos padrão de navegadores do Playwright
  - Tentativa de abrir a URL escolhida (default: https://example.com) em cada navegador
  - Cria screenshots na pasta ./playwright_diagnose_artifacts

Retorno:
  - Código de saída 0 se o(s) teste(s) executarem com sucesso.
  - Código de saída diferente de 0 se algum teste falhar (detalhes no traceback).
"""
import argparse
import json
import os
import platform
import sys
import traceback
import time
from pathlib import Path

ARTIFACTS_DIR = Path.cwd() / "playwright_diagnose_artifacts"
DEFAULT_URL = "https://example.com"

def print_header(title: str):
    print("\n" + "=" * 80)
    print(title)
    print("=" * 80)

def gather_env_info():
    info = {
        "python_version": sys.version.replace("\n", " "),
        "executable": sys.executable,
        "platform": platform.platform(),
        "machine": platform.machine(),
        "cwd": str(Path.cwd()),
        "env": {
            "COMSPEC": os.environ.get("COMSPEC"),
            "TEMP": os.environ.get("TEMP"),
            "TMP": os.environ.get("TMP"),
            "PLAYWRIGHT_BROWSERS_PATH": os.environ.get("PLAYWRIGHT_BROWSERS_PATH"),
            "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH": os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH"),
            "PATH_contains_node": "node.exe" if any("node" in (p.lower()) for p in os.environ.get("PATH", "").split(os.pathsep)) else "no",
        },
    }
    return info

def list_known_browser_paths():
    """
    Mapeia caminhos comuns onde o Playwright armazena os navegadores.
    Não garante que os executáveis existam, apenas lista o que for encontrado.
    """
    locs = []

    # %LOCALAPPDATA%\ms-playwright\*
    localappdata = os.environ.get("LOCALAPPDATA")
    if localappdata:
        base = Path(localappdata) / "ms-playwright"
        if base.exists():
            locs.append(("LOCALAPPDATA/ms-playwright", str(base)))
            for d in sorted(base.iterdir()):
                if d.is_dir():
                    locs.append(("  -", str(d)))

    # venv/site-packages/playwright/.local-browsers (quando PLAYWRIGHT_BROWSERS_PATH=0)
    # Tentamos inferir a partir do local do pacote.
    try:
        import importlib.util
        spec = importlib.util.find_spec("playwright")
        if spec and spec.origin:
            base_pkg = Path(spec.origin).parent
            local_browsers = base_pkg / ".local-browsers"
            if local_browsers.exists():
                locs.append(("playwright/.local-browsers", str(local_browsers)))
                for d in sorted(local_browsers.iterdir()):
                    if d.is_dir():
                        locs.append(("  -", str(d)))
    except Exception as e:
        locs.append(("error_inspecting_playwright_pkg", str(e)))

    return locs

def try_sync(browser: str, url: str, headless: bool, executable_path: str | None, timeout: int) -> bool:
    """
    Testa com a API síncrona. Retorna True se sucesso, False se falhou.
    """
    print_header(f"[SYNC] Testando {browser} (headless={headless}, executable_path={executable_path})")
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        print("Falha ao importar playwright.sync_api:")
        traceback.print_exc()
        return False

    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as p:
            btype = getattr(p, browser)
            launch_kwargs = {"headless": headless}
            if executable_path:
                launch_kwargs["executable_path"] = executable_path

            print("Lançando navegador com:", json.dumps(launch_kwargs, indent=2, ensure_ascii=False))
            browser_obj = btype.launch(**launch_kwargs)
            page = browser_obj.new_page()
            page.set_default_timeout(timeout * 1000)
            print(f"Abrindo URL: {url}")
            page.goto(url)
            title = page.title()
            print(f"Título da página: {title!r}")

            screenshot_path = ARTIFACTS_DIR / f"screenshot_sync_{browser}.png"
            page.screenshot(path=str(screenshot_path))
            print(f"Screenshot salvo em: {screenshot_path}")

            browser_obj.close()
            print(f"[SYNC] {browser}: SUCESSO ✅")
            return True
    except Exception:
        print(f"[SYNC] {browser}: FALHOU ❌")
        traceback.print_exc()
        return False

async def try_async(browser: str, url: str, headless: bool, executable_path: str | None, timeout: int) -> bool:
    """
    Testa com a API assíncrona. Retorna True se sucesso, False se falhou.
    """
    print_header(f"[ASYNC] Testando {browser} (headless={headless}, executable_path={executable_path})")
    try:
        from playwright.async_api import async_playwright
    except Exception:
        print("Falha ao importar playwright.async_api:")
        traceback.print_exc()
        return False

    try:
        ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as p:
            btype = getattr(p, browser)
            launch_kwargs = {"headless": headless}
            if executable_path:
                launch_kwargs["executable_path"] = executable_path

            print("Lançando navegador com:", json.dumps(launch_kwargs, indent=2, ensure_ascii=False))
            browser_obj = await btype.launch(**launch_kwargs)
            page = await browser_obj.new_page()
            page.set_default_timeout(timeout * 1000)
            print(f"Abrindo URL: {url}")
            await page.goto(url)
            title = await page.title()
            print(f"Título da página: {title!r}")

            screenshot_path = ARTIFACTS_DIR / f"screenshot_async_{browser}.png"
            await page.screenshot(path=str(screenshot_path))
            print(f"Screenshot salvo em: {screenshot_path}")

            await browser_obj.close()
            print(f"[ASYNC] {browser}: SUCESSO ✅")
            return True
    except Exception:
        print(f"[ASYNC] {browser}: FALHOU ❌")
        traceback.print_exc()
        return False

def main():
    parser = argparse.ArgumentParser(description="Diagnóstico Playwright (sync/async) para Chromium, Firefox, WebKit.")
    parser.add_argument("--browser", choices=["chromium", "firefox", "webkit", "all"], default="chromium",
                        help="Qual navegador testar (default: chromium).")
    parser.add_argument("--headed", action="store_true", help="Executa com UI (headless=False).")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"URL para abrir (default: {DEFAULT_URL}).")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout em segundos para ações (default: 30).")
    parser.add_argument("--executable-path", default=None, help="Caminho completo para o executável do navegador (se precisar forçar).")
    parser.add_argument("--mode", choices=["sync", "async", "both"], default="both",
                        help="Executar testes sync, async ou ambos (default: both).")
    parser.add_argument("--list", action="store_true", help="Apenas lista caminhos comuns onde os browsers do Playwright ficam e sai.")
    args = parser.parse_args()

    headless = not args.headed
    info = gather_env_info()

    print_header("Informações do ambiente")
    print(json.dumps(info, indent=2, ensure_ascii=False))

    print_header("Caminhos comuns de navegadores do Playwright")
    for label, path in list_known_browser_paths():
        print(f"{label}: {path}")

    if args.list:
        print("\n--list solicitado: finalizando sem executar testes.")
        return 0

    browsers = ["chromium", "firefox", "webkit"] if args.browser == "all" else [args.browser]
    overall_success = True

    if args.mode in ("sync", "both"):
        for b in browsers:
            ok = try_sync(b, args.url, headless, args.executable_path, args.timeout)
            overall_success = overall_success and ok
    if args.mode in ("async", "both"):
        # Executa cada navegador em sequência (sem asyncio.run múltiplo simultâneo para simplificar)
        import asyncio
        for b in browsers:
            ok = asyncio.run(try_async(b, args.url, headless, args.executable_path, args.timeout))
            overall_success = overall_success and ok

    print_header("Resumo")
    print("Sucesso geral:", "✅" if overall_success else "❌")
    return 0 if overall_success else 2

if __name__ == "__main__":
    try:
        rc = main()
        sys.exit(rc)
    except KeyboardInterrupt:
        print("\nInterrompido pelo usuário.")
        sys.exit(130)
    except Exception:
        print("Erro inesperado:")
        traceback.print_exc()
        sys.exit(1)
