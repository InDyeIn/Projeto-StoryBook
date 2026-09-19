#!/usr/bin/env python
"""StoryBook como aplicativo de mesa.

Sobe o servidor dentro do próprio processo e abre uma janela nativa apontando
para ele. Quem usa não vê terminal, endereço nem Python — é só um programa.

    python desktop.py             # janela local, só nesta máquina
    python desktop.py --rede      # também aceita amigos na mesma rede
    python desktop.py --navegador # abre no navegador padrão em vez da janela
    python desktop.py --porta 9000

Empacotado com o PyInstaller, isto vira o StoryBook.exe. Os dados (banco,
uploads e chave de sessão) ficam em %LOCALAPPDATA%\\StoryBook, fora do
executável, para sobreviverem a uma atualização do programa.
"""

from __future__ import annotations

import argparse
import logging
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

logger = logging.getLogger("storybook.desktop")

TITULO = "StoryBook"


# ---------------------------------------------------------------------------
#  Rede
# ---------------------------------------------------------------------------


def porta_livre(preferida: int = 8000) -> int:
    """Devolve a porta preferida, ou outra livre se ela estiver ocupada."""
    for porta in (preferida, 0):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                s.bind(("127.0.0.1", porta))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("Não encontrei nenhuma porta livre.")


def endereco_na_rede() -> str | None:
    """IP desta máquina na rede local, para os amigos se conectarem."""
    try:
        # Não envia nada: só pergunta ao sistema por qual interface ele sairia.
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("10.255.255.255", 1))
            return s.getsockname()[0]
    except OSError:
        return None


def esperar_servidor(url: str, limite: float = 30.0) -> bool:
    """Espera o servidor responder antes de abrir a janela."""
    limite_em = time.monotonic() + limite
    while time.monotonic() < limite_em:
        try:
            with urllib.request.urlopen(f"{url}/api/saude", timeout=1) as r:
                if r.status == 200:
                    return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.2)
    return False


# ---------------------------------------------------------------------------
#  Servidor
# ---------------------------------------------------------------------------


class Servidor:
    """Uvicorn rodando numa thread, para a janela ficar com a principal."""

    def __init__(self, host: str, porta: int) -> None:
        import uvicorn

        from app.main import app

        self._config = uvicorn.Config(
            app,
            host=host,
            port=porta,
            log_level="warning",
            access_log=False,
        )
        self._servidor = uvicorn.Server(self._config)
        self._thread = threading.Thread(
            target=self._servidor.run, name="storybook-servidor", daemon=True
        )

    def iniciar(self) -> None:
        self._thread.start()

    def parar(self) -> None:
        self._servidor.should_exit = True
        self._thread.join(timeout=5)


# ---------------------------------------------------------------------------
#  Janela
# ---------------------------------------------------------------------------


def abrir_janela(url: str, titulo: str) -> bool:
    """Abre a janela nativa. Devolve False se o pywebview não estiver aqui."""
    try:
        import webview
    except ImportError:
        return False

    webview.create_window(
        titulo,
        url,
        width=1440,
        height=900,
        min_size=(1024, 640),
        confirm_close=True,
    )
    # gui=None deixa o pywebview escolher: no Windows usa o WebView2 do Edge.
    webview.start()
    return True


def abrir_navegador(url: str) -> None:
    import webbrowser

    webbrowser.open(url)


# ---------------------------------------------------------------------------
#  Principal
# ---------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="StoryBook — aplicativo de mesa.")
    parser.add_argument(
        "--rede",
        action="store_true",
        help="aceitar conexões de outras máquinas da rede local",
    )
    parser.add_argument(
        "--navegador",
        action="store_true",
        help="abrir no navegador padrão em vez da janela do aplicativo",
    )
    parser.add_argument("--porta", type=int, default=8000)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    porta = porta_livre(args.porta)
    host = "0.0.0.0" if args.rede else "127.0.0.1"
    url = f"http://127.0.0.1:{porta}"

    titulo = TITULO
    if args.rede:
        ip = endereco_na_rede()
        if ip:
            titulo = f"{TITULO} — amigos entram em http://{ip}:{porta}"
            print(f"\n  Seus amigos acessam:  http://{ip}:{porta}\n")

    servidor = Servidor(host, porta)
    servidor.iniciar()

    if not esperar_servidor(url):
        print("O servidor não respondeu a tempo. Veja o log acima.", file=sys.stderr)
        servidor.parar()
        return 1

    print(f"  StoryBook pronto em {url}")

    try:
        if args.navegador or not abrir_janela(url, titulo):
            if not args.navegador:
                print(
                    "  (pywebview não encontrado — abrindo no navegador padrão)",
                    file=sys.stderr,
                )
            abrir_navegador(url)
            print("  Feche esta janela para encerrar o StoryBook.")
            # Sem janela nativa, o processo precisa de algo que o segure.
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                pass
    finally:
        servidor.parar()

    return 0


if __name__ == "__main__":
    sys.exit(main())
