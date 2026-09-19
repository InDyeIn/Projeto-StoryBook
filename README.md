# StoryBook (SB)

Mesa virtual (VTT) e rede social para RPG, em uma única aplicação Python.

Tabletop com mapa e tokens, fichas que se adaptam ao sistema, chat com rolagem
de dados, perfis customizáveis e mensagens diretas — tudo no mesmo lugar, tudo
rodando na sua máquina ou na sua VPS.

---

## Como usar

Há duas formas, e elas não competem:

| | Para quê |
|---|---|
| **StoryBook.exe** | Baixar e abrir no Windows. Sem terminal, sem instalar Python. É um programa. |
| **Servidor** | Rodar na VPS para a mesa acessar de qualquer lugar, a qualquer hora. |

O código é o mesmo nos dois casos — o executável só embrulha o servidor numa
janela e guarda os dados na pasta do usuário.

---

## Aplicativo para Windows

### Baixar

O executável é gerado automaticamente a cada push. No GitHub: **Actions** → a
execução mais recente → **Artifacts** → `StoryBook-windows`. Descompacte e
abra o `StoryBook.exe`.

Para virar um release permanente:

```bash
git tag v0.1.0
git push --tags
```

### Gerar você mesmo (no Windows)

```powershell
py -m venv .venv
.venv\Scripts\pip install -r requirements-desktop.txt
.venv\Scripts\pyinstaller storybook.spec
```

O resultado é `dist\StoryBook.exe`, um arquivo só (~40 MB).

> O PyInstaller **não** faz compilação cruzada: só o Windows gera o `.exe`.
> Por isso existe o workflow em `.github/workflows/build-windows.yml`.

### Rodando o aplicativo

Abrir o `.exe` sobe o servidor por dentro e abre uma janela do programa. Na
primeira vez, crie a sua conta.

| Modo | Comando |
|---|---|
| Só nesta máquina | abrir o `.exe` normalmente |
| Amigos na mesma rede (Wi-Fi/LAN) | `StoryBook.exe --rede` — o título da janela mostra o endereço que eles digitam |
| Abrir no navegador em vez da janela | `StoryBook.exe --navegador` |

Os dados ficam em `%LOCALAPPDATA%\StoryBook`: banco, uploads e a chave de
sessão. Ficam **fora** do executável, então atualizar o programa não apaga as
suas mesas. Para começar do zero, apague essa pasta.

> Para jogar pela internet (não só na rede local), o caminho é a VPS — veja
> **Subindo na VPS**. O `--rede` sozinho só alcança quem está na mesma casa.

---

## Rodando local em 3 comandos (desenvolvimento)

Requisito: **Python 3.11 ou superior**. Nada além disso — o banco padrão é
SQLite, então não precisa de Docker nem de servidor de banco.

Testado em Python 3.11 e 3.13. No Windows, os comandos usam `.venv\Scripts\`
em vez de `.venv/bin/` — veja [COMO-TESTAR.md](COMO-TESTAR.md).

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python run.py
```

> As dependências usam **faixas** de versão (`>=`), não versões fixas, para que
> o pip escolha pacotes já compilados para a sua versão do Python. Para
> congelar versões na VPS: `pip freeze > requirements.lock.txt`.

Abra **http://127.0.0.1:8000**. O `run.py` cria o `.env` na primeira execução,
já com uma `SECRET_KEY` própria.

> Primeira vez? **[COMO-TESTAR.md](COMO-TESTAR.md)** tem um roteiro de 15
> minutos que passa por tudo — mapa, dados, fichas, permissões e tempo real
> com dois navegadores.

### Dados de demonstração (recomendado na primeira vez)

```bash
.venv/bin/python seed.py
```

Cria uma mesa pronta com três agentes, fichas preenchidas, tokens no mapa e uma
conversa. Contas (senha de todas: **`storybook123`**):

| Usuário   | Papel    |
|-----------|----------|
| `halima`  | mestra   |
| `ruan`    | jogador  |
| `dani`    | jogadora |

Entre como `halima`, abra a mesa **Incidente no Arquivo Morto** e você já cai no
tabletop com tudo montado. Para recomeçar do zero: `python seed.py --reset`.

### Testando com outra pessoa na mesma rede

```bash
.venv/bin/python run.py --host 0.0.0.0
```

Os outros acessam `http://SEU-IP-LOCAL:8000`. Dá para abrir duas janelas
anônimas no mesmo PC e entrar com contas diferentes para ver o tempo real
funcionando.

