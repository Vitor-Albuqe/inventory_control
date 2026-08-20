# -*- mode: python ; coding: utf-8 -*-
#
# As páginas em app/pages/*.py são carregadas dinamicamente pelo Streamlit
# em tempo de execução (não são importadas por launcher.py) — a análise
# estática do PyInstaller nunca "vê" o que elas importam. pandas e plotly
# só entram no build "por sorte" (são dependências do próprio Streamlit,
# coletadas pelo collect_all abaixo); qualquer outro pacote usado só dentro
# de uma página (ex.: babel em 6_Vendas.py) precisa ser listado aqui à mão.
from PyInstaller.utils.hooks import collect_all

datas = [('app', 'app'), ('.streamlit', '.streamlit')]
binaries = []
hiddenimports = ['streamlit.web.cli']
tmp_ret = collect_all('streamlit')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]

# Pacotes usados só dentro de app/pages/*.py (invisíveis à análise estática).
tmp_ret = collect_all('babel')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['launcher.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='ControleDeEstoque',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='ControleDeEstoque',
)
