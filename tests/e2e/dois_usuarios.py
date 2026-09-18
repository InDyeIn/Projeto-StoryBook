"""Dois usuários ao mesmo tempo: amizade, convite por chat e mesa em tempo real."""
import os
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CAPTURAS = Path(__file__).resolve().parent / "capturas"
CAPTURAS.mkdir(exist_ok=True)

# Em ambientes que já trazem o Chromium instalado, aponte o caminho em
# PLAYWRIGHT_CHROMIUM. Sem isso, usamos o navegador que o Playwright baixou.
_binario = os.environ.get("PLAYWRIGHT_CHROMIUM")
LANCAMENTO = {"executable_path": _binario} if _binario else {}

BASE = "http://127.0.0.1:8000"
SHOT = str(CAPTURAS)
SUF = str(int(time.time()))[-5:]
erros = []


def cadastrar(pagina, nome, usuario):
    pagina.goto(f"{BASE}/cadastro", wait_until="networkidle")
    pagina.fill("#display_name", nome)
    pagina.fill("#username", usuario)
    pagina.fill("#email", f"{usuario}@sb.com")
    pagina.fill("#password", "senhaforte123")
    pagina.click('button[type="submit"]')
    pagina.wait_for_url("**/painel", timeout=10000)


with sync_playwright() as p:
    nav = p.chromium.launch(**LANCAMENTO)

    ctx_gm = nav.new_context(viewport={"width": 1280, "height": 860})
    ctx_pj = nav.new_context(viewport={"width": 1280, "height": 860})
    gm, pj = ctx_gm.new_page(), ctx_pj.new_page()

    for nome, pagina in (("GM", gm), ("PJ", pj)):
        pagina.on("pageerror", lambda e, n=nome: erros.append(f"[{n}] {e}"))
        pagina.on("console", lambda m, n=nome: erros.append(f"[{n} console] {m.text}") if m.type == "error" else None)

    mestre, jogador = f"mestra{SUF}", f"jogador{SUF}"
    cadastrar(gm, "Mestra Halima", mestre)
    cadastrar(pj, "Jogador Ruan", jogador)
    print(f"1. duas contas criadas: @{mestre} e @{jogador}")

    # --- Amizade ---
    pj.goto(f"{BASE}/amigos", wait_until="networkidle")
    pj.fill("#busca", mestre)
    pj.wait_for_selector("#resultados .list-row", timeout=8000)
    pj.click("#resultados button:has-text('Adicionar')")
    pj.wait_for_timeout(700)
    print("2. pedido de amizade enviado pelo jogador")

    gm.goto(f"{BASE}/amigos", wait_until="networkidle")
    pendentes = gm.locator("[data-aceitar]").count()
    gm.click("[data-aceitar]")
    gm.wait_for_timeout(1200)
    amigos = gm.locator("[data-conversar]").count()
    print(f"3. mestra tinha {pendentes} pedido(s), aceitou -> {amigos} amigo(s)",
          "OK" if amigos == 1 else "FALHOU")
    if amigos != 1:
        erros.append("amizade não foi aceita")

    # --- Mestra cria a mesa ---
    gm.goto(f"{BASE}/painel", wait_until="networkidle")
    gm.click('[data-modal-open="modal-sala"]')
    gm.wait_for_selector("#modal-sala:not(.hidden)")
    gm.fill("#sala-nome", f"Incidente {SUF}")
    gm.click("#form-sala button[type=submit]")
    gm.wait_for_url("**/mesa/**", timeout=10000)
    slug = gm.url.rsplit("/", 1)[-1]
    gm.wait_for_selector("#mapa-mundo")
    gm.wait_for_timeout(1000)
    print("4. mesa criada:", slug)

    # --- Convite pelo painel da mesa ---
    gm.click('[data-aba="mesa"]')
    gm.fill("#form-convite input[name=username]", jogador)
    gm.click("#form-convite button[type=submit]")
    gm.wait_for_timeout(1200)
    print("5. convite enviado para o jogador")

    # --- Jogador recebe o convite no chat e entra ---
    pj.goto(f"{BASE}/mensagens", wait_until="networkidle")
    pj.wait_for_selector("[data-conversa]", timeout=8000)
    pj.click("[data-conversa]")
    pj.wait_for_selector(".convite", timeout=8000)
    pj.wait_for_timeout(500)
    pj.screenshot(path=f"{SHOT}/20-convite-no-chat.png")
    print("6. convite apareceu na caixa de mensagens do jogador")

    pj.click(".convite button")
    pj.wait_for_url("**/mesa/**", timeout=10000)
    pj.wait_for_selector("#mapa-mundo", timeout=10000)
    pj.wait_for_timeout(1500)
    print("7. jogador entrou na mesa pelo convite ->", pj.url.rsplit("/", 1)[-1])

    # --- Presença: a mestra deve ver o jogador conectado ---
    gm.wait_for_timeout(1200)
    membros_gm = gm.locator("#lista-membros .item-membro").count()
    print(f"8. mestra vê {membros_gm} membro(s) na mesa", "OK" if membros_gm == 2 else "FALHOU")
    if membros_gm != 2:
        erros.append(f"presença: mestra vê {membros_gm} membros, esperado 2")

    # --- Tempo real: mestra cria token, jogador deve ver ---
    gm.once("dialog", lambda d: d.accept("Anomalia 7"))
    gm.click("#novo-token")
    gm.wait_for_selector(".token", timeout=8000)
    pj.wait_for_selector(".token", timeout=8000)
    print("9. token criado pela mestra apareceu na tela do jogador (websocket)")

    # --- Tempo real: mestra move, jogador vê a posição nova ---
    token_gm = gm.locator(".token").first
    caixa = token_gm.bounding_box()
    gm.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
    gm.mouse.down()
    gm.mouse.move(caixa["x"] + 260, caixa["y"] + 190, steps=16)
    gm.mouse.up()
    gm.wait_for_timeout(1400)

    pos_gm = gm.locator(".token").first.evaluate("n => [n.style.left, n.style.top]")
    pos_pj = pj.locator(".token").first.evaluate("n => [n.style.left, n.style.top]")
    igual = pos_gm == pos_pj
    print(f"10. posição mestra {pos_gm} vs jogador {pos_pj}", "OK" if igual else "FALHOU")
    if not igual:
        erros.append(f"token dessincronizado: {pos_gm} != {pos_pj}")

    # --- Chat em tempo real ---
    gm.click('[data-aba="chat"]')
    gm.fill("#chat-entrada", "Relatório na mesa, agente.")
    gm.click("#chat-enviar")
    pj.wait_for_selector(".msg-texto:has-text('Relatório na mesa')", timeout=8000)
    print("11. mensagem da mestra chegou no chat do jogador")

    pj.fill("#chat-entrada", "/r 5d6>=4 investigar o arquivo")
    pj.click("#chat-enviar")
    gm.wait_for_selector(".rolagem", timeout=8000)
    gm.wait_for_timeout(500)
    print("12. rolagem do jogador apareceu para a mestra:",
          gm.locator(".rolagem-total").first.inner_text())

    # --- Permissões: mestra tira o direito de mover tokens do jogador ---
    gm.click('[data-aba="mesa"]')
    gm.wait_for_timeout(400)
    gm.locator("#lista-membros button:has-text('⚙')").first.click()
    gm.wait_for_selector("#modal-permissoes:not(.hidden)", timeout=6000)
    gm.wait_for_timeout(400)
    gm.screenshot(path=f"{SHOT}/21-permissoes.png")
    linha = gm.locator(".perm-linha", has_text="Mover os próprios tokens").first
    linha.locator("input[type=checkbox]").uncheck()
    gm.click("#salvar-permissoes")
    gm.wait_for_timeout(1200)
    print("13. permissão 'mover os próprios tokens' revogada do jogador")

    # O jogador tenta mover: a API deve recusar
    pj.wait_for_timeout(800)
    resposta = pj.evaluate("""async () => {
        const id = document.querySelector('.token').dataset.token;
        try {
          await SB.api(`/api/salas/%s/tokens/${id}`, { method: 'PATCH', body: { x: 999, y: 999 } });
          return 'permitiu';
        } catch (e) { return e.message; }
    }""" % slug)
    print("14. jogador tentando mover:", resposta,
          "OK" if "permitiu" not in resposta else "FALHOU")
    if "permitiu" in resposta:
        erros.append("permissão revogada não bloqueou o movimento")

    gm.screenshot(path=f"{SHOT}/22-mesa-gm.png")
    pj.screenshot(path=f"{SHOT}/23-mesa-jogador.png")

    ctx_gm.close(); ctx_pj.close(); nav.close()

print("\n=== ERROS ===")
reais = [e for e in dict.fromkeys(erros)]
if reais:
    for e in reais:
        print(" -", e)
    sys.exit(1)
print("nenhum")