---

## O que já está pronto

### Mesa (tabletop)
- Mapa com **arrastar e zoom**, grade quadrada ou hexagonal, tamanho e cores
  configuráveis, imagem de fundo enviada pelo mestre.
- **Tokens** arrastáveis com encaixe na grade, imagem, cor, nome, marcadores de
  estado e barras de recurso que leem a ficha vinculada.
- **Camada do mestre**: tokens que só quem tem `token.reveal` enxerga — o
  servidor nem envia esses tokens para os outros jogadores.
- **Várias cenas** por mesa, com troca em um clique para todo mundo.
- **Tempo real** por WebSocket: movimento de token, chat, fichas, presença de
  quem está com a mesa aberta e até o ponteiro do mouse dos outros.

### Fichas
- A ficha **não é código**: ela nasce de uma definição de dados
  (`app/systems/`). Adicionar um sistema novo é criar um arquivo — nenhuma tela
  precisa mudar.
- Tipos de campo prontos: texto, texto longo, número, seleção, caixa de marcar,
  trilha de bolinhas, recurso (atual/máximo com barra), lista de linhas e campo
  calculado.
- Campos marcados como `gm_only` são invisíveis e **imutáveis** para jogadores —
  a checagem é no servidor, não só na tela.
- Edição por *patch* de caminho: duas pessoas editando a mesma ficha não
  sobrescrevem o trabalho uma da outra.
- Botão de dado ao lado do campo, com a fórmula do sistema já resolvida.

### Dados
Notação completa, no chat ou na ficha:

| Fórmula     | O que faz                                           |
|-------------|-----------------------------------------------------|
| `d20`       | um dado de vinte                                    |
| `2d6+3`     | soma com modificador                                |
| `4d6kh3`    | rola quatro, mantém os três maiores (`kl` = menores)|
| `6d6>=5`    | pool contando sucessos                              |
| `2d6!`      | dado explosivo                                      |
| `1d20+2d4-1`| vários termos                                       |

No chat: `/r 4d6kh3 iniciativa`. O alvo do pool respeita a dificuldade que o
mestre escolheu ao criar a mesa.

### Permissões
Dezoito permissões granulares (`app/permissions.py`), com padrão por cargo
(Mestre, Co-mestre, Jogador, Espectador) e **ajuste fino por jogador**. Dá para
soltar o mapa inteiro para um jogador e travar os tokens de outro sem inventar
cargos novos. O mestre nunca consegue se trancar para fora da própria mesa.

### Social
- Perfil customizável: foto, capa, cor de destaque, frase, descrição, pronomes,
  localização e **blocos de vitrine** montados por você (links, horários,
  sistemas favoritos) — a ideia de perfil do Steam.
- Amizades com pedido e aceite; pedidos cruzados viram amizade na hora.
- Mensagens diretas em tempo real.
- **Convite para mesa pelo chat**: a pessoa recebe um cartão na conversa e entra
  na mesa sem sair do site. Também funciona por código de convite.

---

## Estrutura

```
desktop.py         lançador do aplicativo (janela nativa + servidor embutido)
storybook.spec     receita do PyInstaller para gerar o .exe
app/
  main.py          aplicação FastAPI, rotas e tratamento de erro
  config.py        configuração (lê o .env)
  database.py      engine e sessão do SQLAlchemy
  models.py        tabelas
  schemas.py       validação das entradas da API (Pydantic)
  security.py      hash de senha (argon2), cookie de sessão, CSRF
  deps.py          usuário atual, acesso a sala, checagem de permissão
  permissions.py   as 18 permissões e os padrões por cargo
  dice.py          motor de dados
  realtime.py      hub de WebSocket
  services.py      serialização e consultas compartilhadas
  systems/         DEFINIÇÕES DOS SISTEMAS DE RPG  ← comece por aqui
  routers/         rotas HTTP e WebSocket
  templates/       páginas (Jinja2)
  static/          CSS e JavaScript
seed.py            dados de demonstração
run.py             servidor de desenvolvimento
tests/             110 testes automatizados
```

---

## Triangle Agency — leia antes de jogar

O arquivo `app/systems/triangle_agency.py` foi escrito **antes do PDF do livro
ser anexado ao projeto**. A estrutura está pronta e funcionando (pool de d6
contando sucessos, competências, trilhas, anomalia, comissões, barras no token,
rolagens rápidas), mas os **nomes e números são marcadores** e precisam ser
conferidos contra o livro.

