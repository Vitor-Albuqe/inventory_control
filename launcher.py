"""Ponto de entrada do executável (PyInstaller).

Sobe o servidor Streamlit embutido e abre o navegador padrão apontando
para ele. Não é usado no desenvolvimento normal (aí se usa
`streamlit run app/main.py` diretamente) — só existe para dar ao usuário
final um .exe de clique duplo, sem precisar instalar Python.
"""

from __future__ import annotations

import sys
import threading
import time
import webbrowser
from pathlib import Path


def _base_path() -> Path:
    """Pasta onde os arquivos do app foram empacotados.

    No .exe (PyInstaller), os dados ficam em sys._MEIPASS. Em
    desenvolvimento (rodando este arquivo direto com `python launcher.py`),
    é a pasta deste próprio arquivo.
    """
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _abrir_navegador(url: str) -> None:
    # Só abre depois que o servidor Streamlit já está respondendo —
    # senão o navegador abre em cima da porta ainda inativa.
    import urllib.request

    for _ in range(60):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except OSError:
            time.sleep(0.5)
    webbrowser.open(url)


def main() -> None:
    base = _base_path()

    # Garante que "import app.xxx" funcione independente de onde o
    # executável foi extraído.
    sys.path.insert(0, str(base))

    app_main = str(base / "app" / "main.py")
    url = "http://localhost:8501"

    threading.Thread(target=_abrir_navegador, args=(url,), daemon=True).start()

    sys.argv = [
        "streamlit",
        "run",
        app_main,
        "--server.headless=true",
        "--global.developmentMode=false",
        # Explícito em vez de depender do .streamlit/config.toml ser
        # encontrado (o Streamlit procura esse arquivo relativo ao diretório
        # de trabalho — se o .exe for aberto/atalho criado com "Iniciar em"
        # apontando pra outro lugar, o config.toml não seria achado e o
        # servidor voltaria a escutar em todas as interfaces de rede).
        "--server.address=127.0.0.1",
    ]

    from streamlit.web import cli as stcli

    sys.exit(stcli.main())


if __name__ == "__main__":
    main()
