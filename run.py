#!/usr/bin/env python
"""Sobe o StoryBook para desenvolvimento local.

    python run.py                 # http://127.0.0.1:8000, recarrega ao salvar
    python run.py --host 0.0.0.0  # acessível na rede local (celular, outro PC)
    python run.py --port 9000
    python run.py --sem-reload    # sem recarregamento automático

Em produção use o uvicorn direto (veja o README).
"""

from __future__ import annotations

import argparse
import secrets
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent


def garantir_env() -> None:
    """Cria o .env na primeira execução, com uma SECRET_KEY própria."""
    env = BASE_DIR / ".env"
    if env.exists():
        return

    exemplo = BASE_DIR / ".env.example"
    conteudo = exemplo.read_text(encoding="utf-8") if exemplo.exists() else ""
    conteudo = conteudo.replace(
        "SECRET_KEY=troque-este-valor-em-producao",
        f"SECRET_KEY={secrets.token_urlsafe(48)}",
    )
    env.write_text(conteudo, encoding="utf-8")
    print("  .env criado com uma SECRET_KEY nova.\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Sobe o StoryBook localmente.")
    parser.add_argument("--host", default=None, help="padrão: 127.0.0.1")
    parser.add_argument("--port", type=int, default=None, help="padrão: 8000")
    parser.add_argument("--sem-reload", action="store_true", help="desliga o auto-reload")
    args = parser.parse_args()

    garantir_env()

    try:
        import uvicorn
    except ImportError:
        print("Dependências não instaladas. Rode:\n")
        print("    python -m venv .venv")
        print("    .venv/bin/pip install -r requirements.txt\n")
        return 1

    from app.config import settings

    host = args.host or settings.host
    port = args.port or settings.port

    print(f"\n  StoryBook em http://{host}:{port}")
    print(f"  Banco: {settings.database_url}")
    print("  Ctrl+C para parar.\n")

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=not args.sem_reload,
        reload_dirs=["app"],
        log_level="info",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
