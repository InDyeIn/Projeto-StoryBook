# Testes de ponta a ponta (navegador)

Estes testes abrem um Chromium de verdade e percorrem o site como um usuário:
criam conta, abrem mesa, arrastam token, rolam dados, editam ficha e conferem se
dois navegadores enxergam a mesma coisa em tempo real.

Diferente dos testes em `tests/`, eles precisam do **servidor rodando** e do
Playwright instalado — por isso ficam separados e não entram no `pytest` padrão.

## Como rodar

```bash
# uma vez
.venv/bin/pip install playwright
.venv/bin/playwright install chromium

# terminal 1
.venv/bin/python run.py

# terminal 2
.venv/bin/python tests/e2e/fluxo_solo.py
.venv/bin/python tests/e2e/dois_usuarios.py
```

As capturas de tela vão para `tests/e2e/capturas/` — úteis para ver o que
mudou depois de mexer no CSS.

## O que cada um cobre

| Arquivo                  | Cobre                                                       |
|--------------------------|-------------------------------------------------------------|
| `fluxo_solo.py`          | cadastro, criação de mesa, token, arrasto, chat, dados, ficha, bolinhas, cena, perfil |
| `dois_usuarios.py`       | amizade, convite pelo chat, presença, sincronia de token, chat em tempo real, revogação de permissão |
| `permissao_revogada.py`  | o token volta ao lugar quando o servidor recusa o movimento — nos dois navegadores |

`permissao_revogada.py` usa a mesa do seed; rode `python seed.py --reset` antes
se tiver bagunçado os dados.

Em `dois_usuarios.py`, o último passo tenta de propósito uma ação proibida —
o `403` que aparece no console do navegador é o teste passando, não uma falha.
