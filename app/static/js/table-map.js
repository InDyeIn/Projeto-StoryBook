/* =========================================================================
   Mapa da mesa: navegação (arrastar/zoom), grade e tokens.

   O mundo é uma <div> transformada por translate+scale; os tokens são
   elementos posicionados nele. Isso mantém tudo acessível pelo DOM (clique
   direito, foco, leitor de tela) — coisa que um <canvas> perderia.
   ========================================================================= */
(function () {
  "use strict";

  const SB = (window.SB = window.SB || {});
  const { el } = SB;

  const ZOOM_MIN = 0.25;
  const ZOOM_MAX = 3;

  function criarMapa(opcoes) {
    const viewport = opcoes.viewport;
    const mundo = opcoes.world;
    const fundo = opcoes.background;
    const grade = opcoes.grid;

    const estado = {
      scene: opcoes.scene,
      tokens: new Map(),
      nos: new Map(),
      selecionado: null,
      zoom: 1,
      panX: 0,
      panY: 0,
      podeMover: opcoes.podeMover || (() => false),
      onMoveEnd: opcoes.onMoveEnd || (() => {}),
      onDragLive: opcoes.onDragLive || (() => {}),
      onSelect: opcoes.onSelect || (() => {}),
      onContext: opcoes.onContext || (() => {}),
      onCursor: opcoes.onCursor || (() => {}),
    };

    /* ------------------------------------------------------------------
       Transformação
       ------------------------------------------------------------------ */
    function aplicarTransformacao() {
      mundo.style.transform = `translate(${estado.panX}px, ${estado.panY}px) scale(${estado.zoom})`;
      opcoes.onZoom?.(estado.zoom);
    }

    function paraCoordenadasDoMundo(clientX, clientY) {
      const caixa = viewport.getBoundingClientRect();
      return {
        x: (clientX - caixa.left - estado.panX) / estado.zoom,
        y: (clientY - caixa.top - estado.panY) / estado.zoom,
      };
    }

    function ajustarZoom(delta, clientX, clientY) {
      const anterior = estado.zoom;
      const novo = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, anterior * delta));
      if (novo === anterior) return;

      // Mantém sob o cursor o mesmo ponto do mapa antes e depois do zoom.
      const caixa = viewport.getBoundingClientRect();
      const px = clientX - caixa.left;
      const py = clientY - caixa.top;
      estado.panX = px - ((px - estado.panX) / anterior) * novo;
      estado.panY = py - ((py - estado.panY) / anterior) * novo;
      estado.zoom = novo;
      aplicarTransformacao();
    }

    function centralizar() {
      const caixa = viewport.getBoundingClientRect();
      const largura = estado.scene.width * estado.scene.grid_size;
      const altura = estado.scene.height * estado.scene.grid_size;
      estado.zoom = Math.min(1, Math.min(caixa.width / largura, caixa.height / altura) * 0.92);
      estado.panX = (caixa.width - largura * estado.zoom) / 2;
      estado.panY = (caixa.height - altura * estado.zoom) / 2;
      aplicarTransformacao();
    }

    /* ------------------------------------------------------------------
       Cena: fundo e grade
       ------------------------------------------------------------------ */
    function desenharCena(cena) {
      estado.scene = cena;
      const largura = cena.width * cena.grid_size;
      const altura = cena.height * cena.grid_size;

      mundo.style.width = `${largura}px`;
      mundo.style.height = `${altura}px`;
      mundo.style.background = cena.background_color || "#0a0d1a";

      fundo.style.backgroundImage = cena.background_url ? `url("${cena.background_url}")` : "none";

      if (!cena.grid_visible || cena.grid_type === "NONE") {
        grade.style.backgroundImage = "none";
        return;
      }

      const passo = cena.grid_size;
      const cor = cena.grid_color || "#2a3354";

      if (cena.grid_type === "HEX") {
        // Grade hexagonal aproximada por duas famílias de linhas diagonais.
        grade.style.backgroundImage = `
          linear-gradient(60deg, ${cor} 1px, transparent 1px),
          linear-gradient(-60deg, ${cor} 1px, transparent 1px),
          linear-gradient(${cor} 1px, transparent 1px)`;
        grade.style.backgroundSize = `${passo}px ${passo * 1.732}px, ${passo}px ${passo * 1.732}px, 100% ${passo * 1.732}px`;
      } else {
        grade.style.backgroundImage = `
          linear-gradient(${cor} 1px, transparent 1px),
          linear-gradient(90deg, ${cor} 1px, transparent 1px)`;
        grade.style.backgroundSize = `${passo}px ${passo}px`;
      }
      grade.style.opacity = ".55";
    }

    /* ------------------------------------------------------------------
       Tokens
       ------------------------------------------------------------------ */
    function iniciais(nome) {
      return (nome || "?")
        .split(/\s+/).filter(Boolean).slice(0, 2)
        .map((parte) => parte[0].toUpperCase()).join("");
    }

    function desenharToken(token) {
      const existente = estado.nos.get(token.id);
      const no = existente || el("div", { class: "token", "data-token": token.id });

      no.style.setProperty("--cor", token.color);
      no.style.left = `${token.x}px`;
      no.style.top = `${token.y}px`;
      no.style.width = `${token.width}px`;
      no.style.height = `${token.height}px`;
      no.style.transform = token.rotation ? `rotate(${token.rotation}deg)` : "";
      no.style.backgroundImage = token.image_url ? `url("${token.image_url}")` : "none";
      no.style.zIndex = String(10 + (token.order || 0));

      no.classList.toggle("is-locked", token.is_locked);
      no.classList.toggle("is-hidden", !token.is_visible);
      no.className = no.className.replace(/camada-\w+/g, "").trim();
      no.classList.add(`camada-${token.layer}`);
      no.classList.toggle("is-selected", estado.selecionado === token.id);

      no.innerHTML = "";
      if (!token.image_url) {
        no.append(el("span", { class: "token-iniciais" }, iniciais(token.name)));
      }
      no.append(el("span", { class: "token-nome" }, token.name));

      if (token.bars?.length) {
        const barras = el("div", { class: "token-barras" });
        for (const barra of token.bars) {
          barras.append(el("div", { class: "token-barra", title: `${barra.label}: ${barra.current}/${barra.max}` },
            el("span", { style: { width: `${barra.ratio * 100}%`, background: barra.color } })));
        }
        no.append(barras);
      }

      if (token.statuses?.length) {
        const estados = el("div", { class: "token-estados" });
        for (const estadoNome of token.statuses.slice(0, 4)) {
          estados.append(el("span", { class: "token-estado", title: estadoNome }, estadoNome[0].toUpperCase()));
        }
        no.append(estados);
      }

      if (!existente) {
        ligarArrasto(no, token.id);
        no.addEventListener("contextmenu", (evento) => {
          evento.preventDefault();
          estado.onContext(estado.tokens.get(token.id), evento);
        });
        mundo.append(no);
        estado.nos.set(token.id, no);
      }

      estado.tokens.set(token.id, token);
    }

    function removerToken(tokenId) {
      estado.nos.get(tokenId)?.remove();
      estado.nos.delete(tokenId);
      estado.tokens.delete(tokenId);
      if (estado.selecionado === tokenId) selecionar(null);
    }

    function selecionar(tokenId) {
      estado.selecionado = tokenId;
      for (const [id, no] of estado.nos) no.classList.toggle("is-selected", id === tokenId);
      estado.onSelect(tokenId ? estado.tokens.get(tokenId) : null);
    }

    function encaixar(valor) {
      if (!estado.scene.snap_to_grid) return valor;
      const passo = estado.scene.grid_size;
      return Math.round(valor / passo) * passo;
    }

    function ligarArrasto(no, tokenId) {
      no.addEventListener("pointerdown", (evento) => {
        if (evento.button !== 0) return;
        const token = estado.tokens.get(tokenId);
        if (!token) return;

        selecionar(tokenId);
        if (!estado.podeMover(token)) return;

        evento.stopPropagation();
        evento.preventDefault();
        no.setPointerCapture(evento.pointerId);
        no.classList.add("is-dragging");

        const inicio = paraCoordenadasDoMundo(evento.clientX, evento.clientY);
        const origemX = token.x;
        const origemY = token.y;
        let x = origemX;
        let y = origemY;

        const avisar = SB.debounce((px, py) => {
          estado.onDragLive({ token_id: tokenId, x: px, y: py });
        }, 45);

        function mover(e) {
          const atual = paraCoordenadasDoMundo(e.clientX, e.clientY);
          x = origemX + (atual.x - inicio.x);
          y = origemY + (atual.y - inicio.y);
          no.style.left = `${x}px`;
          no.style.top = `${y}px`;
          avisar(x, y);
        }

        function soltar(e) {
          no.releasePointerCapture(evento.pointerId);
          no.removeEventListener("pointermove", mover);
          no.removeEventListener("pointerup", soltar);
          no.removeEventListener("pointercancel", soltar);
          no.classList.remove("is-dragging");

          const finalX = Math.max(0, encaixar(x));
          const finalY = Math.max(0, encaixar(y));
          no.style.left = `${finalX}px`;
          no.style.top = `${finalY}px`;

          // A última prévia do arrasto está atrasada por debounce e chegaria
          // DEPOIS da posição final, desencaixando o token na tela dos outros.
          // Cancelamos a pendente e anunciamos a posição definitiva na hora.
          avisar.cancel();
          estado.onDragLive({ token_id: tokenId, x: finalX, y: finalY, final: true });

          if (finalX !== origemX || finalY !== origemY) {
            token.x = finalX;
            token.y = finalY;
            estado.onMoveEnd(tokenId, finalX, finalY);
          }
        }

        no.addEventListener("pointermove", mover);
        no.addEventListener("pointerup", soltar);
        no.addEventListener("pointercancel", soltar);
      });
    }

    /* ------------------------------------------------------------------
       Navegação do viewport
       ------------------------------------------------------------------ */
    viewport.addEventListener("pointerdown", (evento) => {
      // Botão esquerdo em área vazia ou botão do meio: arrasta o mapa.
      if (evento.button !== 0 && evento.button !== 1) return;
      if (evento.target.closest(".token")) return;

      selecionar(null);
      viewport.classList.add("is-panning");
      viewport.setPointerCapture(evento.pointerId);

      const inicioX = evento.clientX - estado.panX;
      const inicioY = evento.clientY - estado.panY;

      function mover(e) {
        estado.panX = e.clientX - inicioX;
        estado.panY = e.clientY - inicioY;
        aplicarTransformacao();
      }
      function soltar() {
        viewport.releasePointerCapture(evento.pointerId);
        viewport.classList.remove("is-panning");
        viewport.removeEventListener("pointermove", mover);
        viewport.removeEventListener("pointerup", soltar);
      }
      viewport.addEventListener("pointermove", mover);
      viewport.addEventListener("pointerup", soltar);
    });

    viewport.addEventListener("wheel", (evento) => {
      evento.preventDefault();
      ajustarZoom(evento.deltaY < 0 ? 1.12 : 1 / 1.12, evento.clientX, evento.clientY);
    }, { passive: false });

    // Ponteiro compartilhado com a mesa (enviado com parcimônia)
    const enviarCursor = SB.debounce((x, y) => estado.onCursor({ x, y }), 70);
    viewport.addEventListener("pointermove", (evento) => {
      const ponto = paraCoordenadasDoMundo(evento.clientX, evento.clientY);
      enviarCursor(Math.round(ponto.x), Math.round(ponto.y));
    });

    return {
      desenharCena,
      desenharToken,
      removerToken,
      selecionar,
      centralizar,
      ajustarZoom: (fator) => {
        const caixa = viewport.getBoundingClientRect();
        ajustarZoom(fator, caixa.left + caixa.width / 2, caixa.top + caixa.height / 2);
      },
      confirmarPosicao(tokenId) {
        const no = estado.nos.get(tokenId);
        if (no) no.dataset.confirmado = "";
      },
      limparTokens() {
        for (const no of estado.nos.values()) no.remove();
        estado.nos.clear();
        estado.tokens.clear();
        estado.selecionado = null;
      },
      moverRemoto(tokenId, x, y, definitiva = false) {
        const no = estado.nos.get(tokenId);
        if (!no || no.classList.contains("is-dragging")) return;
        // Prévias que cheguem fora de ordem depois da posição confirmada
        // são descartadas — a confirmação manda.
        if (!definitiva && no.dataset.confirmado === "1") return;
        no.dataset.confirmado = definitiva ? "1" : "";
        no.style.left = `${x}px`;
        no.style.top = `${y}px`;
      },
      get selecionado() { return estado.selecionado ? estado.tokens.get(estado.selecionado) : null; },
      get cena() { return estado.scene; },
      get zoom() { return estado.zoom; },
      paraCoordenadasDoMundo,
    };
  }

  SB.Mapa = { criar: criarMapa };
})();
