# Como testar o StoryBook

Roteiro de 15 minutos que passa por tudo que já funciona. Cada passo diz
**o que fazer** e **o que você deve ver** — se o que aparecer for diferente, é bug.

---

## Parte 0 — Colocar no ar (uma vez)

Você precisa de **Python 3.11+**. Nada mais: o banco é SQLite, criado sozinho.

```bash
cd Projeto-StoryBook

python -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python seed.py      # cria a mesa de demonstração
.venv/bin/python run.py       # sobe o servidor
```

No Windows, troque `.venv/bin/` por `.venv\Scripts\`.

O terminal deve mostrar:

```
  StoryBook em http://127.0.0.1:8000
  Banco: sqlite:///./storybook.db
  Ctrl+C para parar.

INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Application startup complete.
```

**Deixe esse terminal aberto** — é o servidor. Abra o navegador em
<http://127.0.0.1:8000>.

Contas prontas (senha de todas: **`storybook123`**):

| Usuário  | Papel   |
|----------|---------|
| `halima` | mestra  |
| `ruan`   | jogador |
| `dani`   | jogadora|

> Deu errado? Veja **Se algo não funcionar**, no fim.

---

## Parte 1 — A mesa, como mestre

### 1. Entrar
Clique em **Entrar**, use `halima` / `storybook123`.

**Deve aparecer:** o painel, com o cartão da mesa *Incidente no Arquivo Morto*
e três fichas na coluna da direita.

### 2. Abrir a mesa
Clique no cartão da mesa.

**Deve aparecer:** o tabletop, com a grade quadrada e **3 tokens**. O token
tracejado e apagado é o do mestre — só você o vê. No topo à direita fica o
**código de convite** (8 letras).

Experimente navegar:
- **Arrastar o fundo** move o mapa.
- **Roda do mouse** dá zoom (o canto inferior esquerdo mostra a porcentagem).
- O botão **⌖** recentraliza.

### 3. Mover um token
Arraste o token *Teixeira* para outro lugar e solte.

**Deve acontecer:** ele **encaixa na grade** ao soltar, não fica no meio de uma
célula. A posição é salva na hora — recarregue a página (F5) e ele continua lá.

### 4. Rolar dados
No chat da direita, escreva e envie:

```
/r 4d6kh3 iniciativa
```

**Deve aparecer:** um cartão de rolagem com **4 dados**, um deles riscado (o
menor, descartado por `kh3`), o rótulo *iniciativa* e o total.

Vale testar também:
- `/r 2d6+3` — soma com modificador
- `/r 6d6>=5` — conta sucessos em vez de somar
- `/r banana` — deve dar erro legível, não quebrar nada

Os botões abaixo do campo (**d6**, **2d6**, **d20**) rolam com um clique.

### 5. Abrir e editar uma ficha
Aba **Fichas** → botão **abrir** na ficha do *Agente Teixeira*.

**Deve aparecer:** a ficha com **7 seções** e um aviso amarelo no topo dizendo
que a ficha do Triangle Agency ainda é provisória (isso é proposital — ver
o fim deste arquivo).

Agora:
1. Clique na **6ª bolinha** de *Burocracia*. Ela acende junto com as anteriores.
2. Clique no **🎲** ao lado de *Burocracia*.

**Deve acontecer:** a rolagem no chat sai como `6d6>=4` — ou seja, ela **leu o
valor que você acabou de mudar**. Esse é o ponto principal do sistema de fichas.

Também dá para mexer nas trilhas (**Realidade**, **Confiança**) com os botões
**−** e **+**, e adicionar linhas em *Equipamento*.

### 6. Ações sobre um token
Clique num token no mapa e vá na aba **Mesa**.

**Deve aparecer:** o painel *Token selecionado*, com botões para **Ocultar**,
mandar para a **Camada do mestre**, **Travar**, abrir a **Ficha** e **Apagar**.

### 7. Trocar de cena
No topo direito do mapa há duas cenas: *Subsolo do Arquivo* e *Escritório
Regional*. Clique na segunda.

**Deve acontecer:** o mapa inteiro troca — e trocaria para todos os jogadores
ao mesmo tempo.

### 8. Editar a cena
Aba **Cena**: mude a grade para **Hexagonal**, ou o tamanho da célula, e clique
em **Salvar cena**.

**Deve acontecer:** a grade muda na hora. Dá para enviar uma imagem de mapa em
*Imagem do mapa* — ela aparece para todo mundo assim que o upload termina.

---

## Parte 2 — Duas pessoas ao mesmo tempo

É aqui que dá para ver o tempo real. Você não precisa de dois computadores:
**abra uma janela anônima** (Ctrl+Shift+N) e deixe as duas lado a lado.

### 9. Entrar como jogador
Na janela anônima, entre com `ruan` / `storybook123` e abra a mesma mesa.

**Deve acontecer:** o jogador vê **2 tokens**, não 3. O token da camada do
mestre **não é enviado** para ele — não está só escondido no CSS; o servidor
nem manda.

Na janela da mestra, aba **Mesa**: os três membros aparecem, e quem está com a
mesa aberta agora tem a bolinha verde.

### 10. Ver a sincronia
Com as duas janelas visíveis:

| Faça numa janela                  | Deve acontecer na outra                    |
|-----------------------------------|--------------------------------------------|
| Arrastar um token                 | ele se move junto, e para no mesmo lugar   |
| Mandar mensagem no chat           | chega na hora                              |
| Rolar dados                       | o cartão aparece nas duas                  |
| Mexer o mouse sobre o mapa        | aparece o ponteiro com o nome da pessoa    |
| Mudar *Realidade* na ficha        | a barrinha sob o token muda nas duas       |

### 11. Mexer nas permissões
Na janela da **mestra**, aba **Mesa** → clique na **⚙** ao lado de *Ruan*.

**Deve aparecer:** o painel de cargo e permissões, com **18 permissões** em 5
grupos. As já marcadas são as que o cargo *Jogador* dá.

Faça o teste que importa:
1. **Desmarque** *Mover os próprios tokens*.
2. **Salvar**.
3. Na janela do jogador, tente arrastar o token dele.

**Deve acontecer:** o token **volta sozinho para o lugar** e aparece um aviso
*"Você não pode mover este token."* Na janela da mestra ele nem se mexeu. A
checagem é no servidor — não adianta mexer no navegador.

> O servidor guarda o veredito por ~3 segundos para não consultar o banco a
> cada quadro do arrasto. Se você revogar e tentar arrastar **no mesmo
> instante**, o token pode piscar na tela dos outros antes de voltar. Espere
> uns segundos entre revogar e testar.

Marque de volta e confirme que ele volta a mover.

Vale testar também: dar *Mover qualquer token* para o jogador, ou mudar o cargo
dele para **Co-mestre** e ver o que aparece a mais.

---

## Parte 3 — A parte social

### 12. Convite pelo chat
Na janela da mestra, aba **Mesa** → campo **Convidar** → escreva `dani` →
**Convidar**.

Abra outra janela anônima, entre como `dani` e vá em **Mensagens**.

**Deve aparecer:** um cartão de convite na conversa, com o nome da mesa e um
botão **Entrar na mesa**. Clicando, ela entra direto — sem copiar código.

O código de 8 letras no topo da mesa também funciona: **Painel** → *Entrar com
código*.

### 13. Mensagens diretas
Em **Mensagens**, escreva algo para a mestra e veja chegar na outra janela na
hora. O botão **Convidar para mesa** manda o convite dentro da conversa.

### 14. Amigos
Em **Amigos**, busque por um nome. Peça amizade, aceite na outra janela.
Pedidos cruzados (os dois pedem) viram amizade na hora.

### 15. Perfil
Clique no seu nome no topo → **Editar perfil**.

Teste: trocar a **foto** e a **capa** (clique nas áreas), mudar a **cor de
destaque** e adicionar um **bloco de vitrine** (ex.: tipo *Links*, título
"Onde me achar", item "Meu blog" → `https://…`).

