/* =========================================================================
   Renderizador de fichas.

   Recebe a definição do sistema (seções e campos) e os valores do personagem,
   e desenha a ficha inteira. Não existe nenhuma regra de Triangle Agency aqui —
   só os tipos de campo declarados em app/systems/base.py.

   Uso:
     const ficha = SB.Sheet.montar(elemento, {
       character, system, canEdit, isGm,
       onRoll: (formula, rotulo) => {...}   // opcional
     });
     ficha.atualizar(novoPersonagem);       // reaplica valores vindos do socket
   ========================================================================= */
(function () {
  "use strict";

  const SB = (window.SB = window.SB || {});
  const { el } = SB;

  function lerCaminho(objeto, caminho) {
    return caminho.split(".").reduce((acc, chave) => {
      return acc && typeof acc === "object" ? acc[chave] : undefined;
    }, objeto);
  }

  function montar(host, opcoes) {
    const estado = {
      character: opcoes.character,
      system: opcoes.system,
      canEdit: Boolean(opcoes.canEdit),
      isGm: Boolean(opcoes.isGm),
      onRoll: opcoes.onRoll || null,
      onChange: opcoes.onChange || null,
      pendente: {},
    };

    const indicador = el("span", { class: "ficha-salvando" }, "salvando…");

    /* ------------------------------------------------------------------
       Persistência: junta várias edições e manda um PATCH só.
       ------------------------------------------------------------------ */
    const enviar = SB.debounce(async () => {
      const patch = estado.pendente;
      estado.pendente = {};
      if (!Object.keys(patch).length) return;

      indicador.classList.add("is-on");
      try {
        const resposta = await SB.api(`/api/fichas/${estado.character.id}`, {
          method: "PATCH",
          body: { patch },
        });
        estado.character = resposta.character;
        estado.onChange?.(resposta.character);
      } catch (erro) {
        SB.toast(erro.message, "error");
      } finally {
        indicador.classList.remove("is-on");
      }
    }, 600);

    function definir(caminho, valor) {
      // Atualiza a cópia local para a tela responder na hora…
      const partes = caminho.split(".");
      let cursor = estado.character.data;
      for (const parte of partes.slice(0, -1)) {
        if (typeof cursor[parte] !== "object" || cursor[parte] === null) cursor[parte] = {};
        cursor = cursor[parte];
      }
      cursor[partes.at(-1)] = valor;

      // …e agenda a gravação.
      estado.pendente[caminho] = valor;
      enviar();
    }

    async function salvarMeta(campos) {
      try {
        const resposta = await SB.api(`/api/fichas/${estado.character.id}`, {
          method: "PATCH",
          body: campos,
        });
        estado.character = resposta.character;
        estado.onChange?.(resposta.character);
      } catch (erro) {
        SB.toast(erro.message, "error");
      }
    }

    function rolar(formula, rotulo) {
      if (estado.onRoll) estado.onRoll(formula, rotulo, estado.character.id);
      else SB.toast("Abra a ficha dentro da mesa para rolar dados.", "info");
    }

    /* ------------------------------------------------------------------
       Campos
       ------------------------------------------------------------------ */
    function campoTexto(campo, multilinha) {
      const valor = lerCaminho(estado.character.data, campo.key) ?? "";
      const node = el(multilinha ? "textarea" : "input", {
        type: multilinha ? null : "text",
        value: multilinha ? null : valor,
        placeholder: campo.placeholder || "",
        disabled: !podeEditar(campo),
      });
      if (multilinha) node.value = valor;
      node.addEventListener("input", () => definir(campo.key, node.value));
      return node;
    }

    function campoNumero(campo) {
      const valor = lerCaminho(estado.character.data, campo.key);
      const node = el("input", {
        type: "number",
        value: valor ?? 0,
        min: campo.min ?? null,
        max: campo.max ?? null,
        step: campo.step || 1,
        disabled: !podeEditar(campo),
      });
      node.addEventListener("input", () => {
        const numero = node.value === "" ? 0 : Number(node.value);
        if (Number.isFinite(numero)) definir(campo.key, numero);
      });
      return node;
    }

    function campoSelect(campo) {
      const valor = lerCaminho(estado.character.data, campo.key);
      const node = el("select", { disabled: !podeEditar(campo) });
      for (const opcao of campo.options || []) {
        const item = el("option", { value: opcao.value }, opcao.label);
        if (opcao.value === valor) item.selected = true;
        node.append(item);
      }
      node.addEventListener("change", () => definir(campo.key, node.value));
      return node;
    }

    function campoCheckbox(campo) {
      const valor = Boolean(lerCaminho(estado.character.data, campo.key));
      const input = el("input", { type: "checkbox", disabled: !podeEditar(campo) });
      input.checked = valor;
      input.addEventListener("change", () => definir(campo.key, input.checked));
      return el("label", { class: "check" }, input, el("span", {}, campo.hint || "Sim"));
    }

    function campoDots(campo) {
      const max = campo.max ?? 5;
      const min = campo.min ?? 0;
      const atual = Number(lerCaminho(estado.character.data, campo.key) ?? min);
      const editavel = podeEditar(campo);
      const caixa = el("div", { class: `dots${editavel ? "" : " is-locked"}` });

      for (let i = 1; i <= max; i++) {
        const bolinha = el("button", {
          type: "button",
          class: `dot${i <= atual ? " is-on" : ""}`,
          "aria-label": `${campo.label}: ${i}`,
        });
        if (editavel) {
          bolinha.addEventListener("click", () => {
            // Clicar na última bolinha acesa apaga — evita ficar preso no valor.
            const novo = i === atual ? Math.max(min, i - 1) : i;
            definir(campo.key, novo);
            [...caixa.children].forEach((outra, indice) => {
              outra.classList.toggle("is-on", indice < novo);
            });
          });
        }
        caixa.append(bolinha);
      }
      return caixa;
    }

    function campoRecurso(campo) {
      const bruto = lerCaminho(estado.character.data, campo.key) || {};
      const editavel = podeEditar(campo);
      let atual = Number(bruto.atual ?? 0);
      let maximo = Number(bruto.max ?? campo.max ?? 10);

      const preenchimento = el("div", {
        class: "recurso-fill",
        style: { background: corDaBarra(campo.key), width: "0%" },
      });
      const entradaAtual = el("input", {
        type: "number", value: atual, disabled: !editavel, "aria-label": `${campo.label} atual`,
      });
      const entradaMax = el("input", {
        type: "number", value: maximo, disabled: !editavel, "aria-label": `${campo.label} máximo`,
      });

      function pintar() {
        const razao = maximo > 0 ? Math.max(0, Math.min(1, atual / maximo)) : 0;
        preenchimento.style.width = `${razao * 100}%`;
      }
      pintar();

      function ajustar(delta) {
        atual = Math.max(0, Math.min(maximo, atual + delta));
        entradaAtual.value = atual;
        definir(`${campo.key}.atual`, atual);
        pintar();
      }

      entradaAtual.addEventListener("input", () => {
        atual = Number(entradaAtual.value || 0);
        definir(`${campo.key}.atual`, atual);
        pintar();
      });
      entradaMax.addEventListener("input", () => {
        maximo = Number(entradaMax.value || 0);
        definir(`${campo.key}.max`, maximo);
        pintar();
      });

      const linha = el("div", { class: "recurso-valores" });
      let menos = null;
      let mais = null;

      if (editavel) {
        menos = el("button", {
          type: "button", class: "recurso-passo", onClick: () => ajustar(-1),
        }, "−");
        mais = el("button", {
          type: "button", class: "recurso-passo", onClick: () => ajustar(1),
        }, "+");
        linha.append(menos);
      }
      linha.append(entradaAtual, el("span", { class: "muted" }, "/"), entradaMax);
      if (mais) linha.append(mais);

      /* Com máximo zero os botões não têm o que fazer. Em vez de ficarem
         clicáveis e silenciosos, desligam e dizem o motivo — numa ficha nova
         do Triangle Agency todas as Qualidades começam assim, e o jogador
         precisa definir o máximo antes. */
      function ajustarBotoes() {
        for (const [botao, texto] of [[menos, "Diminuir"], [mais, "Aumentar"]]) {
          if (!botao) continue;
          const travado = maximo <= 0;
          botao.disabled = travado;
          botao.title = travado ? "Defina o máximo antes (campo à direita)." : texto;
        }
      }
      ajustarBotoes();

      entradaMax.addEventListener("input", ajustarBotoes);

      const caixa = el("div", { class: "recurso" },
        linha,
        el("div", { class: "recurso-barra" }, preenchimento));

      if (editavel && maximo <= 0) {
        caixa.append(el("span", { class: "hint recurso-aviso" }, "sem máximo definido"));
      }
      return caixa;
    }

    function corDaBarra(caminho) {
      const barra = (estado.system.token_bars || []).find((b) => b.path === caminho);
      return barra ? barra.color : "var(--accent)";
    }

    function campoLista(campo) {
      const editavel = podeEditar(campo);
      const caixa = el("div", { class: "lista" });

      function redesenhar() {
        caixa.innerHTML = "";
        const linhas = lerCaminho(estado.character.data, campo.key) || [];

        if (!linhas.length && !editavel) {
          caixa.append(el("div", { class: "lista-vazia" }, "Nada por aqui."));
          return;
        }

        const tabela = el("table");
        const cabecalho = el("tr");
        for (const coluna of campo.columns || []) {
          cabecalho.append(el("th", {}, coluna.label));
        }
        if (editavel) cabecalho.append(el("th", { class: "lista-acao" }));
        tabela.append(el("thead", {}, cabecalho));

        const corpo = el("tbody");
        linhas.forEach((linha, indice) => {
          const tr = el("tr");
          for (const coluna of campo.columns || []) {
            const entrada = el("input", {
              type: coluna.type === "number" ? "number" : coluna.type === "checkbox" ? "checkbox" : "text",
              disabled: !editavel,
            });
            if (coluna.type === "checkbox") entrada.checked = Boolean(linha[coluna.key]);
            else entrada.value = linha[coluna.key] ?? "";

            entrada.addEventListener("input", () => {
              const atualizadas = [...(lerCaminho(estado.character.data, campo.key) || [])];
              atualizadas[indice] = {
                ...atualizadas[indice],
                [coluna.key]:
                  coluna.type === "checkbox" ? entrada.checked
                  : coluna.type === "number" ? Number(entrada.value || 0)
                  : entrada.value,
              };
              definir(campo.key, atualizadas);
            });
            tr.append(el("td", {}, entrada));
          }

          if (editavel) {
            tr.append(el("td", { class: "lista-acao" },
              el("button", {
                type: "button", class: "lista-remover", title: "Remover linha",
                onClick: () => {
                  const restantes = (lerCaminho(estado.character.data, campo.key) || [])
                    .filter((_, i) => i !== indice);
                  definir(campo.key, restantes);
                  redesenhar();
                },
              }, "✕")));
          }
          corpo.append(tr);
        });

        if (!linhas.length) {
          const colspan = (campo.columns?.length || 1) + (editavel ? 1 : 0);
          corpo.append(el("tr", {}, el("td", { colspan },
            el("div", { class: "lista-vazia" }, "Nenhuma linha ainda."))));
        }
        tabela.append(corpo);
        caixa.append(tabela);

        if (editavel) {
          caixa.append(el("div", { style: { padding: ".5rem" } },
            el("button", {
              type: "button", class: "btn btn-ghost btn-sm",
              onClick: () => {
                const vazia = {};
                for (const coluna of campo.columns || []) {
                  vazia[coluna.key] = coluna.type === "checkbox" ? false : coluna.type === "number" ? 0 : "";
                }
                definir(campo.key, [...(lerCaminho(estado.character.data, campo.key) || []), vazia]);
                redesenhar();
              },
            }, "+ Adicionar linha")));
        }
      }

      redesenhar();
      return caixa;
    }

    function podeEditar(campo) {
      if (!estado.canEdit) return false;
      if (campo.gm_only && !estado.isGm) return false;
      return true;
    }

    function desenharCampo(campo) {
      if (campo.gm_only && !estado.isGm) return null;

      const corpo =
        campo.type === "textarea" ? campoTexto(campo, true)
        : campo.type === "number" ? campoNumero(campo)
        : campo.type === "select" ? campoSelect(campo)
        : campo.type === "checkbox" ? campoCheckbox(campo)
        : campo.type === "dots" ? campoDots(campo)
        : campo.type === "resource" ? campoRecurso(campo)
        : campo.type === "list" ? campoLista(campo)
        : campoTexto(campo, false);

      const topo = el("div", { class: "campo-topo" },
        el("span", { class: `campo-rotulo${campo.gm_only ? " campo-gm" : ""}` },
          campo.gm_only ? `${campo.label} 🔒` : campo.label));

      if (campo.roll) {
        topo.append(el("button", {
          type: "button", class: "btn-rolar", title: `Rolar ${campo.roll.label || campo.label}`,
          onClick: () => rolar(campo.roll.formula, campo.roll.label || campo.label),
        }, "🎲"));
      }

      const node = el("div", { class: "campo", "data-span": String(campo.span || 1) }, topo, corpo);
      if (campo.hint && campo.type !== "checkbox") {
        node.append(el("span", { class: "hint" }, campo.hint));
      }
      return node;
    }

    /* ------------------------------------------------------------------
       Desenho completo
       ------------------------------------------------------------------ */
    function desenhar() {
      host.innerHTML = "";
      host.style.position = "relative";
      const raiz = el("div", { class: "ficha" });
      raiz.append(indicador);

      // Cabeçalho: retrato + nome + visibilidade
      const retrato = el("div", { class: "ficha-retrato" });
      if (estado.character.avatar_url) {
        retrato.append(el("img", { src: estado.character.avatar_url, alt: "" }));
      } else {
        retrato.textContent = (estado.character.name || "?")[0].toUpperCase();
      }
      if (estado.canEdit) {
        retrato.addEventListener("click", () => escolherRetrato());
      } else {
        retrato.style.cursor = "default";
      }

      const nome = el("input", {
        class: "ficha-nome", value: estado.character.name, disabled: !estado.canEdit,
        maxlength: 64, "aria-label": "Nome do personagem",
      });
      nome.addEventListener("change", () => salvarMeta({ name: nome.value.trim() || "Sem nome" }));

      const linhaMeta = el("div", { class: "row row-wrap", style: { gap: ".5rem" } },
        el("span", { class: "badge" }, estado.system.short_name));

      if (estado.canEdit) {
        const visibilidade = el("select", {
          class: "select", style: { width: "auto", fontSize: ".8rem", padding: ".25rem 1.8rem .25rem .5rem" },
          "aria-label": "Quem pode ver esta ficha",
        });
        for (const [valor, rotulo] of [
          ["PRIVATE", "Só eu e o mestre"],
          ["PARTY", "Toda a mesa"],
          ["PUBLIC", "Público no perfil"],
        ]) {
          const item = el("option", { value: valor }, rotulo);
          if (valor === estado.character.visibility) item.selected = true;
          visibilidade.append(item);
        }
        visibilidade.addEventListener("change", () => salvarMeta({ visibility: visibilidade.value }));
        linhaMeta.append(visibilidade);
      }

      raiz.append(el("div", { class: "ficha-topo" },
        retrato,
        el("div", { class: "grow stack", style: { gap: ".4rem" } }, nome, linhaMeta)));

      if (estado.system.status === "draft" && estado.system.draft_note) {
        raiz.append(el("div", { class: "ficha-aviso" },
          el("span", {}, "⚠️"), el("span", {}, estado.system.draft_note)));
      }

      for (const secao of estado.system.sections || []) {
        const campos = el("div", { class: "ficha-campos", style: { "--cols": String(secao.columns || 2) } });
        let visiveis = 0;
        for (const campo of secao.fields || []) {
          const node = desenharCampo(campo);
          if (node) { campos.append(node); visiveis++; }
        }
        if (!visiveis) continue;

        const topo = el("div", { class: "ficha-secao-topo" }, el("h4", {}, secao.title));
        if (secao.description) topo.append(el("p", {}, secao.description));
        raiz.append(el("section", { class: "ficha-secao" }, topo, campos));
      }

      host.append(raiz);
    }

    async function escolherRetrato() {
      const entrada = el("input", { type: "file", accept: "image/*" });
      entrada.addEventListener("change", async () => {
        const arquivo = entrada.files?.[0];
        if (!arquivo) return;
        const dados = new FormData();
        dados.append("file", arquivo);
        dados.append("kind", "token");
        await SB.run(async () => {
          const enviado = await SB.api("/api/upload", { method: "POST", body: dados });
          await salvarMeta({ avatar_url: enviado.url });
          desenhar();
        });
      });
      entrada.click();
    }

    desenhar();

    return {
      desenhar,
      get character() { return estado.character; },
      atualizar(personagem) {
        estado.character = personagem;
        desenhar();
      },
    };
  }

  SB.Sheet = { montar };
})();
