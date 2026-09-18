"""Fluxo completo de um usuário: conta, mesa, token, dados, ficha e perfil."""
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

SUF = str(int(time.time()))[-5:]

BASE = "http://127.0.0.1:8000"
SHOT = str(CAPTURAS)
erros = []

with sync_playwright() as p:
    navegador = p.chromium.launch(**LANCAMENTO)
    ctx = navegador.new_context(viewport={"width": 1440, "height": 900})
    pagina = ctx.new_page()
    pagina.on("console", lambda m: erros.append(f"[console.{m.type}] {m.text}") if m.type == "error" else None)
    pagina.on("pageerror", lambda e: erros.append(f"[pageerror] {e}"))

    # 1) Landing
    pagina.goto(BASE, wait_until="networkidle")
    pagina.screenshot(path=f"{SHOT}/01-landing.png", full_page=False)
    print("1. landing:", pagina.title())

    # 2) Cadastro de um segundo usuário (jogador)
    pagina.goto(f"{BASE}/cadastro", wait_until="networkidle")
    pagina.fill("#display_name", "Agente Vieira")
    pagina.fill("#username", f"vieira{SUF}")
    pagina.fill("#email", f"vieira{SUF}@sb.com")
    pagina.fill("#password", "senhaforte123")
    pagina.screenshot(path=f"{SHOT}/02-cadastro.png")
    pagina.click('button[type="submit"]')
    pagina.wait_for_url("**/painel", timeout=10000)
    print("2. cadastro -> painel ok")

    # 3) Criar mesa pelo modal
    pagina.click('[data-modal-open="modal-sala"]')
    pagina.wait_for_selector("#modal-sala:not(.hidden)")
    pagina.fill("#sala-nome", f"A Mesa do Vieira {SUF}")
    pagina.fill("#sala-desc", "Testando o tabletop de verdade.")
    pagina.screenshot(path=f"{SHOT}/03-criar-sala.png")
    pagina.click("#form-sala button[type=submit]")
    pagina.wait_for_url("**/mesa/**", timeout=10000)
    print("3. sala criada ->", pagina.url)

    # 4) Mesa carregada
    pagina.wait_for_selector("#mapa-mundo", timeout=10000)
    pagina.wait_for_timeout(1200)
    pagina.screenshot(path=f"{SHOT}/04-mesa.png")
    print("4. mesa: zoom =", pagina.inner_text("#nivel-zoom"))

    # 5) Criar um token (prompt nativo)
    pagina.once("dialog", lambda d: d.accept("Sentinela"))
    pagina.click("#novo-token")
    pagina.wait_for_selector(".token", timeout=8000)
    print("5. token criado:", pagina.locator(".token").count())

    # 6) Arrastar o token
    token = pagina.locator(".token").first
    caixa = token.bounding_box()
    antes = (token.evaluate("n => n.style.left"), token.evaluate("n => n.style.top"))
    pagina.mouse.move(caixa["x"] + caixa["width"] / 2, caixa["y"] + caixa["height"] / 2)
    pagina.mouse.down()
    pagina.mouse.move(caixa["x"] + 220, caixa["y"] + 150, steps=14)
    pagina.mouse.up()
    pagina.wait_for_timeout(900)
    depois = (token.evaluate("n => n.style.left"), token.evaluate("n => n.style.top"))
    print(f"6. arrasto: {antes} -> {depois}", "OK" if antes != depois else "FALHOU")
    if antes == depois:
        erros.append("token não se moveu ao arrastar")

    # 7) Chat + rolagem de dados
    pagina.fill("#chat-entrada", "Todos a postos.")
    pagina.click("#chat-enviar")
    pagina.wait_for_timeout(500)
    pagina.fill("#chat-entrada", "/r 4d6kh3 iniciativa")
    pagina.click("#chat-enviar")
    pagina.wait_for_selector(".rolagem", timeout=8000)
    pagina.wait_for_timeout(400)
    print("7. chat:", pagina.locator(".msg").count(), "mensagens |",
          pagina.locator(".rolagem").count(), "rolagem(ns)")
    print("   resultado:", pagina.locator(".rolagem-total").first.inner_text())

    # 8) Ficha: criar e abrir
    pagina.click('[data-aba="fichas"]')
    pagina.once("dialog", lambda d: d.accept("Vieira, Agente"))
    pagina.click("#nova-ficha")
    pagina.wait_for_timeout(1200)
    pagina.click("#lista-fichas button:has-text('abrir')")
    pagina.wait_for_selector(".ficha-secao", timeout=8000)
    pagina.wait_for_timeout(600)
    pagina.screenshot(path=f"{SHOT}/05-ficha.png")
    print("8. ficha:", pagina.locator(".ficha-secao").count(), "seções |",
          pagina.locator(".campo").count(), "campos |",
          pagina.locator(".dot").count(), "bolinhas")

    # 9) Editar a ficha: clicar na 5a bolinha de Burocracia
    dots = pagina.locator(".dots").first
    dots.locator(".dot").nth(4).click()
    pagina.wait_for_timeout(1200)
    acesas = dots.locator(".dot.is-on").count()
    print("9. bolinhas acesas após clicar na 5a:", acesas, "OK" if acesas == 5 else "FALHOU")
    if acesas != 5:
        erros.append(f"dots: esperava 5 acesas, veio {acesas}")

    # 10) Rolar a partir da ficha
    pagina.locator(".btn-rolar").first.click()
    pagina.wait_for_timeout(1200)
    pagina.screenshot(path=f"{SHOT}/06-ficha-editada.png")
    pagina.click("#modal-ficha [data-modal-close]")
    pagina.wait_for_timeout(400)
    total_rolagens = pagina.locator(".rolagem").count()
    print("10. rolagens no chat:", total_rolagens)

    # 11) Aba Mesa (membros/permissões)
    pagina.click('[data-aba="mesa"]')
    pagina.wait_for_timeout(400)
    pagina.screenshot(path=f"{SHOT}/07-aba-mesa.png")
    print("11. membros listados:", pagina.locator("#lista-membros .item-membro").count())

    # 12) Aba Cena
    pagina.click('[data-aba="cena"]')
    pagina.wait_for_timeout(300)
    pagina.fill("#cena-nome", "Escritório Central")
    pagina.select_option("#cena-grade", "HEX")
    pagina.click("#form-cena button[type=submit]")
    pagina.wait_for_timeout(1000)
    pagina.screenshot(path=f"{SHOT}/08-cena-hex.png")
    print("12. cena salva (grade hexagonal)")

    # 13) Perfil e configurações
    pagina.goto(f"{BASE}/configuracoes", wait_until="networkidle")
    pagina.fill("#tagline", "Arquivo e Documentação, terceiro turno.")
    pagina.fill("#bio", "Jogo desde 2014. Prefiro mesas de investigação.\nDisponível terças e quintas.")
    pagina.click("#add-bloco")
    pagina.wait_for_timeout(300)
    campos = pagina.locator(".bloco-vitrine input")
    campos.nth(0).fill("Links")
    campos.nth(1).fill("Meu blog")
    campos.nth(2).fill("https://exemplo.com")
    pagina.screenshot(path=f"{SHOT}/09-configuracoes.png")
    pagina.click('#form-perfil button[type="submit"]')
    pagina.wait_for_url(f"**/u/vieira{SUF}", timeout=10000)
    pagina.wait_for_timeout(600)
    pagina.screenshot(path=f"{SHOT}/10-perfil.png", full_page=True)
    print("13. perfil salvo:", pagina.inner_text(".perfil-nome"))

    # 14) Painel final
    pagina.goto(f"{BASE}/painel", wait_until="networkidle")
    pagina.wait_for_timeout(500)
    pagina.screenshot(path=f"{SHOT}/11-painel.png")
    print("14. painel: salas =", pagina.locator(".sala-card").count())

    ctx.close()
    navegador.close()

print("\n=== ERROS DE JAVASCRIPT ===")
if erros:
    for e in dict.fromkeys(erros):
        print(" -", e)
    sys.exit(1)
print("nenhum")
