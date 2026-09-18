"""Permissão revogada no meio da sessão: o token tem que voltar ao lugar.

Regressão de dois bugs reais:
  * a posição recusada pelo servidor ficava na tela de quem arrastou;
  * a prévia do arrasto era retransmitida sem checar permissão, então quem não
    podia mover mexia o token na tela dos outros.

Precisa do servidor rodando e dos dados do seed (`python seed.py --reset`).
"""
import sys
import os
from pathlib import Path

from playwright.sync_api import sync_playwright

CAPTURAS = Path(__file__).resolve().parent / "capturas"
CAPTURAS.mkdir(exist_ok=True)

_binario = os.environ.get("PLAYWRIGHT_CHROMIUM")
LANCAMENTO = {"executable_path": _binario} if _binario else {}

BASE = "http://127.0.0.1:8000"
OUT = str(CAPTURAS)
falhas = []


def checar(rot, ok, det=""):
    print(f"  {'OK ' if ok else 'FALHOU'}  {rot} {det}")
    if not ok:
        falhas.append(rot)


def entrar(pg, quem):
    pg.goto(f"{BASE}/entrar", wait_until="networkidle")
    pg.fill("#identifier", quem)
    pg.fill("#password", "storybook123")
    pg.click('button[type="submit"]')
    pg.wait_for_url("**/painel", timeout=10000)
    pg.goto(f"{BASE}/mesa/incidente-no-arquivo-morto", wait_until="networkidle")
    pg.wait_for_selector("#mapa-mundo", timeout=10000)
    pg.wait_for_timeout(1600)


with sync_playwright() as p:
    nav = p.chromium.launch(**LANCAMENTO)
    gm = nav.new_context(viewport={"width": 1280, "height": 860}).new_page()
    pj = nav.new_context(viewport={"width": 1280, "height": 860}).new_page()

    entrar(gm, "halima")
    entrar(pj, "ruan")

    # O token do Ruan é o que ele mesmo possui.
    alvo = pj.locator(".token").first
    token_id = alvo.get_attribute("data-token")

    print("\n1) Com permissão, o arrasto vale")
    antes = alvo.evaluate("n => [n.style.left, n.style.top]")
    cx = alvo.bounding_box()
    pj.mouse.move(cx["x"] + cx["width"] / 2, cx["y"] + cx["height"] / 2)
    pj.mouse.down(); pj.mouse.move(cx["x"] + 190, cx["y"] + 130, steps=12); pj.mouse.up()
    pj.wait_for_timeout(1400)
    depois = alvo.evaluate("n => [n.style.left, n.style.top]")
    no_gm = gm.locator(f'[data-token="{token_id}"]').evaluate("n => [n.style.left, n.style.top]")
    checar("token moveu", antes != depois, f"{antes} -> {depois}")
    checar("mestra vê a mesma posição", depois == no_gm)

    print("\n2) Mestra revoga 'mover os próprios tokens'")
    gm.click('[data-aba="mesa"]'); gm.wait_for_timeout(500)
    gm.locator("#lista-membros button:has-text('⚙')").first.click()
    gm.wait_for_selector("#modal-permissoes:not(.hidden)", timeout=6000)
    gm.locator(".perm-linha", has_text="Mover os próprios tokens").first \
      .locator("input[type=checkbox]").uncheck()
    gm.click("#salvar-permissoes")
    gm.wait_for_timeout(1500)
    checar("permissão salva", True)

    # O veredito da prévia fica em cache por 3s; espera passar.
    pj.wait_for_timeout(3500)

    print("\n3) Jogador tenta arrastar mesmo assim")
    origem = alvo.evaluate("n => [n.style.left, n.style.top]")
    cx = alvo.bounding_box()
    pj.mouse.move(cx["x"] + cx["width"] / 2, cx["y"] + cx["height"] / 2)
    pj.mouse.down(); pj.mouse.move(cx["x"] + 230, cx["y"] - 140, steps=14); pj.mouse.up()
    pj.wait_for_timeout(2200)

    final_pj = alvo.evaluate("n => [n.style.left, n.style.top]")
    final_gm = gm.locator(f'[data-token="{token_id}"]').evaluate("n => [n.style.left, n.style.top]")
    aviso = pj.locator(".toast").count()
    texto = pj.locator(".toast").first.inner_text() if aviso else ""

    pj.screenshot(path=f"{OUT}/p11-recusado.png")

    checar("token voltou ao lugar no jogador", final_pj == origem, f"{origem} -> {final_pj}")
    checar("mestra não viu o token sair do lugar", final_gm == origem, f"{final_gm}")
    checar("apareceu aviso ao jogador", aviso > 0, f"({texto!r})")

    print("\n4) Devolvendo a permissão")
    gm.locator("#lista-membros button:has-text('⚙')").first.click()
    gm.wait_for_selector("#modal-permissoes:not(.hidden)", timeout=6000)
    gm.locator(".perm-linha", has_text="Mover os próprios tokens").first \
      .locator("input[type=checkbox]").check()
    gm.click("#salvar-permissoes")
    gm.wait_for_timeout(1500)
    pj.wait_for_timeout(3500)

    cx = alvo.bounding_box()
    pj.mouse.move(cx["x"] + cx["width"] / 2, cx["y"] + cx["height"] / 2)
    pj.mouse.down(); pj.mouse.move(cx["x"] + 130, cx["y"] + 70, steps=12); pj.mouse.up()
    pj.wait_for_timeout(1500)
    voltou = alvo.evaluate("n => [n.style.left, n.style.top]")
    checar("volta a mover normalmente", voltou != origem, f"{voltou}")

    nav.close()

print("\n" + "=" * 44)
if falhas:
    print("FALHAS:", *dict.fromkeys(falhas), sep="\n  - ")
    sys.exit(1)
print("Comportamento confere com o roteiro.")