**Deve acontecer:** ao salvar, o perfil aparece com a capa tingida na sua cor e
o bloco na lateral — a ideia do perfil do Steam.

---

## Parte 4 — Testes automatizados

Não precisam do servidor rodando:

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

**Deve terminar com:** `110 passed`.

Há ainda testes que abrem um Chromium de verdade e refazem boa parte deste
roteiro sozinhos — inclusive com dois navegadores simultâneos:

```bash
.venv/bin/playwright install chromium   # uma vez

# com o servidor rodando em outro terminal:
.venv/bin/python tests/e2e/fluxo_solo.py
.venv/bin/python tests/e2e/dois_usuarios.py
```

Em `dois_usuarios.py`, o último passo tenta de propósito uma ação proibida — o
`403` no console é o teste passando.

---

## Recomeçar do zero

```bash
.venv/bin/python seed.py --reset
```

Apaga o banco e recria a mesa de demonstração. Útil depois de bagunçar tudo.

---

## Se algo não funcionar

| Sintoma | Causa provável |
|---|---|
| `python: command not found` | Use `python3`. |
| `ModuleNotFoundError: fastapi` | Você rodou com o Python do sistema. Use `.venv/bin/python`. |
| `Address already in use` | Já tem servidor na 8000. Feche o outro terminal ou use `python run.py --port 8001`. |
| Página abre mas a mesa não sincroniza | O WebSocket não conectou. Aparece *"Reconectando à mesa…"* no rodapé do mapa. Em produção, quase sempre é o Nginx sem `proxy_set_header Upgrade` (veja o README). |
| Login não passa com as contas de demonstração | O seed não rodou ou o banco foi apagado. Rode `python seed.py`. |
| Tudo estranho depois de mexer no código | `python seed.py --reset` e reinicie o servidor. |

Para ver o erro de verdade, olhe o terminal onde o `run.py` está rodando — o
traceback aparece lá.

---

## O que **ainda não** funciona (é esperado)

- **A ficha do Triangle Agency é provisória.** Foi escrita antes do PDF do livro
  ser anexado. A mecânica funciona (pool de d6, competências, trilhas, anomalia),
  mas os **nomes e números são marcadores meus** e precisam ser conferidos com o
  livro. É por isso que aparece o aviso amarelo no topo da ficha. O que conferir
  está listado no topo de `app/systems/triangle_agency.py`.
- Sem névoa de guerra e sem medição de distância no mapa.
- Sem recuperação de senha por e-mail.
- Um processo só: ao subir na VPS, use `--workers 1` (explicado no README).
