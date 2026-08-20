"""Gera os screenshots do README a partir do app rodando.

Screenshot de portfólio envelhece: muda a interface, mudam os dados, e a
imagem no README passa a mostrar uma versão que não existe mais. Este script
regenera todas de uma vez, sempre do app real.

Uso:
    # 1. Em outro terminal, suba o app:
    streamlit run app/main.py

    # 2. Capture:
    python scripts/capturar_screenshots.py

Usa o Chrome já instalado via DevTools Protocol (nenhuma dependência nova).
`chrome --screenshot` sozinho não serve: ele dispara antes do Streamlit
terminar o handshake de websocket e captura o esqueleto de carregamento —
por isso aqui a espera é de tempo real, depois de confirmar que a página
renderizou conteúdo de verdade.
"""

from __future__ import annotations

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import requests
import tornado.ioloop
import tornado.websocket

ROOT = Path(__file__).resolve().parents[1]
DESTINO = ROOT / "docs" / "img"
BASE_URL = os.environ.get("APP_URL", "http://localhost:8501")
PORTA_CDP = 9222

CAMINHOS_CHROME = [
    Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Google/Chrome/Application/chrome.exe",
    Path(os.environ.get("PROGRAMFILES", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
    Path("/usr/bin/google-chrome"),
    Path("/usr/bin/chromium"),
    Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
]

# (arquivo, rota, altura da janela, segundos de espera)
# Páginas com gráfico pesado precisam de mais tempo de render.
PAGINAS = [
    ("01-alertas.png",      "/alertas",      1000, 6),
    ("02-dashboard.png",    "/dashboard",    1400, 9),
    ("03-analises-sql.png", "/Analises_SQL", 1300, 9),
    ("04-vendas.png",       "/Vendas",       1100, 7),
    ("05-estoque.png",      "/Estoque",      1200, 7),
]

LARGURA = 1440


def achar_chrome() -> Path:
    for caminho in CAMINHOS_CHROME:
        if caminho and caminho.exists():
            return caminho
    print("Chrome/Edge não encontrado. Defina CHROME_PATH.", file=sys.stderr)
    sys.exit(1)


def app_no_ar() -> bool:
    try:
        return requests.get(BASE_URL, timeout=3).status_code == 200
    except requests.RequestException:
        return False


class SessaoCDP:
    """Conversa com o Chrome pelo DevTools Protocol (JSON sobre websocket)."""

    def __init__(self, ws_url: str):
        self.ws_url = ws_url
        self.id = 0
        self.loop = tornado.ioloop.IOLoop.current()
        self.conn = self.loop.run_sync(
            lambda: tornado.websocket.websocket_connect(ws_url, max_message_size=64 * 1024 * 1024)
        )

    def comando(self, metodo: str, **params) -> dict:
        self.id += 1
        meu_id = self.id
        self.conn.write_message(json.dumps({"id": meu_id, "method": metodo, "params": params}))

        async def esperar_resposta():
            while True:
                msg = await self.conn.read_message()
                if msg is None:
                    raise RuntimeError("Conexão com o Chrome caiu.")
                dados = json.loads(msg)
                # Eventos (sem "id") são ignorados: só interessa a resposta
                if dados.get("id") == meu_id:
                    return dados.get("result", {})

        return self.loop.run_sync(esperar_resposta)

    def fechar(self):
        self.conn.close()


def capturar(chrome: Path, perfil: Path) -> int:
    processo = subprocess.Popen(
        [
            str(chrome),
            "--headless=new",
            "--disable-gpu",
            "--hide-scrollbars",
            "--force-color-profile=srgb",
            f"--remote-debugging-port={PORTA_CDP}",
            f"--user-data-dir={perfil}",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Espera o endpoint de debug subir
    for _ in range(40):
        try:
            requests.get(f"http://127.0.0.1:{PORTA_CDP}/json/version", timeout=1)
            break
        except requests.RequestException:
            time.sleep(0.25)
    else:
        processo.terminate()
        print("Chrome não abriu a porta de depuração.", file=sys.stderr)
        return 1

    DESTINO.mkdir(parents=True, exist_ok=True)
    falhas = 0

    try:
        for arquivo, rota, altura, espera in PAGINAS:
            url = f"{BASE_URL}{rota}"
            alvo = requests.put(f"http://127.0.0.1:{PORTA_CDP}/json/new?about:blank", timeout=10).json()
            sessao = SessaoCDP(alvo["webSocketDebuggerUrl"])
            try:
                sessao.comando(
                    "Emulation.setDeviceMetricsOverride",
                    width=LARGURA, height=altura, deviceScaleFactor=2, mobile=False,
                )
                sessao.comando("Page.enable")
                sessao.comando("Page.navigate", url=url)

                # Streamlit pinta um esqueleto antes dos dados chegarem pelo
                # websocket; a espera de tempo real é o que separa a imagem
                # útil da imagem de "carregando".
                time.sleep(espera)

                texto = sessao.comando(
                    "Runtime.evaluate",
                    expression="document.body.innerText.length",
                    returnByValue=True,
                ).get("result", {}).get("value", 0)

                if texto < 200:
                    time.sleep(espera)  # segunda chance para páginas lentas

                png = sessao.comando(
                    "Page.captureScreenshot", format="png", captureBeyondViewport=True
                )["data"]
                destino = DESTINO / arquivo
                destino.write_bytes(base64.b64decode(png))
                tamanho_kb = destino.stat().st_size / 1024
                if tamanho_kb < 30:
                    print(f"  [aviso] {arquivo} ficou com {tamanho_kb:.0f} KB — "
                          f"provavelmente capturou a tela de carregamento.")
                    falhas += 1
                else:
                    print(f"  {arquivo:<22} {tamanho_kb:>6.0f} KB   {rota}")
            finally:
                sessao.fechar()
                requests.get(
                    f"http://127.0.0.1:{PORTA_CDP}/json/close/{alvo['id']}", timeout=5
                )
    finally:
        processo.terminate()
        processo.wait(timeout=10)

    return falhas


def main() -> None:
    if not app_no_ar():
        print(
            f"O app não respondeu em {BASE_URL}.\n"
            f"Suba primeiro em outro terminal:  streamlit run app/main.py",
            file=sys.stderr,
        )
        sys.exit(1)

    chrome = Path(os.environ.get("CHROME_PATH") or achar_chrome())
    print(f"Navegador: {chrome}")
    print(f"Capturando de {BASE_URL} para {DESTINO}\n")

    perfil = Path(tempfile.mkdtemp(prefix="cafezinho_shots_"))
    try:
        falhas = capturar(chrome, perfil)
    finally:
        shutil.rmtree(perfil, ignore_errors=True)

    print()
    if falhas:
        print(f"{falhas} captura(s) suspeita(s). Aumente a espera em PAGINAS e rode de novo.")
        sys.exit(1)
    print("Screenshots atualizados.")


if __name__ == "__main__":
    main()
