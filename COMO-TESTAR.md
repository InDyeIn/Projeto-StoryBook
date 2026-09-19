# Como testar o StoryBook

Roteiro de 15 minutos que passa por tudo que já funciona. Cada passo diz
**o que fazer** e **o que você deve ver** — se o que aparecer for diferente, é bug.

---

## O caminho mais curto: o aplicativo

Se você só quer usar, não precisa de Python nem de terminal.

1. No GitHub, **Actions** → a execução mais recente → **Artifacts** →
   `StoryBook-windows`.
2. Descompacte e abra o **StoryBook.exe**.
3. Crie a sua conta na primeira tela.

Pronto — é um programa com janela própria. Os seus dados ficam em
`%LOCALAPPDATA%\StoryBook` e sobrevivem a atualizações do executável.

Para jogar com amigos da mesma rede, abra pelo Prompt de Comando:

```powershell
StoryBook.exe --rede
```

O título da janela passa a mostrar o endereço que eles digitam no navegador.

> O `.exe` não traz a mesa de demonstração — ele começa vazio, com a sua conta.
> O roteiro abaixo usa os dados de demonstração, que só existem no modo
> desenvolvedor.

---

## Parte 0 — Colocar no ar (uma vez, modo desenvolvedor)

Você precisa de **Python 3.11 ou mais novo**. Nada além disso: o banco é SQLite
e é criado sozinho.

### Linux / macOS

```bash
cd Projeto-StoryBook

python3 -m venv .venv
.venv/bin/pip install -r requirements.txt

.venv/bin/python seed.py      # cria a mesa de demonstração
.venv/bin/python run.py       # sobe o servidor
```

### Windows

No Windows o executável fica em `Scripts`, não em `bin`.

**PowerShell ou Prompt de Comando:**

```powershell
cd Projeto-StoryBook

py -m venv .venv
.venv\Scripts\pip install -r requirements.txt

.venv\Scripts\python seed.py
.venv\Scripts\python run.py
```

**Git Bash (MINGW64):** as barras são normais, mas o caminho continua `Scripts`:

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

