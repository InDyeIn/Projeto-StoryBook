/* =========================================================================
   Mesa: liga o mapa, o chat, os painéis e o WebSocket.
   O estado inicial chega embutido na página (window.ESTADO_MESA).
   ========================================================================= */
(function () {
  "use strict";

  const SB = window.SB;
  const { el } = SB;
  const estado = window.ESTADO_MESA;
  const SLUG = estado.room.slug;
  const API = `/api/salas/${SLUG}`;

  const permissoes = new Set(estado.me.permissions);
  const pode = (chave) => permissoes.has(chave);
  const membrosPorId = new Map(estado.members.map((m) => [m.user_id, m]));
  const fichasPorId = new Map(estado.characters.map((c) => [c.id, c]));

  /* ====================================================================
     MAPA
     ==================================================================== */
  const mapa = SB.Mapa.criar({
    viewport: document.getElementById("mapa-viewport"),
    world: document.getElementById("mapa-mundo"),
    background: document.getElementById("mapa-fundo"),
    grid: document.getElementById("mapa-grade"),
    scene: estado.scene,

    podeMover(token) {
      if (token.is_locked && !pode("token.move.any")) return false;
      if (pode("token.move.any")) return true;
      return token.owner_id === estado.me.user_id && pode("token.move.own");
    },

    onMoveEnd(tokenId, x, y, desfazer) {
      SB.run(
        () => SB.api(`${API}/tokens/${tokenId}`, { method: "PATCH", body: { x, y } }),
        { onError: desfazer },
      );
    },

    onDragLive(dados) {
      socket.send("token:dragging", dados);
    },

    onSelect(token) {
      desenharSelecionado(token);
    },

    onContext(token, evento) {
      abrirMenuToken(token, evento.clientX, evento.clientY);
    },

    onCursor(ponto) {
      socket.send("cursor", ponto);
    },

    onZoom(zoom) {
      document.getElementById("nivel-zoom").textContent = `${Math.round(zoom * 100)}%`;
    },
  });

  mapa.desenharCena(estado.scene);
  estado.tokens.forEach((token) => mapa.desenharToken(token));
  mapa.centralizar();

  document.getElementById("zoom-mais").onclick = () => mapa.ajustarZoom(1.2);
  document.getElementById("zoom-menos").onclick = () => mapa.ajustarZoom(1 / 1.2);
  document.getElementById("zoom-centro").onclick = () => mapa.centralizar();

  /* ====================================================================
     ABAS
     ==================================================================== */
  document.querySelectorAll("[data-aba]").forEach((botao) => {
    botao.addEventListener("click", () => {
      document.querySelectorAll("[data-aba]").forEach((b) => b.classList.remove("is-active"));
      document.querySelectorAll(".aba-conteudo").forEach((p) => p.classList.remove("is-active"));
      botao.classList.add("is-active");
      document.getElementById(`aba-${botao.dataset.aba}`).classList.add("is-active");
    });
  });

  /* ====================================================================
     CHAT
     ==================================================================== */
  const listaChat = document.getElementById("chat-lista");
  const entradaChat = document.getElementById("chat-entrada");
  const avisoDigitando = document.getElementById("digitando");

  function coladoNoFim() {
    return listaChat.scrollHeight - listaChat.scrollTop - listaChat.clientHeight < 90;
  }

  function desenharFaces(rolagem) {
    const caixa = el("div", { class: "rolagem-dados" });
    for (const termo of rolagem.terms || []) {
      if (!termo.dice?.length) continue;
      for (const dado of termo.dice) {
        const classes = ["face"];
        if (dado.success === true) classes.push("is-sucesso");
        if (!dado.kept) classes.push("is-descartada");
        if (dado.exploded) classes.push("is-explodida");
        caixa.append(el("span", { class: classes.join(" "), title: `d${dado.sides}` }, dado.value));
      }
    }
    return caixa;
  }

  function desenharMensagem(mensagem) {
    if (mensagem.kind === "SYSTEM") {
      return el("div", { class: "msg-sistema" }, mensagem.body);
    }

    const autor = mensagem.author;
    const linha = el("div", {
      class: `msg${mensagem.kind === "OOC" ? " msg-ooc" : ""}${mensagem.whisper_to ? " msg-sussurro" : ""}`,
      "data-id": mensagem.id,
    });

    linha.append(SB.avatar(autor, "sm"));

    const corpo = el("div", { class: "msg-corpo" });
    const cor = membrosPorId.get(autor?.id)?.color;
    corpo.append(el("div", { class: "msg-topo" },
      el("span", { class: "msg-autor", style: cor ? { color: cor } : {} },
        autor?.display_name || "Desconhecido"),
      el("span", { class: "msg-hora" }, SB.hora(mensagem.created_at)),
      mensagem.whisper_to ? el("span", { class: "badge badge-pink" }, "segredo") : null));

    if (mensagem.kind === "ROLL" && mensagem.payload) {
      const rolagem = mensagem.payload;
      const total = rolagem.is_pool
        ? `${rolagem.successes} ${rolagem.successes === 1 ? "sucesso" : "sucessos"}`
        : rolagem.total;

      const bloco = el("div", { class: "rolagem" },
        el("div", { class: "rolagem-topo" },
          el("div", {},
            rolagem.label ? el("div", { class: "rolagem-rotulo" }, rolagem.label) : null,
            el("div", { class: "rolagem-formula" }, rolagem.formula)),
          el("div", { class: "rolagem-total" }, String(total))),
        desenharFaces(rolagem));
      corpo.append(bloco);
    } else {
      corpo.append(el("div", { class: "msg-texto" }, mensagem.body));
    }

    linha.append(corpo);
    return linha;
  }

  function adicionarMensagem(mensagem) {
    if (listaChat.querySelector(`[data-id="${mensagem.id}"]`)) return;
    const perto = coladoNoFim();
    listaChat.append(desenharMensagem(mensagem));
    if (perto) listaChat.scrollTop = listaChat.scrollHeight;
  }

  estado.messages.forEach(adicionarMensagem);
  listaChat.scrollTop = listaChat.scrollHeight;

  async function enviarMensagem() {
    const texto = entradaChat.value.trim();
    if (!texto) return;
    entradaChat.value = "";
    entradaChat.style.height = "auto";

    await SB.run(async () => {
      await SB.api(`${API}/mensagens`, { method: "POST", body: { body: texto } });
    });
  }

  entradaChat.addEventListener("keydown", (evento) => {
    if (evento.key === "Enter" && !evento.shiftKey) {
      evento.preventDefault();
      enviarMensagem();
    }
  });

  entradaChat.addEventListener("input", () => {
    entradaChat.style.height = "auto";
    entradaChat.style.height = `${Math.min(entradaChat.scrollHeight, 140)}px`;
    anunciarDigitacao();
  });

  const anunciarDigitacao = SB.debounce(() => socket.send("typing"), 900);
  document.getElementById("chat-enviar").onclick = enviarMensagem;

  // Botões de rolagem rápida. As do sistema que dependem de ficha ficam na
  // própria ficha; aqui só entram as que rodam sozinhas. Se o sistema não
  // tiver nenhuma assim, oferecemos a rolagem padrão dele para a fileira não
  // ficar vazia.
  const dicas = document.getElementById("chat-dicas");
  const avulsas = (estado.system_quick_rolls || []).filter((r) => !r.formula.includes("{{"));

  const atalhos = avulsas.length
    ? avulsas.map((r) => ({ label: r.label, formula: r.formula }))
    : [
        { label: estado.room.system_name ? "Rolagem padrão" : "Padrão",
          formula: estado.system_default_roll || "d20" },
        { label: "d6", formula: "d6" },
        { label: "2d6", formula: "2d6" },
        { label: "d20", formula: "d20" },
      ];

  for (const atalho of atalhos) {
    dicas.append(el("button", {
      class: "chip", type: "button", title: atalho.formula,
      onClick: () => rolar(atalho.formula, atalho.label),
    }, atalho.label));
  }

  async function rolar(formula, rotulo, characterId) {
    await SB.run(() =>
      SB.api(`${API}/rolar`, {
        method: "POST",
        body: { formula, label: rotulo, character_id: characterId || null },
      }));
  }
  window.__rolarNaMesa = rolar;

  /* ====================================================================
     PAINEL: MEMBROS
     ==================================================================== */
  const listaMembros = document.getElementById("lista-membros");
  const online = new Set();

  function desenharMembros() {
    listaMembros.innerHTML = "";
    for (const membro of membrosPorId.values()) {
      const conectado = online.has(membro.user_id);
      const linha = el("div", { class: "item-membro" },
        SB.avatar(membro.user, "sm"),
        el("div", { class: "grow", style: { minWidth: 0 } },
          el("div", { class: "truncate", style: { fontSize: ".88rem" } },
            membro.nickname || membro.user.display_name),
          el("div", { class: "small muted" }, membro.role_label)),
        el("span", {
          class: `presence-dot ${conectado ? "presence-ONLINE" : ""}`,
          title: conectado ? "na mesa agora" : "fora",
        }));

      if (pode("room.permissions") && membro.user_id !== estado.room.owner_id) {
        linha.append(el("button", {
          class: "btn btn-ghost btn-sm", title: "Cargo e permissões",
          onClick: () => abrirPermissoes(membro),
        }, "⚙"));
      }
      listaMembros.append(linha);
    }
  }
  desenharMembros();

  /* ====================================================================
     PAINEL: FICHAS
     ==================================================================== */
  const listaFichas = document.getElementById("lista-fichas");

  function desenharFichas() {
    listaFichas.innerHTML = "";
    if (!fichasPorId.size) {
      listaFichas.append(el("div", { class: "empty" },
        el("h4", {}, "Nenhuma ficha ainda"),
        el("p", { class: "small", style: { margin: ".3rem 0 0" } },
          "Crie a sua para começar a rolar dados com ela.")));
      return;
    }

    for (const ficha of fichasPorId.values()) {
      const linha = el("div", { class: "item-membro" },
        el("span", { class: "avatar avatar-sm" },
          ficha.avatar_url ? el("img", { src: ficha.avatar_url, alt: "" }) : ficha.name[0].toUpperCase()),
        el("div", { class: "grow", style: { minWidth: 0 } },
          el("div", { class: "truncate", style: { fontSize: ".88rem" } }, ficha.name),
          el("div", { class: "small muted" },
            ficha.is_npc ? "NPC" : (ficha.owner?.display_name || ""))),
        el("button", {
          class: "btn btn-ghost btn-sm", title: "Abrir ficha",
          onClick: () => abrirFicha(ficha.id),
        }, "abrir"));

      if (pode("token.create")) {
        linha.append(el("button", {
          class: "btn btn-ghost btn-sm", title: "Colocar no mapa",
          onClick: () => SB.run(async () => {
            await SB.api(`/api/fichas/${ficha.id}/token?scene_id=${mapa.cena.id}`, { method: "POST" });
            SB.toast("Token colocado no mapa.", "ok");
          }),
        }, "🗺"));
      }
      listaFichas.append(linha);
    }
  }
  desenharFichas();

  document.getElementById("nova-ficha")?.addEventListener("click", async () => {
    const nome = prompt("Nome do personagem:");
    if (!nome?.trim()) return;
    await SB.run(async () => {
      await SB.api("/api/fichas", {
        method: "POST",
        body: { name: nome.trim(), room_id: estado.room.id },
      });
    });
  });

  let fichaAberta = null;
  async function abrirFicha(fichaId) {
    const modal = document.getElementById("modal-ficha");
    const host = document.getElementById("ficha-host");
    host.innerHTML = '<p class="muted" style="padding:2rem;text-align:center">Carregando…</p>';
    SB.openModal("modal-ficha");

    await SB.run(async () => {
      const dados = await SB.api(`/api/fichas/${fichaId}`);
      fichaAberta = SB.Sheet.montar(host, {
        character: dados.character,
        system: dados.system,
        canEdit: dados.can_edit,
        isGm: dados.is_gm,
        onRoll: (formula, rotulo, id) => rolar(formula, rotulo, id),
        onChange: (personagem) => {
          fichasPorId.set(personagem.id, personagem);
          desenharFichas();
        },
      });
    });
  }
  window.__abrirFicha = abrirFicha;

  /* ====================================================================
     PAINEL: CENA
     ==================================================================== */
  const formCena = document.getElementById("form-cena");
  if (formCena) {
    formCena.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const dados = Object.fromEntries(new FormData(formCena));
      await SB.run(async () => {
        await SB.api(`${API}/cenas/${mapa.cena.id}`, {
          method: "PATCH",
          body: {
            name: dados.name,
            grid_type: dados.grid_type,
            grid_size: Number(dados.grid_size),
            grid_color: dados.grid_color,
            background_color: dados.background_color,
            width: Number(dados.width),
            height: Number(dados.height),
            grid_visible: formCena.querySelector('[name="grid_visible"]').checked,
            snap_to_grid: formCena.querySelector('[name="snap_to_grid"]').checked,
          },
        });
        SB.toast("Cena atualizada.", "ok");
      });
    });

    document.getElementById("cena-fundo")?.addEventListener("change", async (evento) => {
      const arquivo = evento.target.files?.[0];
      if (!arquivo) return;
      const dados = new FormData();
      dados.append("file", arquivo);
      dados.append("kind", "scene");
      await SB.run(async () => {
        const enviado = await SB.api("/api/upload", { method: "POST", body: dados });
        await SB.api(`${API}/cenas/${mapa.cena.id}`, {
          method: "PATCH",
          body: { background_url: enviado.url },
        });
        SB.toast("Mapa atualizado.", "ok");
      });
    });
  }

  document.getElementById("nova-cena")?.addEventListener("click", async () => {
    const nome = prompt("Nome da nova cena:");
    if (!nome?.trim()) return;
    await SB.run(() => SB.api(`${API}/cenas`, { method: "POST", body: { name: nome.trim() } }));
  });

  document.querySelectorAll("[data-trocar-cena]").forEach((botao) => {
    botao.addEventListener("click", () => {
      SB.run(() =>
        SB.api(`${API}/cenas/${botao.dataset.trocarCena}`, {
          method: "PATCH",
          body: { is_active: true },
        }));
    });
  });

  /* ====================================================================
     TOKENS: criação e menu
     ==================================================================== */
  document.getElementById("novo-token")?.addEventListener("click", async () => {
    const nome = prompt("Nome do token:");
    if (!nome?.trim()) return;
    const passo = mapa.cena.grid_size;
    await SB.run(() =>
      SB.api(`${API}/tokens`, {
        method: "POST",
        body: {
          scene_id: mapa.cena.id,
          name: nome.trim(),
          x: passo * 2, y: passo * 2,
          width: passo, height: passo,
        },
      }));
  });

  function desenharSelecionado(token) {
    const caixa = document.getElementById("token-selecionado");
    if (!caixa) return;
    caixa.innerHTML = "";
    if (!token) {
      caixa.append(el("p", { class: "small muted", style: { margin: 0 } },
        "Clique num token para ver as opções."));
      return;
    }
    caixa.append(
      el("div", { class: "row-between", style: { marginBottom: ".6rem" } },
        el("strong", {}, token.name),
        el("span", { class: "badge" }, token.layer === "GM_ONLY" ? "camada do mestre" : "mapa")),
      el("div", { class: "row row-wrap", style: { gap: ".4rem" } },
        pode("token.reveal") ? el("button", {
          class: "btn btn-ghost btn-sm",
          onClick: () => atualizarToken(token.id, { is_visible: !token.is_visible }),
        }, token.is_visible ? "Ocultar" : "Revelar") : null,
        pode("token.reveal") ? el("button", {
          class: "btn btn-ghost btn-sm",
          onClick: () => atualizarToken(token.id, {
            layer: token.layer === "GM_ONLY" ? "TOKENS" : "GM_ONLY",
          }),
        }, token.layer === "GM_ONLY" ? "Mandar pro mapa" : "Camada do mestre") : null,
        pode("token.move.any") ? el("button", {
          class: "btn btn-ghost btn-sm",
          onClick: () => atualizarToken(token.id, { is_locked: !token.is_locked }),
        }, token.is_locked ? "Destravar" : "Travar") : null,
        token.character_id ? el("button", {
          class: "btn btn-ghost btn-sm",
          onClick: () => abrirFicha(token.character_id),
        }, "Ficha") : null,
        el("button", {
          class: "btn btn-danger btn-sm",
          onClick: () => apagarToken(token.id),
        }, "Apagar")));
  }
  desenharSelecionado(null);

  function atualizarToken(tokenId, campos) {
    SB.run(() => SB.api(`${API}/tokens/${tokenId}`, { method: "PATCH", body: campos }));
  }

  function apagarToken(tokenId) {
    if (!confirm("Apagar este token?")) return;
    SB.run(() => SB.api(`${API}/tokens/${tokenId}`, { method: "DELETE" }));
  }

  function abrirMenuToken(token, x, y) {
    mapa.selecionar(token.id);
    document.querySelector('[data-aba="mesa"]')?.click();
  }

  /* ====================================================================
     PERMISSÕES
     ==================================================================== */
  function abrirPermissoes(membro) {
    const modal = document.getElementById("modal-permissoes");
    const host = document.getElementById("permissoes-host");
    host.innerHTML = "";

    const cargo = el("select", { class: "select" });
    for (const [valor, rotulo] of Object.entries(window.ROLE_LABELS)) {
      const item = el("option", { value: valor }, rotulo);
      if (valor === membro.role) item.selected = true;
      cargo.append(item);
    }

    host.append(
      el("div", { class: "row", style: { gap: ".7rem", marginBottom: "1rem" } },
        SB.avatar(membro.user, "lg"),
        el("div", {},
          el("strong", {}, membro.user.display_name),
          el("div", { class: "small muted" }, `@${membro.user.username}`))),
      el("div", { class: "field", style: { marginBottom: "1.2rem" } },
        el("span", { class: "label" }, "Cargo"), cargo),
      el("p", { class: "small muted" },
        "Ajustes abaixo valem só para esta pessoa. Em cinza está o que o cargo já dá."));

    const overrides = { ...(membro.overrides || {}) };
    const efetivas = new Set(membro.permissions);

    for (const [grupo, chaves] of Object.entries(window.PERMISSION_GROUPS)) {
      const bloco = el("div", { class: "perm-grupo" }, el("h5", {}, grupo));
      for (const chave of chaves) {
        const caixa = el("input", { type: "checkbox" });
        caixa.checked = efetivas.has(chave);
        caixa.addEventListener("change", () => { overrides[chave] = caixa.checked; });

        bloco.append(el("label", { class: "perm-linha" },
          el("span", { class: "perm-nome" }, window.PERMISSIONS[chave]),
          caixa));
      }
      host.append(bloco);
    }

    document.getElementById("salvar-permissoes").onclick = async () => {
      await SB.run(async () => {
        await SB.api(`${API}/membros/${membro.id}`, {
          method: "PATCH",
          body: { role: cargo.value, permissions: overrides },
        });
        SB.closeModal("modal-permissoes");
        SB.toast("Permissões salvas.", "ok");
      });
    };

    SB.openModal("modal-permissoes");
  }

  /* ====================================================================
     CONVITES
     ==================================================================== */
  document.getElementById("copiar-convite")?.addEventListener("click", async (evento) => {
    const codigo = evento.currentTarget.dataset.codigo;
    try {
      await navigator.clipboard.writeText(codigo);
      SB.toast("Código copiado.", "ok");
    } catch {
      SB.toast(`Código: ${codigo}`, "info");
    }
  });

  document.getElementById("form-convite")?.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const entrada = evento.target.querySelector('[name="username"]');
    const usuario = entrada.value.trim().toLowerCase();
    if (!usuario) return;

    await SB.run(async () => {
      await SB.api(`${API}/convidar`, { method: "POST", body: { username: usuario } });
      entrada.value = "";
      SB.toast("Convite enviado no chat da pessoa.", "ok");
    });
  });

  /* ====================================================================
     WEBSOCKET
     ==================================================================== */
  const aviso = document.getElementById("aviso-conexao");
  const cursores = new Map();

  const socket = SB.connect(`/ws/mesa/${SLUG}`, {
    onOpen: () => aviso.classList.add("hidden"),
    onClose: () => aviso.classList.remove("hidden"),

    onEvent(evento, dados) {
      switch (evento) {
        case "chat:message":
          adicionarMensagem(dados);
          break;

        case "token:created":
        case "token:updated":
          // O servidor é a fonte da verdade: libera a trava de prévias.
          mapa.confirmarPosicao(dados.id);
          mapa.desenharToken(dados);
          if (mapa.selecionado?.id === dados.id) desenharSelecionado(dados);
          break;

        case "token:deleted":
          mapa.removerToken(dados.token_id);
          break;

        case "token:dragging":
          mapa.moverRemoto(dados.token_id, dados.x, dados.y, Boolean(dados.final));
          break;

        case "scene:updated":
          if (dados.id === mapa.cena.id) mapa.desenharCena(dados);
          break;

        case "scene:switched":
        case "room:deleted":
          // Trocou o mapa inteiro (ou a sala sumiu): recarregar é o mais honesto.
          window.location.reload();
          break;

        case "character:created":
        case "character:updated":
          fichasPorId.set(dados.id, dados);
          desenharFichas();
          if (fichaAberta?.character?.id === dados.id) fichaAberta.atualizar(dados);
          break;

        case "character:deleted":
          fichasPorId.delete(dados.character_id);
          desenharFichas();
          break;

        case "member:joined":
        case "member:updated":
          membrosPorId.set(dados.user_id, dados);
          desenharMembros();
          break;

        case "member:left":
          membrosPorId.delete(dados.user_id);
          online.delete(dados.user_id);
          desenharMembros();
          break;

        case "presence:list":
          online.clear();
          dados.forEach((id) => online.add(id));
          desenharMembros();
          break;

        case "presence:joined":
          online.add(dados.id);
          desenharMembros();
          break;

        case "presence:left":
          online.delete(dados.user_id);
          cursores.get(dados.user_id)?.remove();
          cursores.delete(dados.user_id);
          desenharMembros();
          break;

        case "cursor":
          desenharCursor(dados);
          break;

        case "typing":
          mostrarDigitando(dados.display_name);
          break;

        case "room:updated":
          document.getElementById("nome-da-mesa").textContent = dados.name;
          break;
      }
    },
  });

  function desenharCursor(dados) {
    const membro = membrosPorId.get(dados.user_id);
    if (!membro) return;

    let no = cursores.get(dados.user_id);
    if (!no) {
      no = el("div", { class: "cursor-remoto" },
        el("svg", { width: "14", height: "18", viewBox: "0 0 14 18",
          html: `<path d="M1 1 L1 15 L5 11 L7.5 17 L10 16 L7.5 10 L13 10 Z"
                 fill="${membro.color}" stroke="#070a14" stroke-width="1.2"/>` }),
        el("span", { style: { color: membro.color } }, membro.user.display_name));
      document.getElementById("mapa-mundo").append(no);
      cursores.set(dados.user_id, no);
    }
    no.style.left = `${dados.x}px`;
    no.style.top = `${dados.y}px`;
  }

  let timerDigitando;
  function mostrarDigitando(nome) {
    avisoDigitando.textContent = `${nome} está escrevendo…`;
    clearTimeout(timerDigitando);
    timerDigitando = setTimeout(() => { avisoDigitando.textContent = ""; }, 2600);
  }

  window.addEventListener("beforeunload", () => socket.close());
})();
