# -*- mode: python ; coding: utf-8 -*-
"""Receita do PyInstaller para gerar o StoryBook.exe.

    pyinstaller storybook.spec

Gera `dist/StoryBook.exe`: um arquivo só, sem instalador e sem Python na
máquina de quem vai usar.

Precisa rodar NO WINDOWS — o PyInstaller não faz compilação cruzada. O
workflow em .github/workflows/build-windows.yml faz isso automaticamente.
"""

from PyInstaller.utils.hooks import collect_submodules

# Templates e estáticos são lidos em tempo de execução: o PyInstaller não
# enxerga esses caminhos sozinho, então vão listados na mão.
dados = [
    ("app/templates", "app/templates"),
    ("app/static", "app/static"),
]

# O uvicorn e o SQLAlchemy carregam partes por nome, em tempo de execução.
# Sem declarar, o executável quebra só na hora de usar.
ocultos = (
    collect_submodules("uvicorn")
    + collect_submodules("app.systems")
    + [
        "sqlalchemy.dialects.sqlite",
        "sqlalchemy.dialects.postgresql",
        "anyio._backends._asyncio",
        "email_validator",
    ]
)

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    binaries=[],
    datas=dados,
    hiddenimports=ocultos,
    hookspath=[],
    runtime_hooks=[],
    # Pesos que não usamos e engordariam o executável em dezenas de MB.
    excludes=["tkinter", "matplotlib", "numpy", "pytest", "playwright"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="StoryBook",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    # console=False: sem janela preta de terminal atrás do aplicativo.
    console=False,
    disable_windowed_traceback=False,
    icon="app/static/img/storybook.ico",
)