.venv/Scripts/python seed.py
.venv/Scripts/python run.py
```

> **Deixe a pasta do projeto num caminho sem espaços nem parênteses.** Algo como
> `C:\Users\Voce\Downloads\Projeto-StoryBook (1)\...` funciona na maior parte
> do tempo, mas atrapalha ferramentas que compilam pacotes. Renomear para
> `C:\projetos\storybook` evita dor de cabeça.

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

**Deve aparecer:** a ficha com **8 seções**, montada sobre as regras do livro:

- **ARC** — Anomalia, Realidade e Competência, com as nove opções de cada;
- **Habilidades Anômalas** — as três que a Anomalia concede;
- **Qualidades e Garantias de Qualidade** — as nove Qualidades, cada uma com
  GQs gastáveis (9 no total, distribuídas em três);
- **Situação funcional** — Burnout, Méritos e Deméritos;
- Relacionamentos, Requisições e anotações.

Experimente:
1. Escolha uma **Anomalia** no seletor.
2. Numa Qualidade, defina o **máximo** (o número da direita) e depois use
   **+** e **−** no atual. Sem máximo definido, os botões ficam travados de
   propósito — é o estado de uma ficha recém-criada.
3. Recarregue a página (F5) e reabra a ficha: tudo continua lá.

### 3b. A jogada da Agência
No chat, clique em **Jogada da Agência** (ou escreva `/r 6d4=3`).

**Deve aparecer:** seis dados de quatro faces, com os **3s** destacados, e
abaixo quanto de **Caos** aquela jogada gerou — um por dado que não saiu 3.

Role umas quantas vezes até sair **exatamente três 3s**: o cartão fica dourado
e mostra **✦ Triscendência** — sucesso sem gerar Caos nenhum.

### 6. Ações sobre um token
Clique num token no mapa e vá na aba **Mesa**.

**Deve aparecer:** o painel *Token selecionado*, com botões para **Ocultar**,
mandar para a **Camada do mestre**, **Travar**, abrir a **Ficha** e **Apagar**.

### 7. Trocar de cena
No topo direito do mapa há duas cenas: *Subsolo do Arquivo* e *Escritório
Regional*. Clique na segunda.

**Deve acontecer:** o mapa inteiro troca — e trocaria para todos os jogadores
ao mesmo tempo.

### 8. Editar a cena e enviar um mapa
Aba **Cena**: mude a grade para **Hexagonal**, ou o tamanho da célula, e clique
em **Salvar cena**. A grade muda na hora.

Agora o teste que importa: em *Imagem do mapa*, envie uma imagem **fora da
proporção da cena** (uma bem larga, por exemplo).

**Deve acontecer:** a cena se redimensiona sozinha para o tamanho da imagem em
casas, e o mapa aparece **sem achatar**. Se quiser conferir, há o seletor
*Enquadramento do fundo*:

| Opção | O que faz |
|---|---|
| Caber inteira | mostra tudo, sem distorcer (padrão) |
| Preencher | ocupa a cena toda, cortando as sobras |
| Tamanho original | 1 pixel da imagem = 1 pixel do mapa |
| Repetir lado a lado | para texturas |
| Esticar | força no retângulo — **este distorce**, e é o único que faz isso |

O botão **Ajustar a cena à imagem** refaz o cálculo a qualquer momento.

### 8b. Régua
Clique em **📏 Régua** na barra do mapa (ou segure **Shift**) e arraste.

**Deve aparecer:** uma linha com a distância em metros e em casas. Quem mais
estiver na mesa vê a sua régua enquanto você mede, com o seu nome.

Na aba **Cena** dá para mudar quanto vale uma casa, o nome da unidade e como
contar a diagonal (por casa, linha reta ou em cruz).

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

> **Pare o servidor antes.** O SQLite não gosta de ter o arquivo trocado
> embaixo de quem está usando: se você resetar com o `run.py` rodando, ele
> continua preso ao arquivo antigo e passa a responder "no such table". Feche
> com Ctrl+C, rode o reset e suba de novo.

No aplicativo (`.exe`), recomeçar do zero é apagar a pasta
`%LOCALAPPDATA%\StoryBook`.

---

## Se algo não funcionar

| Sintoma | Causa provável |
|---|---|
| `python: command not found` | Use `python3` (Linux/macOS) ou `py` (Windows). |
| `ModuleNotFoundError: fastapi` (ou `sqlalchemy`) | Você rodou com o Python do sistema, ou a instalação não terminou. Use `.venv/bin/python` (`.venv/Scripts/python` no Windows) e confira se o `pip install` terminou sem erro. |
| No Windows: `.venv/bin/python: No such file or directory` | No Windows é `.venv/Scripts/python`, não `bin`. |
| `Failed building wheel for Pillow` / `pydantic-core`, falando em **zlib**, **link.exe** ou **Visual Studio build tools** | Ver a seção abaixo. |
| `Address already in use` | Já tem servidor na 8000. Feche o outro terminal ou use `python run.py --port 8001`. |
| Página abre mas a mesa não sincroniza | O WebSocket não conectou. Aparece *"Reconectando à mesa…"* no rodapé do mapa. Em produção, quase sempre é o Nginx sem `proxy_set_header Upgrade` (veja o README). |
| Login não passa com as contas de demonstração | O seed não rodou ou o banco foi apagado. Rode `python seed.py`. |
| Tudo estranho depois de mexer no código | `python seed.py --reset` e reinicie o servidor. |

Para ver o erro de verdade, olhe o terminal onde o `run.py` está rodando — o
traceback aparece lá.

### Erro compilando Pillow ou pydantic-core

Se a instalação tentar **compilar** pacotes e reclamar de `zlib`, `link.exe` ou
*"Visual Studio build tools"*, é porque o pip não achou um pacote pronto para a
sua versão do Python e foi compilar do zero.

Isso acontecia com o `requirements.txt` antigo, que fixava versões exatas de
2024 — elas não têm pacote pronto para Python 3.14. **O arquivo atual usa faixas
de versão**, então o pip escolhe uma versão que tenha pacote pronto para o seu
Python.

Se você pegou o projeto antes dessa correção, refaça o ambiente:

```bash
# Git Bash / Linux / macOS
rm -rf .venv
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt     # no Windows
```

```powershell
# PowerShell
Remove-Item -Recurse -Force .venv
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Deve baixar tudo pronto, sem a etapa de *"Building wheel"*.

Se mesmo assim algo insistir em compilar, instale o **Python 3.13** em
<https://python.org/downloads> e crie o ambiente com ele:

```powershell
py -3.13 -m venv .venv
```

O 3.13 é a versão em que esta aplicação foi testada de ponta a ponta — todas as
bibliotecas já têm pacote pronto para ela.

---

## O que **ainda não** funciona (é esperado)

- Sem névoa de guerra no mapa.
- Sem recuperação de senha por e-mail.
- Um processo só: ao subir na VPS, use `--workers 1` (explicado no README).
- A reserva de **Caos** é mostrada por jogada, mas ainda não há um contador da
  mesa — por enquanto quem soma é o GM.
- O `.exe` é gerado só para Windows. Em Linux e macOS, rode pelo `run.py`.
