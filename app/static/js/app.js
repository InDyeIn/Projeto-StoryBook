/* =========================================================================
   StoryBook — utilidades compartilhadas por todas as páginas.
   ========================================================================= */
(function () {
  "use strict";

  const SB = (window.SB = window.SB || {});

  /* --------------------------------------------------------------------
     Avisos flutuantes
     -------------------------------------------------------------------- */
  SB.toast = function (message, kind = "info", timeout = 4200) {
    const host = document.getElementById("toasts");
    if (!host) return;

    const el = document.createElement("div");
    el.className = `toast toast-${kind}`;
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.textContent = message;
    host.appendChild(el);

    const remove = () => {
      el.classList.add("is-out");
      setTimeout(() => el.remove(), 220);
    };
    el.addEventListener("click", remove);
    setTimeout(remove, timeout);
  };

  /* --------------------------------------------------------------------
     Chamadas à API — sempre com CSRF e erro legível
     -------------------------------------------------------------------- */
  SB.api = async function (url, options = {}) {
    const opts = { credentials: "same-origin", ...options, headers: { ...(options.headers || {}) } };

    if (opts.body !== undefined && !(opts.body instanceof FormData)) {
      opts.headers["Content-Type"] = "application/json";
      if (typeof opts.body !== "string") opts.body = JSON.stringify(opts.body);
    }
    if ((opts.method || "GET").toUpperCase() !== "GET" && SB.csrf) {
      opts.headers["X-CSRF-Token"] = SB.csrf;
    }

    let response;
    try {
      response = await fetch(url, opts);
    } catch {
      throw new Error("Sem conexão com o servidor.");
    }

    if (response.status === 204) return null;

    let payload = null;
    const type = response.headers.get("content-type") || "";
    if (type.includes("application/json")) {
      payload = await response.json().catch(() => null);
    }

    if (!response.ok) {
      const detail = payload && (payload.detail || payload.error);
      throw new Error(typeof detail === "string" ? detail : `Erro ${response.status}.`);
    }
    return payload;
  };

  /** Envolve uma ação assíncrona mostrando o erro num toast. */
  SB.run = async function (fn, { onError } = {}) {
    try {
      return await fn();
    } catch (error) {
      SB.toast(error.message || "Algo deu errado.", "error");
      if (onError) onError(error);
      return undefined;
    }
  };

  /* --------------------------------------------------------------------
     Janelas modais — abertas por [data-modal-open="id"]
     -------------------------------------------------------------------- */
  SB.openModal = function (id) {
    const modal = document.getElementById(id);
    if (!modal) return;
    modal.classList.remove("hidden");
    const focusable = modal.querySelector("input, textarea, select, button");
    if (focusable) setTimeout(() => focusable.focus(), 40);
  };

  SB.closeModal = function (id) {
    const modal = document.getElementById(id);
    if (modal) modal.classList.add("hidden");
  };

  document.addEventListener("click", (event) => {
    const opener = event.target.closest("[data-modal-open]");
    if (opener) {
      event.preventDefault();
      SB.openModal(opener.dataset.modalOpen);
      return;
    }

    const closer = event.target.closest("[data-modal-close]");
    if (closer) {
      event.preventDefault();
      const modal = closer.closest(".modal-backdrop");
      if (modal) modal.classList.add("hidden");
      return;
    }

    // Clicar fora do cartão fecha
    if (event.target.classList.contains("modal-backdrop")) {
      event.target.classList.add("hidden");
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;
    document.querySelectorAll(".modal-backdrop:not(.hidden)").forEach((modal) => {
      modal.classList.add("hidden");
    });
  });

  /* --------------------------------------------------------------------
     Helpers de DOM
     -------------------------------------------------------------------- */
  SB.el = function (tag, attrs = {}, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(attrs)) {
      if (value === null || value === undefined || value === false) continue;
      if (key === "class") node.className = value;
      else if (key === "style" && typeof value === "object") Object.assign(node.style, value);
      else if (key.startsWith("on") && typeof value === "function") {
        node.addEventListener(key.slice(2).toLowerCase(), value);
      } else if (key === "html") node.innerHTML = value;
      else node.setAttribute(key, value);
    }
    for (const child of children.flat()) {
      if (child === null || child === undefined || child === false) continue;
      node.append(child instanceof Node ? child : document.createTextNode(String(child)));
    }
    return node;
  };

  SB.avatar = function (user, size = "sm") {
    const box = SB.el("span", { class: `avatar avatar-${size}` });
    if (user && user.avatar_url) {
      box.append(SB.el("img", { src: user.avatar_url, alt: "" }));
    } else {
      box.textContent = (user && (user.initials || user.display_name?.[0])) || "?";
    }
    return box;
  };

  SB.hora = function (iso) {
    if (!iso) return "";
    const date = new Date(iso);
    return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
  };

  SB.escape = function (text) {
    const div = document.createElement("div");
    div.textContent = text == null ? "" : String(text);
    return div.innerHTML;
  };

  /** Adia execuções em rajada (arrastar token, digitar em campo de ficha).
      O `.cancel()` descarta uma chamada ainda pendente — necessário quando um
      valor definitivo já foi enviado e a prévia atrasada chegaria depois dele. */
  SB.debounce = function (fn, wait = 250) {
    let timer;
    function adiada(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), wait);
    }
    adiada.cancel = () => clearTimeout(timer);
    return adiada;
  };

  /* --------------------------------------------------------------------
     WebSocket com reconexão automática
     -------------------------------------------------------------------- */
  SB.connect = function (path, handlers = {}) {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const url = `${protocol}//${location.host}${path}`;
    let socket = null;
    let attempt = 0;
    let closedByUs = false;
    let heartbeat = null;

    function open() {
      socket = new WebSocket(url);

      socket.addEventListener("open", () => {
        attempt = 0;
        handlers.onOpen?.();
        heartbeat = setInterval(() => {
          if (socket?.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ event: "ping" }));
          }
        }, 25000);
      });

      socket.addEventListener("message", (event) => {
        let parsed;
        try {
          parsed = JSON.parse(event.data);
        } catch {
          return;
        }
        if (parsed.event === "pong") return;
        handlers.onEvent?.(parsed.event, parsed.data);
      });

      socket.addEventListener("close", () => {
        clearInterval(heartbeat);
        if (closedByUs) return;
        handlers.onClose?.();
        // Espera crescente até 15s para não martelar o servidor.
        const delay = Math.min(1000 * 2 ** attempt++, 15000);
        setTimeout(open, delay);
      });

      socket.addEventListener("error", () => socket?.close());
    }

    open();

    return {
      send(event, data) {
        if (socket?.readyState === WebSocket.OPEN) {
          socket.send(JSON.stringify({ event, data }));
          return true;
        }
        return false;
      },
      close() {
        closedByUs = true;
        clearInterval(heartbeat);
        socket?.close();
      },
    };
  };

  /* --------------------------------------------------------------------
     Formulários: envia como JSON e mostra o erro na própria página
     -------------------------------------------------------------------- */
  document.addEventListener("submit", async (event) => {
    const form = event.target;
    if (!form.matches("form[data-api]")) return;

    event.preventDefault();
    const submitButton = form.querySelector('[type="submit"]');
    const errorBox = form.querySelector("[data-error]");
    const original = submitButton?.textContent;

    if (errorBox) {
      errorBox.textContent = "";
      errorBox.classList.add("hidden");
    }
    if (submitButton) {
      submitButton.disabled = true;
      submitButton.textContent = form.dataset.loading || "Enviando…";
    }

    try {
      const body = {};
      new FormData(form).forEach((value, key) => {
        if (key === "csrf_token") return;
        body[key] = value;
      });
      form.querySelectorAll('input[type="checkbox"]').forEach((input) => {
        if (input.name && input.name !== "csrf_token") body[input.name] = input.checked;
      });

      const result = await SB.api(form.action, { method: form.method || "POST", body });
      const redirect = form.dataset.redirect || result?.redirect;
      if (redirect) {
        window.location.href = redirect.replace("{slug}", result?.slug || "");
      } else {
        form.dispatchEvent(new CustomEvent("sb:success", { detail: result }));
      }
    } catch (error) {
      if (errorBox) {
        errorBox.textContent = error.message;
        errorBox.classList.remove("hidden");
      } else {
        SB.toast(error.message, "error");
      }
    } finally {
      if (submitButton) {
        submitButton.disabled = false;
        submitButton.textContent = original;
      }
    }
  });
})();