O topo do arquivo lista exatamente o que conferir:

- nome e quantidade das Competências (hoje: 4, escala 0–6);
- alvo do pool (hoje: 4+) e regra de crítico;
- nome e escala das trilhas de Realidade e Confiança;
- estrutura da Anomalia;
- lista real de Divisões;
- regra de Comissões.

**Para corrigir, edite só esse arquivo.** A ficha, as barras do token, o chat e
a tela de criação de mesa se readaptam sozinhos. Depois rode `pytest` — há
testes que conferem que todo campo tem valor inicial, que as barras apontam para
campos de recurso e que as fórmulas referenciam caminhos existentes.

### Adicionando outro sistema

1. Copie `app/systems/generico.py` (é o exemplo mais enxuto).
2. Ajuste `sections`, `defaults`, `token_bars` e `quick_rolls`.
3. Registre em `app/systems/__init__.py`, na lista `SYSTEMS`.

Pronto: o sistema aparece no seletor de mesa, a ficha se desenha sozinha e as
rolagens funcionam.

---

## Testes

```bash
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

Cobrem o motor de dados, as permissões, a consistência das definições de
sistema e a API (contas, mesas, tokens, fichas, amizades e convites), incluindo
os casos em que o acesso **deve** ser negado. Não precisam de servidor rodando.

Há também testes de navegador em `tests/e2e/`, que abrem um Chromium de verdade
e percorrem o site como um usuário — inclusive com dois navegadores ao mesmo
tempo, para conferir o tempo real. Eles precisam do servidor no ar; veja
`tests/e2e/README.md`.

---

## Subindo na VPS

### 1. Trocar para PostgreSQL

Descomente a linha do `psycopg` em `requirements.txt`, instale e aponte a URL:

```bash
DATABASE_URL=postgresql+psycopg://storybook:senha-forte@localhost:5432/storybook
```

Nada no código muda — é tudo SQLAlchemy.

### 2. `.env` de produção

```bash
DEBUG=false
BASE_URL=https://seudominio.com          # habilita cookie Secure automaticamente
SECRET_KEY=<python -c "import secrets; print(secrets.token_urlsafe(48))">
DATABASE_URL=postgresql+psycopg://...
ALLOW_PUBLIC_SIGNUP=false                # se quiser instância fechada
```

> `SECRET_KEY` fixa é obrigatória em produção: sem ela, cada reinício derruba
> todas as sessões.

### 3. Serviço

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Mantenha **um processo só** (`--workers 1`). O hub de WebSocket vive na memória
do processo; com vários workers, quem estiver em workers diferentes não recebe
os eventos um do outro. Para escalar depois, o caminho é trocar
`app/realtime.py` por um hub com Redis Pub/Sub.

Exemplo de unidade systemd:

```ini
[Unit]
Description=StoryBook
After=network.target postgresql.service

[Service]
User=storybook
WorkingDirectory=/opt/storybook
EnvironmentFile=/opt/storybook/.env
ExecStart=/opt/storybook/.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000
Restart=always

[Install]
WantedBy=multi-user.target
```

### 4. Nginx (o WebSocket precisa do upgrade)

```nginx
location / {
    proxy_pass http://127.0.0.1:8000;
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 3600s;
}
client_max_body_size 10M;
```

Sem o `Upgrade`/`Connection`, o site abre mas a mesa não sincroniza.

### 5. Uploads

Ficam no disco, em `UPLOAD_DIR` (padrão `./uploads`). Inclua essa pasta no
backup junto com o banco.

---

## Decisões de projeto

- **Sem framework de frontend.** As páginas são Jinja2 e o JavaScript é próprio,
  sem build. Isso mantém o deploy em um comando e o projeto legível.
- **Tokens são elementos do DOM, não `<canvas>`.** Custa um pouco de desempenho
  com centenas de tokens, mas ganha acessibilidade, clique direito, foco e CSS.
- **O banco é a fonte da verdade; o WebSocket só avisa.** Se a conexão cair,
  recarregar a página reconstrói o estado inteiro — nada vive só na memória.
- **Toda permissão é verificada no servidor.** A interface esconde o que você
  não pode fazer, mas quem tentar pela API leva 403.

## Limitações conhecidas

- Um processo só (ver acima).
- Sem recuperação de senha por e-mail.
- Névoa de guerra e medição de distância no mapa ainda não existem.
- A ficha do Triangle Agency é provisória (ver seção acima).
