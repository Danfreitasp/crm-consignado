#!/usr/bin/env python3
"""Gerenciador do CRM Consignado.

Interface gráfica para as tarefas do dia a dia sem usar o terminal:

- abrir o CRM (iniciando o servidor quando necessário) no navegador;
- reiniciar o CRM;
- fechar o CRM;
- atualizar o código com git pull (fast-forward, sem descartar trabalho local);
- abrir a pasta do projeto e os logs.

Uso:
    python gerenciador_crm.py

Empacotamento no Windows:
    pyinstaller --onefile --windowed --name GerenciadorCRM gerenciador_crm.py
"""
from __future__ import annotations

import csv
import json
import os
import queue
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

APP_PY = "app.py"
TITULO = "Gerenciador CRM"
PORTA_PADRAO = 5000
ESPERA_INICIO = 90
ESPERA_PARADA = 20
SEM_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)

COR_FUNDO = "#f2f4f7"
COR_CARTAO = "#ffffff"
COR_BORDA = "#d8dee4"
COR_TEXTO = "#1f2328"
COR_SUAVE = "#57606a"
VERDE = "#1a7f37"
VERMELHO = "#b42318"
AMARELO = "#946200"


# ---------------------------------------------------------------------------
# Funções auxiliares (sem interface, cobertas pelos testes)
# ---------------------------------------------------------------------------
def pasta_dados() -> Path:
    """Pasta local de configuração e logs do gerenciador."""
    base = os.environ.get("APPDATA") or str(Path.home())
    pasta = Path(base) / "GerenciadorCRM"
    pasta.mkdir(parents=True, exist_ok=True)
    return pasta


def caminho_config() -> Path:
    return pasta_dados() / "config.json"


def caminho_log_gerenciador() -> Path:
    return pasta_dados() / "gerenciador.log"


def caminho_log_crm() -> Path:
    return pasta_dados() / "crm.log"


def carregar_config() -> dict:
    try:
        dados = json.loads(caminho_config().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return dados if isinstance(dados, dict) else {}


def salvar_config(config: dict) -> None:
    try:
        caminho_config().write_text(
            json.dumps(config, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def detectar_pasta_projeto(
    pasta_config: str | None = None,
    pasta_exe: Path | None = None,
    cwd: Path | None = None,
) -> Path | None:
    """Encontra a pasta que contém o app.py do CRM."""
    candidatos: list[Path] = []
    if pasta_config:
        candidatos.append(Path(pasta_config))
    if pasta_exe is None:
        if getattr(sys, "frozen", False):
            pasta_exe = Path(sys.executable).resolve().parent
        else:
            pasta_exe = Path(__file__).resolve().parent
    candidatos.append(Path(pasta_exe))
    candidatos.append(Path(cwd) if cwd is not None else Path.cwd())
    candidatos.append(Path(__file__).resolve().parent)

    vistos: set[Path] = set()
    for candidato in candidatos:
        try:
            resolvido = candidato.resolve()
        except OSError:
            continue
        if resolvido in vistos:
            continue
        vistos.add(resolvido)
        if (resolvido / APP_PY).is_file():
            return resolvido
    return None


def porta_configurada(config: dict) -> int:
    """Lê a porta salva na configuração, ignorando valores inválidos."""
    try:
        porta = int(config.get("porta") or 0)
    except (TypeError, ValueError):
        return 0
    return porta if 1 <= porta <= 65535 else 0


def ler_porta(pasta: Path | None) -> int:
    """Lê a porta usada em app.run(...), com 5000 como padrão."""
    if not pasta:
        return PORTA_PADRAO
    try:
        texto = (pasta / APP_PY).read_text(encoding="utf-8", errors="replace")
    except OSError:
        return PORTA_PADRAO
    encontrado = re.search(r"app\.run\([^)]*?port\s*=\s*(\d+)", texto)
    if not encontrado:
        return PORTA_PADRAO
    try:
        porta = int(encontrado.group(1))
    except ValueError:
        return PORTA_PADRAO
    return porta if 1 <= porta <= 65535 else PORTA_PADRAO


def localizar_python(pasta: Path | None, configurado: str | None = None) -> tuple[str | None, str]:
    """Retorna (executável, origem) para iniciar o app.py."""
    if configurado:
        caminho = Path(configurado).expanduser()
        if caminho.is_file():
            return str(caminho), "configurado"

    if pasta:
        for ambiente in (".venv", "venv", "env"):
            for nome in ("python.exe", "pythonw.exe"):
                caminho = pasta / ambiente / "Scripts" / nome
                if caminho.is_file():
                    return str(caminho), f"ambiente {ambiente}"

    for nome in ("python.exe", "python"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho, "PATH"

    for nome in ("py.exe", "py"):
        caminho = shutil.which(nome)
        if caminho:
            return caminho, "launcher py"

    return None, "não encontrado"


def caminho_exe_atual() -> Path | None:
    """Caminho do executável em execução, quando rodando empacotado."""
    if not getattr(sys, "frozen", False):
        return None
    return Path(sys.executable).resolve()


def arquivo_do_executavel(pasta: Path | None) -> tuple[Path, str] | None:
    """Executável atual e o caminho dele relativo à pasta do projeto."""
    exe = caminho_exe_atual()
    if exe is None or not pasta:
        return None
    try:
        relativo = exe.relative_to(pasta.resolve()).as_posix()
    except (ValueError, OSError):
        return None
    return exe, relativo


def caminho_executavel_antigo(exe: Path) -> Path:
    return exe.with_name(exe.name + ".old")


def _candidatos_backup(exe: Path) -> list[Path]:
    return [caminho_executavel_antigo(exe)] + [
        exe.with_name(f"{exe.name}.old{i}") for i in range(2, 10)
    ]


def liberar_executavel(exe: Path) -> Path | None:
    """Renomeia o executável em uso para .old e devolve o backup.

    O Windows bloqueia sobrescrever um .exe em execução, mas permite
    renomeá-lo. O processo atual continua rodando a partir do backup.
    Se um backup anterior ainda estiver em uso, tenta outro nome.
    """
    for backup in _candidatos_backup(exe):
        try:
            backup.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            continue
        try:
            exe.rename(backup)
        except OSError:
            return None
        return backup
    return None


def restaurar_executavel(exe: Path | None, backup: Path | None) -> None:
    if exe is None or backup is None or not backup.is_file():
        return
    try:
        if exe.exists():
            exe.unlink()
        backup.rename(exe)
    except OSError:
        pass


def remover_executavel_antigo(exe: Path | None) -> None:
    if exe is None:
        return
    for backup in _candidatos_backup(exe):
        try:
            backup.unlink(missing_ok=True)
        except OSError:
            pass


def porta_aberta(porta: int, host: str = "127.0.0.1", timeout: float = 0.25) -> bool:
    if not porta:
        return False
    try:
        with socket.create_connection((host, porta), timeout=timeout):
            return True
    except OSError:
        return False


def interpretar_netstat(saida: str, porta: int) -> list[int]:
    """Extrai os PIDs que escutam na porta a partir da saída do netstat.

    O texto da coluna de estado varia entre versões e idiomas do Windows
    (LISTENING, ESCUTANDO, …), então a linha de escuta é reconhecida pelo
    endereço remoto zerado ou pelo estado, sem exigir um texto específico.
    """
    escutando: list[int] = []
    conexoes: list[int] = []
    for linha in (saida or "").splitlines():
        partes = linha.split()
        if len(partes) < 5 or partes[0].upper() not in {"TCP", "TCPV6"}:
            continue
        if partes[1].rsplit(":", 1)[-1] != str(porta):
            continue
        if not partes[-1].isdigit():
            continue
        pid = int(partes[-1])
        if pid <= 0:
            continue
        estado = partes[3].upper()
        remoto = partes[2].rsplit(":", 1)[-1]
        if remoto in {"0", "*"} or estado.startswith(("LISTEN", "ESCUT", "OUV")):
            if pid not in escutando:
                escutando.append(pid)
        elif pid not in conexoes and pid not in escutando:
            conexoes.append(pid)
    # Em último caso, aceita qualquer conexão cuja porta local seja a procurada.
    return escutando or conexoes


def _pids_na_porta_tabela(porta: int) -> list[int]:
    """PIDs que escutam na porta, direto da tabela TCP do Windows.

    Usa GetExtendedTcpTable (iphlpapi) para não depender do netstat, que
    pode falhar, demorar ou ter a saída em formato inesperado.
    """
    if os.name != "nt":
        return []
    try:
        import ctypes
        from ctypes import wintypes

        class LinhaIPv4(ctypes.Structure):
            _fields_ = [
                ("estado", wintypes.DWORD),
                ("endereco_local", wintypes.DWORD),
                ("porta_local", wintypes.DWORD),
                ("endereco_remoto", wintypes.DWORD),
                ("porta_remota", wintypes.DWORD),
                ("pid", wintypes.DWORD),
            ]

        class LinhaIPv6(ctypes.Structure):
            _fields_ = [
                ("endereco_local", ctypes.c_ubyte * 16),
                ("escopo_local", wintypes.DWORD),
                ("porta_local", wintypes.DWORD),
                ("endereco_remoto", ctypes.c_ubyte * 16),
                ("escopo_remoto", wintypes.DWORD),
                ("porta_remota", wintypes.DWORD),
                ("estado", wintypes.DWORD),
                ("pid", wintypes.DWORD),
            ]

        iphlpapi = ctypes.WinDLL("iphlpapi")
        consultar = iphlpapi.GetExtendedTcpTable
        consultar.argtypes = [
            ctypes.c_void_p,
            ctypes.POINTER(wintypes.DWORD),
            wintypes.BOOL,
            wintypes.ULONG,
            ctypes.c_int,
            wintypes.ULONG,
        ]
        consultar.restype = wintypes.DWORD

        pids: list[int] = []

        def coletar(familia: int, linha) -> None:
            # TCP_TABLE_OWNER_PID_LISTENER = 3
            tamanho = wintypes.DWORD(0)
            consultar(None, ctypes.byref(tamanho), False, familia, 3, 0)
            if not tamanho.value:
                return
            buffer = ctypes.create_string_buffer(tamanho.value)
            if consultar(buffer, ctypes.byref(tamanho), False, familia, 3, 0) != 0:
                return
            total = ctypes.cast(buffer, ctypes.POINTER(wintypes.DWORD)).contents.value
            inicio = ctypes.addressof(buffer) + ctypes.sizeof(wintypes.DWORD)
            itens = ctypes.cast(inicio, ctypes.POINTER(linha * total)).contents
            for item in itens:
                # A porta vem em ordem de bytes de rede nos 16 bits baixos.
                porta_local = ((item.porta_local & 0xFF) << 8) | (
                    (item.porta_local >> 8) & 0xFF
                )
                if porta_local != porta:
                    continue
                pid = int(item.pid)
                if pid > 0 and pid not in pids:
                    pids.append(pid)

        coletar(2, LinhaIPv4)  # AF_INET
        coletar(23, LinhaIPv6)  # AF_INET6
        return pids
    except Exception:  # pragma: no cover - depende da API do Windows
        return []


def _pids_na_porta_powershell(porta: int) -> list[int]:
    if os.name != "nt":
        return []
    script = (
        f"Get-NetTCPConnection -LocalPort {int(porta)} -State Listen "
        "-ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess"
    )
    try:
        resultado = _rodar(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=30,
        )
    except (OSError, subprocess.SubprocessError):
        return []
    pids: list[int] = []
    for linha in (resultado.stdout or "").splitlines():
        texto = linha.strip()
        if texto.isdigit() and int(texto) > 0 and int(texto) not in pids:
            pids.append(int(texto))
    return pids


def pids_na_porta(porta: int) -> list[int]:
    if os.name != "nt" or not porta:
        return []
    pids = _pids_na_porta_tabela(porta)
    if pids:
        return pids
    try:
        resultado = _rodar(["netstat", "-ano"], timeout=30)
    except (OSError, subprocess.SubprocessError):
        resultado = None
    if resultado is not None:
        pids = interpretar_netstat(resultado.stdout, porta)
        if pids:
            return pids
    return _pids_na_porta_powershell(porta)


def nome_processo(pid: int) -> str:
    if os.name != "nt":
        return ""
    try:
        resultado = _rodar(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], timeout=15
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    linhas = [linha for linha in (resultado.stdout or "").splitlines() if linha.strip()]
    if not linhas:
        return ""
    try:
        campos = next(csv.reader([linhas[0]]))
    except (csv.Error, StopIteration):
        return ""
    if not campos:
        return ""
    nome = campos[0].strip()
    return nome if nome.lower().endswith(".exe") else ""


def linha_de_comando(pid: int) -> str:
    if os.name != "nt":
        return ""
    script = (
        f"$p = Get-CimInstance Win32_Process -Filter 'ProcessId={int(pid)}'; "
        "if ($p) { $p.CommandLine }"
    )
    try:
        resultado = _rodar(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            timeout=20,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return (resultado.stdout or "").strip()


def processo_e_python(nome: str) -> bool:
    nome = (nome or "").strip().lower()
    return nome.startswith("python") or nome in {"py.exe", "pyw.exe"}


def encerrar_processo(pid: int) -> tuple[bool, str]:
    if os.name != "nt":
        return False, "Sistema não suportado."
    try:
        resultado = _rodar(["taskkill", "/PID", str(int(pid)), "/T", "/F"], timeout=30)
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    saida = ((resultado.stdout or "") + (resultado.stderr or "")).strip()
    return resultado.returncode == 0, saida


def ambiente_git() -> dict:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_PAGER"] = "cat"
    env.setdefault("GIT_OPTIONAL_LOCKS", "0")
    return env


def interpretar_status_git(saida: str) -> dict:
    dados = {
        "branch": "",
        "upstream": "",
        "ahead": None,
        "behind": None,
        "alterados": 0,
        "nao_rastreados": 0,
    }
    for linha in (saida or "").splitlines():
        if linha.startswith("# branch.head "):
            dados["branch"] = linha[len("# branch.head "):].strip()
        elif linha.startswith("# branch.upstream "):
            dados["upstream"] = linha[len("# branch.upstream "):].strip()
        elif linha.startswith("# branch.ab "):
            encontrado = re.match(r"# branch\.ab \+(\d+) -(\d+)", linha)
            if encontrado:
                dados["ahead"] = int(encontrado.group(1))
                dados["behind"] = int(encontrado.group(2))
        elif linha.startswith("? "):
            dados["nao_rastreados"] += 1
        elif linha.startswith("#") or not linha.strip():
            continue
        else:
            dados["alterados"] += 1
    return dados


def resumo_git(pasta: Path | None) -> str:
    if not pasta or not (pasta / ".git").exists():
        return "Git: pasta sem repositório"
    try:
        resultado = _rodar(
            ["git", "-c", "core.quotepath=false", "status", "--porcelain=v2", "--branch"],
            cwd=pasta,
            timeout=30,
            encoding="utf-8",
            env=ambiente_git(),
        )
    except (OSError, subprocess.SubprocessError):
        return "Git: indisponível"
    if resultado.returncode != 0:
        return "Git: erro ao consultar o repositório"

    dados = interpretar_status_git(resultado.stdout)
    partes = [f"Branch {dados['branch'] or '?'}"]
    if not dados["upstream"]:
        partes.append("sem referência remota")
    elif dados["behind"] is None:
        partes.append(f"remoto {dados['upstream']}")
    elif dados["behind"] == 0:
        partes.append("em dia com o remoto")
    else:
        partes.append(f"{dados['behind']} commit(s) para baixar")
    if dados["ahead"]:
        partes.append(f"{dados['ahead']} commit(s) local(is) não enviado(s)")
    if dados["alterados"]:
        partes.append(f"{dados['alterados']} alteração(ões) local(is)")
    elif dados["nao_rastreados"]:
        partes.append(f"{dados['nao_rastreados']} arquivo(s) novo(s)")
    else:
        partes.append("sem alterações locais")
    return " · ".join(partes)


def alteracoes_relevantes(arquivos: list[str]) -> bool:
    """Indica se o pull mexeu em algo que exige reiniciar o CRM."""
    for arquivo in arquivos:
        if arquivo in {"app.py", "requirements.txt"}:
            return True
        if arquivo.startswith(("static/", "templates/", "data/")):
            return True
    return False


def cauda(caminho: Path, linhas: int = 25) -> str:
    try:
        texto = caminho.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return "\n".join(texto.splitlines()[-linhas:])


def rotacionar_log(caminho: Path, limite: int = 4 * 1024 * 1024) -> None:
    try:
        if caminho.exists() and caminho.stat().st_size > limite:
            destino = caminho.with_suffix(".1.log")
            destino.unlink(missing_ok=True)
            caminho.rename(destino)
    except OSError:
        pass


def _rodar(
    args: list[str],
    *,
    cwd: Path | None = None,
    timeout: float = 30,
    encoding: str = "oem",
    env: dict | None = None,
) -> subprocess.CompletedProcess:
    return subprocess.run(
        args,
        cwd=None if cwd is None else str(cwd),
        capture_output=True,
        text=True,
        encoding=encoding,
        errors="replace",
        timeout=timeout,
        env=env,
        stdin=subprocess.DEVNULL,
        creationflags=SEM_JANELA,
    )


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------
class GerenciadorCRM(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(TITULO)
        self.geometry("940x680")
        self.minsize(840, 600)
        self.configure(bg=COR_FUNDO)

        self._config = carregar_config()
        self._pasta = detectar_pasta_projeto(self._config.get("pasta"))
        self._porta = porta_configurada(self._config) or ler_porta(self._pasta)
        remover_executavel_antigo(caminho_exe_atual())
        self._python_config = str(self._config.get("python") or "")
        self._processo: subprocess.Popen | None = None
        self._exe_backup: Path | None = None
        self._arquivo_log_crm = None
        self._ocupado = False
        self._crm_aberto = False
        self._fila: queue.Queue = queue.Queue()
        self._botoes_acao: list[ttk.Button] = []
        self._botoes_por_nome: dict[str, ttk.Button] = {}

        self._montar_interface()
        self.protocol("WM_DELETE_WINDOW", self._ao_fechar)
        self._drenar_fila()
        self._registrar_inicio()
        self._atualizar_status()
        self.after(1500, self._ciclo_status)

    # -- construção da janela -------------------------------------------------
    @property
    def _url(self) -> str:
        return f"http://127.0.0.1:{self._porta}/"

    @property
    def _pasta_valida(self) -> bool:
        return bool(self._pasta and (self._pasta / APP_PY).is_file())

    def _montar_interface(self) -> None:
        estilo = ttk.Style(self)
        for tema in ("vista", "clam"):
            if tema in estilo.theme_names():
                estilo.theme_use(tema)
                break

        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        cabecalho = tk.Frame(self, bg=COR_FUNDO)
        cabecalho.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 6))
        tk.Label(
            cabecalho, text=TITULO, bg=COR_FUNDO, fg=COR_TEXTO,
            font=("Segoe UI", 18, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            cabecalho,
            text="Atualize o código, reinicie e feche o CRM sem usar o terminal.",
            bg=COR_FUNDO, fg=COR_SUAVE, font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x")

        cartao = tk.Frame(
            self, bg=COR_CARTAO, highlightbackground=COR_BORDA, highlightthickness=1
        )
        cartao.grid(row=1, column=0, sticky="ew", padx=14, pady=(0, 10))
        self._rotulo_status = tk.Label(
            cartao, text="Verificando…", bg=COR_CARTAO, fg=COR_SUAVE,
            font=("Segoe UI", 13, "bold"), anchor="w",
        )
        self._rotulo_status.pack(fill="x", padx=12, pady=(10, 2))
        self._rotulo_projeto = tk.Label(
            cartao, text="", bg=COR_CARTAO, fg=COR_SUAVE, font=("Segoe UI", 9),
            anchor="w", justify="left", wraplength=880,
        )
        self._rotulo_projeto.pack(fill="x", padx=12)
        self._rotulo_git = tk.Label(
            cartao, text="Git: verificando…", bg=COR_CARTAO, fg=COR_SUAVE,
            font=("Segoe UI", 9), anchor="w", justify="left", wraplength=880,
        )
        self._rotulo_git.pack(fill="x", padx=12, pady=(0, 10))

        acoes = ttk.LabelFrame(self, text="Ações", padding=10)
        acoes.grid(row=2, column=0, sticky="ew", padx=14, pady=(0, 10))
        for coluna in range(3):
            acoes.columnconfigure(coluna, weight=1, uniform="acao")

        botoes = [
            ("Abrir CRM", self.abrir_crm, "Abre o CRM no navegador, inclusive se já estiver aberto."),
            ("Iniciar CRM", self.iniciar_crm, "Inicia o servidor do CRM quando estiver parado."),
            ("Reiniciar CRM", self.reiniciar_crm, "Encerra e inicia o CRM novamente."),
            ("Fechar CRM", self.fechar_crm, "Encerra o processo do CRM."),
            ("Fazer Git Pull", self.git_pull, "Baixa atualizações sem descartar alterações locais."),
            ("Ver log do CRM", self.ver_log_crm, "Abre o log gerado ao iniciar o CRM."),
            ("Abrir pasta", self.abrir_pasta, "Abre a pasta do projeto no Explorador."),
            ("Configurações", self.abrir_configuracoes, "Pasta do projeto, Python e porta."),
            ("Limpar histórico", self.limpar_historico, "Limpa apenas o painel de mensagens."),
        ]
        self._dicas: list[_Tooltip] = []
        for indice, (texto, comando, dica) in enumerate(botoes):
            linha, coluna = divmod(indice, 3)
            botao = ttk.Button(acoes, text=texto, command=comando, width=20)
            botao.grid(row=linha, column=coluna, padx=4, pady=4, sticky="ew")
            self._botoes_acao.append(botao)
            self._botoes_por_nome[texto] = botao
            self._dicas.append(_Tooltip(botao, dica))

        quadro_log = ttk.LabelFrame(self, text="Histórico", padding=8)
        quadro_log.grid(row=3, column=0, sticky="nsew", padx=14, pady=(0, 8))
        quadro_log.columnconfigure(0, weight=1)
        quadro_log.rowconfigure(0, weight=1)
        self._texto_log = tk.Text(
            quadro_log, height=10, wrap="word", state="disabled",
            bg="#fbfbfb", fg=COR_TEXTO, relief="flat", padx=8, pady=6,
            font=("Consolas", 9),
        )
        barra = ttk.Scrollbar(quadro_log, orient="vertical", command=self._texto_log.yview)
        self._texto_log.configure(yscrollcommand=barra.set)
        self._texto_log.grid(row=0, column=0, sticky="nsew")
        barra.grid(row=0, column=1, sticky="ns")
        self._texto_log.tag_configure("erro", foreground=VERMELHO)
        self._texto_log.tag_configure("ok", foreground=VERDE)
        self._texto_log.tag_configure("aviso", foreground=AMARELO)
        self._texto_log.tag_configure("info", foreground=COR_TEXTO)
        self._texto_log.tag_configure("destaque", foreground="#0b4f8a")

        tk.Label(
            self,
            text="O CRM continua em execução se você fechar esta janela.",
            bg=COR_FUNDO, fg=COR_SUAVE, font=("Segoe UI", 8), anchor="w",
        ).grid(row=4, column=0, sticky="ew", padx=16, pady=(0, 8))

    # -- log ------------------------------------------------------------------
    def _log(self, mensagem: str, nivel: str = "info") -> None:
        horario = datetime.now().strftime("%H:%M:%S")
        self._texto_log.configure(state="normal")
        self._texto_log.insert("end", f"{horario}  {mensagem}\n", nivel)
        self._texto_log.see("end")
        self._texto_log.configure(state="disabled")
        try:
            with caminho_log_gerenciador().open("a", encoding="utf-8") as arquivo:
                arquivo.write(f"{datetime.now().isoformat(timespec='seconds')}  {mensagem}\n")
        except OSError:
            pass

    def _enviar_log(self, mensagem: str, nivel: str = "info") -> None:
        self._fila.put(("log", (mensagem, nivel)))

    def _enviar(self, tipo: str, dados=None) -> None:
        self._fila.put((tipo, dados))

    def _drenar_fila(self) -> None:
        try:
            while True:
                tipo, dados = self._fila.get_nowait()
                if tipo == "log":
                    self._log(*dados)
                elif tipo == "atualizar_status":
                    self._atualizar_status()
                elif tipo == "info_git":
                    self._rotulo_git.configure(text=dados)
                elif tipo == "fim_acao":
                    self._definir_ocupado(False)
                    self._atualizar_status()
                    self._atualizar_info_git()
                elif tipo == "fim_git":
                    relevantes, atualizou_gerenciador = dados
                    self._definir_ocupado(False)
                    self._atualizar_status()
                    self._atualizar_info_git()
                    if atualizou_gerenciador:
                        if self._crm_aberto:
                            self._log(
                                "Reinicie o CRM depois de reabrir o gerenciador, se necessário.",
                                "aviso",
                            )
                        if messagebox.askyesno(
                            "Gerenciador atualizado",
                            "A nova versão do gerenciador foi baixada.\n\n"
                            "Reiniciar o gerenciador agora para usá-la?",
                            parent=self,
                        ):
                            self._reiniciar_gerenciador()
                        else:
                            self._log(
                                "Feche e abra o gerenciador para usar a nova versão.", "aviso"
                            )
                    elif relevantes and self._crm_aberto:
                        if messagebox.askyesno(
                            "Atualização aplicada",
                            "As mudanças afetam o CRM em execução.\n"
                            "Deseja reiniciar agora para aplicá-las?",
                            parent=self,
                        ):
                            self.reiniciar_crm()
        except queue.Empty:
            pass
        self.after(120, self._drenar_fila)

    def limpar_historico(self) -> None:
        self._texto_log.configure(state="normal")
        self._texto_log.delete("1.0", "end")
        self._texto_log.configure(state="disabled")
        self._log("Histórico limpo.", "info")

    # -- estado ---------------------------------------------------------------
    def _atualizar_status(self) -> None:
        self._crm_aberto = self._pasta_valida and porta_aberta(self._porta)
        proprio = self._processo is not None and self._processo.poll() is None
        if self._crm_aberto and proprio:
            texto, cor = f"CRM em execução · iniciado por este gerenciador (porta {self._porta})", VERDE
        elif self._crm_aberto:
            texto, cor = f"CRM em execução · processo externo (porta {self._porta})", VERDE
        elif proprio:
            texto, cor = "Iniciando o CRM…", AMARELO
        elif self._pasta_valida:
            texto, cor = "CRM parado", COR_SUAVE
        else:
            texto, cor = "Pasta do projeto não configurada", VERMELHO
        self._rotulo_status.configure(text=texto, fg=cor)
        self._atualizar_botoes()

    def _atualizar_botoes(self) -> None:
        if self._ocupado:
            return
        habilitado = self._pasta_valida
        for botao in self._botoes_acao:
            botao.configure(state="normal" if habilitado else "disabled")
        if not habilitado:
            for nome in ("Configurações", "Limpar histórico"):
                self._botoes_por_nome[nome].configure(state="normal")
            return
        self._botoes_por_nome["Iniciar CRM"].configure(
            state="disabled" if self._crm_aberto else "normal"
        )
        self._botoes_por_nome["Fechar CRM"].configure(
            state="normal" if self._crm_aberto else "disabled"
        )

    def _atualizar_rotulos(self) -> None:
        python, origem = localizar_python(self._pasta, self._python_config)
        projeto = str(self._pasta) if self._pasta else "não encontrada"
        detalhe_python = f"{python} ({origem})" if python else "não encontrado"
        self._rotulo_projeto.configure(
            text=f"Projeto: {projeto}    ·    Porta: {self._porta}    ·    Python: {detalhe_python}"
        )
        self._atualizar_status()

    def _definir_ocupado(self, ocupado: bool) -> None:
        self._ocupado = bool(ocupado)
        for botao in self._botoes_acao:
            botao.configure(state="disabled" if self._ocupado else "normal")
        self.configure(cursor="watch" if self._ocupado else "")
        if not self._ocupado:
            self._atualizar_botoes()

    def _ciclo_status(self) -> None:
        try:
            self._atualizar_status()
        finally:
            self.after(4000, self._ciclo_status)

    def _atualizar_info_git(self) -> None:
        if not self._pasta_valida:
            self._rotulo_git.configure(text="Git: configure a pasta do projeto")
            return
        threading.Thread(target=self._tarefa_info_git, daemon=True).start()

    def _tarefa_info_git(self) -> None:
        try:
            texto = resumo_git(self._pasta)
        except Exception as exc:  # pragma: no cover - defensivo
            texto = f"Git: indisponível ({exc})"
        self._enviar("info_git", texto)

    def _registrar_inicio(self) -> None:
        rotacionar_log(caminho_log_gerenciador())
        self._log("Gerenciador iniciado.", "destaque")
        if not self._pasta_valida:
            self._log(
                "Não encontrei o app.py. Abra as Configurações e indique a pasta do CRM.",
                "erro",
            )
            self._atualizar_rotulos()
            self.after(500, self.abrir_configuracoes)
            return
        self._log(f"Projeto: {self._pasta}", "info")
        self._log(f"URL local: {self._url}", "info")
        python, origem = localizar_python(self._pasta, self._python_config)
        if python:
            self._log(f"Python: {python} ({origem})", "info")
        else:
            self._log(
                "Python não encontrado. Instale o Python ou indique o executável em Configurações.",
                "erro",
            )
        self._log(f"Log do CRM: {caminho_log_crm()}", "info")
        if shutil.which("git") is None:
            self._log("Git não encontrado no PATH; o Git Pull não vai funcionar.", "erro")
        self._atualizar_rotulos()
        self._atualizar_info_git()

    # -- abrir / iniciar ------------------------------------------------------
    def abrir_crm(self) -> None:
        if not self._pasta_valida:
            self._log("Configure a pasta do projeto antes de abrir o CRM.", "erro")
            return
        self._atualizar_status()
        if not self._crm_aberto:
            if messagebox.askyesno(
                "Abrir CRM",
                "O CRM não está em execução.\n\nIniciar agora?",
                parent=self,
            ):
                self._iniciar(abrir_navegador=True)
            else:
                self._log("O CRM não está em execução. Use Iniciar CRM.", "aviso")
            return
        webbrowser.open(self._url)
        self._log(f"Abrindo {self._url}", "info")

    def iniciar_crm(self) -> None:
        if self._ocupado:
            return
        if self._crm_aberto:
            self._log("O CRM já está em execução.", "ok")
            return
        self._iniciar(abrir_navegador=False)

    def abrir_pasta(self) -> None:
        if not self._pasta:
            self._log("Pasta do projeto não configurada.", "erro")
            return
        try:
            os.startfile(str(self._pasta))  # type: ignore[attr-defined]
        except OSError as exc:
            self._log(f"Não foi possível abrir a pasta: {exc}", "erro")

    def ver_log_crm(self) -> None:
        caminho = caminho_log_crm()
        if not caminho.exists():
            self._log("Ainda não existe log do CRM; inicie o CRM pelo gerenciador.", "aviso")
            return
        try:
            os.startfile(str(caminho))  # type: ignore[attr-defined]
        except OSError as exc:
            self._log(f"Não foi possível abrir o log: {exc}", "erro")

    def _iniciar(self, abrir_navegador: bool) -> None:
        if not self._pasta_valida:
            self._log("Pasta do projeto inválida; configure antes de iniciar.", "erro")
            return
        python, origem = localizar_python(self._pasta, self._python_config)
        if not python:
            self._log("Python não encontrado. Configure o executável em Configurações.", "erro")
            messagebox.showerror(
                TITULO,
                "Não encontrei o Python para iniciar o CRM.\n"
                "Instale o Python ou indique o executável em Configurações.",
                parent=self,
            )
            return
        self._definir_ocupado(True)
        self._log(f"Iniciando o CRM com {python} ({origem})…", "destaque")
        threading.Thread(
            target=self._tarefa_iniciar,
            args=(python, abrir_navegador),
            daemon=True,
        ).start()

    def _tarefa_iniciar(self, python: str, abrir_navegador: bool) -> None:
        try:
            self._iniciar_sem_ui(python, abrir_navegador)
        finally:
            self._enviar("fim_acao", None)

    def _iniciar_sem_ui(self, python: str, abrir_navegador: bool) -> bool:
        pasta = self._pasta
        if not pasta:
            return False
        log_crm = caminho_log_crm()
        rotacionar_log(log_crm)
        try:
            arquivo = log_crm.open("ab", buffering=0)
        except OSError as exc:
            self._enviar_log(f"Não foi possível abrir o log do CRM: {exc}", "erro")
            return False
        self._arquivo_log_crm = arquivo

        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        comando = [python, "-u", str(pasta / APP_PY)]
        self._enviar_log("Comando: " + subprocess.list2cmdline(comando), "info")
        try:
            processo = subprocess.Popen(
                comando,
                cwd=str(pasta),
                stdin=subprocess.DEVNULL,
                stdout=arquivo,
                stderr=subprocess.STDOUT,
                env=env,
                creationflags=SEM_JANELA,
            )
        except OSError as exc:
            self._enviar_log(f"Falha ao iniciar o CRM: {exc}", "erro")
            self._fechar_log_crm()
            return False

        self._processo = processo
        self._enviar("atualizar_status", None)
        self._enviar_log(
            f"Processo PID {processo.pid} iniciado. Aguardando resposta na porta {self._porta}…",
            "info",
        )
        limite = time.monotonic() + ESPERA_INICIO
        while time.monotonic() < limite:
            if processo.poll() is not None:
                self._enviar_log(
                    f"O CRM encerrou durante a inicialização (código {processo.returncode}).",
                    "erro",
                )
                self._registrar_cauda(log_crm)
                self._fechar_log_crm()
                self._processo = None
                return False
            if porta_aberta(self._porta):
                self._enviar_log(f"CRM disponível em {self._url}", "ok")
                if abrir_navegador:
                    webbrowser.open(self._url)
                return True
            time.sleep(0.8)

        self._enviar_log(
            f"O CRM ainda não respondeu após {ESPERA_INICIO}s. Ele pode continuar "
            "iniciando; acompanhe pelo log.",
            "aviso",
        )
        self._registrar_cauda(log_crm)
        return False

    def _registrar_cauda(self, caminho: Path, linhas: int = 20) -> None:
        texto = cauda(caminho, linhas)
        if not texto:
            self._enviar_log("(log vazio)", "aviso")
            return
        self._enviar_log("Últimas linhas do log do CRM:", "aviso")
        for linha in texto.splitlines():
            self._enviar_log("   " + linha, "info")

    def _fechar_log_crm(self) -> None:
        arquivo, self._arquivo_log_crm = self._arquivo_log_crm, None
        if arquivo is not None:
            try:
                arquivo.close()
            except OSError:
                pass

    # -- fechar / reiniciar ---------------------------------------------------
    def _reiniciar_gerenciador(self) -> None:
        exe = caminho_exe_atual()
        if exe is None or not exe.is_file():
            self._log(
                "Não encontrei o novo GerenciadorCRM.exe; abra-o manualmente.", "erro"
            )
            return
        alvo = arquivo_do_executavel(self._pasta)
        if alvo is not None and not self._executavel_integro(alvo[1]):
            tinha_backup = self._exe_backup is not None
            restaurar_executavel(exe, self._exe_backup)
            self._exe_backup = None
            if tinha_backup:
                detalhe = (
                    "A versão anterior foi restaurada. Feche este gerenciador e "
                    "abra-o novamente para continuar na versão antiga."
                )
            else:
                detalhe = (
                    "Feche este gerenciador e rode no terminal: git checkout HEAD -- "
                    f"{alvo[1]}"
                )
            self._log(
                "O novo executável não passou na verificação de integridade. " + detalhe,
                "erro",
            )
            messagebox.showerror(
                "Gerenciador não atualizado",
                "O novo GerenciadorCRM.exe chegou corrompido.\n\n" + detalhe,
                parent=self,
            )
            return
        try:
            subprocess.Popen(
                [str(exe)], cwd=None if self._pasta is None else str(self._pasta)
            )
        except OSError as exc:
            self._log(
                f"Não foi possível abrir a nova versão: {exc}. Abra manualmente.", "erro"
            )
            return
        self._exe_backup = None
        self._fechar_log_crm()
        self.destroy()

    def _alvos_para_parar(self) -> tuple[list[int], bool]:
        if self._processo is not None:
            if self._processo.poll() is None:
                return [self._processo.pid], False
            self._processo = None
            self._fechar_log_crm()
        if not porta_aberta(self._porta):
            return [], False
        return pids_na_porta(self._porta), True

    def fechar_crm(self) -> None:
        if self._ocupado:
            return
        pids, externo = self._alvos_para_parar()
        if not pids:
            if porta_aberta(self._porta):
                self._log(
                    f"A porta {self._porta} está em uso, mas não consegui identificar o processo. "
                    "Nada foi encerrado. Feche o CRM pelo terminal em que ele foi iniciado "
                    "(ou pelo gerenciador que o abriu) e tente de novo.",
                    "erro",
                )
            else:
                self._log("O CRM já está parado.", "info")
            self._atualizar_status()
            return
        if externo:
            confirmacao = (
                "O CRM está aberto fora deste gerenciador "
                f"(PID {', '.join(str(pid) for pid in pids)}).\n\nEncerrar mesmo assim?"
            )
        else:
            confirmacao = "Encerrar o CRM agora?"
        if not messagebox.askyesno("Fechar CRM", confirmacao, parent=self):
            return
        self._definir_ocupado(True)
        threading.Thread(
            target=self._tarefa_parar, args=(pids,), daemon=True
        ).start()

    def _tarefa_parar(self, pids: list[int]) -> None:
        try:
            self._parar_sem_ui(pids)
        finally:
            self._enviar("fim_acao", None)

    def _parar_sem_ui(self, pids: list[int]) -> bool:
        if not pids:
            self._enviar_log("O CRM já está parado.", "info")
            return True
        for pid in pids:
            nome = nome_processo(pid)
            if not nome:
                self._enviar_log(f"PID {pid} já não existe.", "aviso")
                continue
            if not processo_e_python(nome):
                self._enviar_log(
                    f"PID {pid} é '{nome}' e não parece ser o CRM; ignorado por segurança.",
                    "erro",
                )
                continue
            comando = linha_de_comando(pid)
            if comando and "app.py" not in comando.lower() and "flask" not in comando.lower():
                self._enviar_log(
                    "Aviso: o processo não referencia app.py; encerrando por solicitação.",
                    "aviso",
                )
            self._enviar_log(f"Encerrando PID {pid} ({nome})…", "info")
            ok, saida = encerrar_processo(pid)
            if not ok:
                self._enviar_log(
                    f"Falha ao encerrar PID {pid}: {saida[:300] or 'sem detalhes'}",
                    "erro",
                )

        limite = time.monotonic() + ESPERA_PARADA
        while time.monotonic() < limite and porta_aberta(self._porta):
            time.sleep(0.5)
        if porta_aberta(self._porta):
            self._enviar_log(f"A porta {self._porta} continua em uso.", "erro")
            return False

        self._enviar_log("CRM encerrado.", "ok")
        if self._processo is not None and self._processo.poll() is not None:
            self._processo = None
        self._fechar_log_crm()
        return True

    def reiniciar_crm(self) -> None:
        if self._ocupado:
            return
        pids, externo = self._alvos_para_parar()
        if not pids and porta_aberta(self._porta):
            self._log(
                f"A porta {self._porta} está em uso, mas não consegui identificar o processo. "
                "O reinício foi cancelado.",
                "erro",
            )
            return
        if externo and pids:
            if not messagebox.askyesno(
                "Reiniciar CRM",
                "O CRM está aberto fora deste gerenciador "
                f"(PID {', '.join(str(pid) for pid in pids)}).\n\nReiniciar mesmo assim?",
                parent=self,
            ):
                return
        self._definir_ocupado(True)
        threading.Thread(
            target=self._tarefa_reiniciar, args=(pids,), daemon=True
        ).start()

    def _tarefa_reiniciar(self, pids: list[int]) -> None:
        try:
            self._enviar_log("Reiniciando o CRM…", "destaque")
            if pids and not self._parar_sem_ui(pids):
                self._enviar_log("Não foi possível encerrar o CRM; reinício cancelado.", "erro")
                return
            python, origem = localizar_python(self._pasta, self._python_config)
            if not python:
                self._enviar_log(
                    "Python não encontrado; não foi possível reiniciar o CRM.", "erro"
                )
                return
            self._enviar_log(f"Python: {python} ({origem})", "info")
            self._iniciar_sem_ui(python, abrir_navegador=False)
        finally:
            self._enviar("fim_acao", None)

    # -- git ------------------------------------------------------------------
    def git_pull(self) -> None:
        if self._ocupado:
            return
        if not self._pasta_valida:
            self._log("Configure a pasta do projeto antes de atualizar.", "erro")
            return
        if shutil.which("git") is None:
            self._log("Git não encontrado no PATH.", "erro")
            messagebox.showerror(TITULO, "Git não encontrado no PATH.", parent=self)
            return
        if self._processo is not None and self._processo.poll() is None:
            if not messagebox.askyesno(
                "Fazer Git Pull",
                "O CRM está em execução. A atualização será baixada agora e aplicada "
                "somente quando você reiniciar.\n\nContinuar?",
                parent=self,
            ):
                return
        self._definir_ocupado(True)
        threading.Thread(target=self._tarefa_git_pull, daemon=True).start()

    def _git(self, args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
        return _rodar(
            ["git", "-c", "core.quotepath=false", *args],
            cwd=self._pasta,
            timeout=timeout,
            encoding="utf-8",
            env=ambiente_git(),
        )

    def _executavel_integro(self, relativo: str) -> bool:
        """Confere se o .exe do disco tem exatamente os bytes do commit atual."""
        esperado = self._git(["rev-parse", f"HEAD:{relativo}"])
        if esperado.returncode != 0 or not esperado.stdout.strip():
            return False
        atual = self._git(["hash-object", "--no-filters", "--", relativo])
        if atual.returncode != 0:
            return False
        return atual.stdout.strip() == esperado.stdout.strip()

    def _registrar_saida_git(self, resultado: subprocess.CompletedProcess) -> None:
        nivel = "info" if resultado.returncode == 0 else "erro"
        texto = ((resultado.stdout or "") + (resultado.stderr or "")).strip()
        if not texto:
            return
        for linha in texto.splitlines():
            if linha.strip():
                self._enviar_log("   " + linha.rstrip(), nivel)

    def _tarefa_git_pull(self) -> None:
        relevantes = False
        gerenciador_atualizado = False
        exe_atual: Path | None = None
        backup_exe: Path | None = None
        relativo = ""
        try:
            self._enviar_log(f"Verificando o repositório em {self._pasta}…", "destaque")
            resultado = self._git(["status", "--porcelain"])
            if resultado.returncode != 0:
                self._enviar_log("Não foi possível ler o status do Git:", "erro")
                self._registrar_saida_git(resultado)
                return

            linhas = [linha for linha in resultado.stdout.splitlines() if linha.strip()]
            modificados = [linha for linha in linhas if not linha.startswith("??")]
            novos = [linha for linha in linhas if linha.startswith("??")]
            if modificados:
                self._enviar_log(
                    "Existem alterações locais não commitadas. O pull foi cancelado "
                    "para não sobrescrever nada:",
                    "erro",
                )
                for linha in modificados[:25]:
                    self._enviar_log("   " + linha, "erro")
                if len(modificados) > 25:
                    self._enviar_log(f"   … e mais {len(modificados) - 25} arquivo(s).", "erro")
                self._enviar_log(
                    "Faça commit ou resolva essas alterações e tente novamente.", "aviso"
                )
                return
            if novos:
                self._enviar_log(
                    f"{len(novos)} arquivo(s) não rastreado(s) serão preservados.", "aviso"
                )
                for linha in novos[:10]:
                    self._enviar_log("   " + linha, "aviso")
                if len(novos) > 10:
                    self._enviar_log(f"   … e mais {len(novos) - 10} arquivo(s).", "aviso")

            resultado = self._git(["rev-parse", "--abbrev-ref", "HEAD"])
            if resultado.returncode != 0:
                self._enviar_log("Não foi possível identificar a branch atual.", "erro")
                return
            branch = resultado.stdout.strip() or "(desconhecida)"
            self._enviar_log(f"Branch atual: {branch}", "info")

            self._enviar_log("Buscando atualizações (git fetch)…", "info")
            resultado = self._git(["fetch", "--prune"], timeout=180)
            self._registrar_saida_git(resultado)
            if resultado.returncode != 0:
                self._enviar_log("O git fetch falhou; verifique a conexão e as credenciais.", "erro")
                return

            resultado = self._git(
                ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"]
            )
            remoto = resultado.stdout.strip() if resultado.returncode == 0 else ""
            if not remoto:
                self._enviar_log("A branch atual não tem referência remota configurada.", "erro")
                return

            resultado = self._git(["rev-list", "--left-right", "--count", f"HEAD...{remoto}"])
            if resultado.returncode != 0:
                self._enviar_log("Não foi possível comparar com o remoto.", "erro")
                self._registrar_saida_git(resultado)
                return
            partes = resultado.stdout.split()
            try:
                frente, atras = int(partes[0]), int(partes[1])
            except (IndexError, ValueError):
                self._enviar_log("Resposta inesperada do Git ao comparar commits.", "erro")
                return

            if atras == 0:
                extra = f" Há {frente} commit(s) local(is) não enviado(s)." if frente else ""
                self._enviar_log(f"Já está atualizado em relação a {remoto}.{extra}", "ok")
                return
            if frente:
                self._enviar_log(
                    f"A branch divergiu de {remoto}: {frente} commit(s) local(is) e "
                    f"{atras} remoto(s). O pull automático foi cancelado.",
                    "erro",
                )
                return

            alvo_exe = arquivo_do_executavel(self._pasta)
            arquivos_novos: list[str] = []
            if alvo_exe:
                resultado = self._git(["diff", "--name-only", f"HEAD..{remoto}"])
                if resultado.returncode == 0:
                    arquivos_novos = [
                        linha for linha in resultado.stdout.splitlines() if linha.strip()
                    ]
            if alvo_exe and alvo_exe[1] in arquivos_novos:
                exe_atual, relativo = alvo_exe
                backup_exe = liberar_executavel(exe_atual)
                if backup_exe is None:
                    exe_atual = None
                    self._enviar_log(
                        "Esta atualização inclui o GerenciadorCRM.exe, mas não foi possível "
                        "liberá-lo (arquivo em uso). Feche o gerenciador e faça o pull por "
                        "outro programa (terminal ou GitHub Desktop); depois abra-o novamente.",
                        "erro",
                    )
                    return
                self._enviar_log("Executável do gerenciador liberado para atualização.", "info")
                if self._git(["ls-files", "--error-unmatch", relativo]).returncode == 0:
                    self._git(["checkout", "--", relativo])

            self._enviar_log(
                f"{atras} commit(s) novo(s) em {remoto}. Aplicando git pull --ff-only…",
                "destaque",
            )
            antes = self._git(["rev-parse", "HEAD"]).stdout.strip()
            resultado = self._git(["pull", "--ff-only"], timeout=300)
            self._registrar_saida_git(resultado)
            if resultado.returncode != 0:
                self._enviar_log(
                    "O git pull falhou. Nenhuma alteração local foi descartada.", "erro"
                )
                return
            depois = self._git(["rev-parse", "HEAD"]).stdout.strip()
            self._enviar_log(f"Atualizado: {antes[:7]} → {depois[:7]}", "ok")

            gerenciador_atualizado = backup_exe is not None
            if gerenciador_atualizado and exe_atual is not None:
                if not self._executavel_integro(relativo):
                    self._enviar_log(
                        "O GerenciadorCRM.exe baixado não confere com o repositório. "
                        "Tentando restaurar o arquivo do Git…",
                        "aviso",
                    )
                    self._git(["checkout", "HEAD", "--", relativo])
                    if self._executavel_integro(relativo):
                        self._enviar_log(
                            "Executável restaurado pelo Git e verificado.", "ok"
                        )
                    else:
                        gerenciador_atualizado = False
                        self._enviar_log(
                            "Não foi possível obter um executável íntegro do Git. "
                            "A versão anterior do gerenciador foi restaurada; se o problema "
                            "continuar, rode no terminal: git checkout HEAD -- "
                            f"{relativo}",
                            "erro",
                        )
                if gerenciador_atualizado:
                    self._enviar_log(
                        "O GerenciadorCRM.exe também foi atualizado e verificado; "
                        "reabra o gerenciador para usar a nova versão.",
                        "aviso",
                    )

            arquivos: list[str] = []
            if antes and depois and antes != depois:
                resultado = self._git(["diff", "--name-only", f"{antes}..{depois}"])
                arquivos = [linha for linha in resultado.stdout.splitlines() if linha.strip()]
            if arquivos:
                self._enviar_log(f"{len(arquivos)} arquivo(s) alterado(s):", "info")
                for arquivo in arquivos[:30]:
                    self._enviar_log("   " + arquivo, "info")
                if len(arquivos) > 30:
                    self._enviar_log(f"   … e mais {len(arquivos) - 30} arquivo(s).", "info")
            relevantes = alteracoes_relevantes(arquivos)
            if "requirements.txt" in arquivos:
                self._enviar_log(
                    "requirements.txt mudou: reinstale as dependências com "
                    "pip install -r requirements.txt.",
                    "aviso",
                )
            if relevantes:
                self._enviar_log(
                    "As mudanças afetam o CRM; reinicie para aplicá-las.", "aviso"
                )
        except subprocess.TimeoutExpired:
            self._enviar_log("A operação com o Git demorou demais e foi interrompida.", "erro")
        except Exception as exc:  # pragma: no cover - defensivo
            self._enviar_log(f"Erro inesperado no git pull: {exc}", "erro")
        finally:
            if backup_exe is not None:
                if gerenciador_atualizado:
                    # Mantém o backup até o gerenciador ser relançado com sucesso.
                    self._exe_backup = backup_exe
                else:
                    restaurar_executavel(exe_atual, backup_exe)
                    self._exe_backup = None
            self._enviar("fim_git", (relevantes, gerenciador_atualizado))

    # -- configurações --------------------------------------------------------
    def abrir_configuracoes(self) -> None:
        if self._ocupado:
            return
        janela = tk.Toplevel(self)
        janela.title("Configurações")
        janela.transient(self)
        janela.grab_set()
        janela.resizable(False, False)
        janela.configure(bg=COR_FUNDO)

        quadro = ttk.Frame(janela, padding=14)
        quadro.pack(fill="both", expand=True)
        quadro.columnconfigure(1, weight=1)

        pasta_var = tk.StringVar(value=str(self._pasta or ""))
        python_var = tk.StringVar(value=self._python_config)
        porta_var = tk.StringVar(value=str(porta_configurada(self._config) or ""))

        ttk.Label(quadro, text="Pasta do projeto (contém o app.py)").grid(
            row=0, column=0, sticky="w", pady=(0, 6)
        )
        entrada_pasta = ttk.Entry(quadro, textvariable=pasta_var, width=52)
        entrada_pasta.grid(row=0, column=1, sticky="ew", padx=(8, 4), pady=(0, 6))

        def escolher_pasta() -> None:
            escolhida = filedialog.askdirectory(
                title="Pasta do CRM (onde está o app.py)",
                initialdir=pasta_var.get() or str(Path.cwd()),
                parent=janela,
            )
            if escolhida:
                pasta_var.set(escolhida)
                porta_var.set(str(ler_porta(Path(escolhida))))

        ttk.Button(quadro, text="Procurar…", command=escolher_pasta).grid(
            row=0, column=2, sticky="ew", pady=(0, 6)
        )

        ttk.Label(quadro, text="Python (opcional)").grid(row=1, column=0, sticky="w", pady=(0, 6))
        entrada_python = ttk.Entry(quadro, textvariable=python_var, width=52)
        entrada_python.grid(row=1, column=1, sticky="ew", padx=(8, 4), pady=(0, 6))

        def escolher_python() -> None:
            escolhido = filedialog.askopenfilename(
                title="Selecione o python.exe",
                filetypes=[("Executável", "*.exe"), ("Todos os arquivos", "*.*")],
                parent=janela,
            )
            if escolhido:
                python_var.set(escolhido)

        ttk.Button(quadro, text="Procurar…", command=escolher_python).grid(
            row=1, column=2, sticky="ew", pady=(0, 6)
        )

        ttk.Label(quadro, text="Porta (vazio = automática)").grid(row=2, column=0, sticky="w")
        ttk.Entry(quadro, textvariable=porta_var, width=10).grid(
            row=2, column=1, sticky="w", padx=(8, 4)
        )

        ttk.Label(
            quadro,
            text="Deixe o Python em branco para usar .venv, PATH ou o launcher py.",
            foreground=COR_SUAVE,
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(8, 12))

        def detectar() -> None:
            pasta = detectar_pasta_projeto(None) or self._pasta
            if pasta:
                pasta_var.set(str(pasta))
                porta_var.set(str(ler_porta(pasta)))
            python, _ = localizar_python(Path(pasta_var.get()) if pasta_var.get() else None, "")
            if python:
                python_var.set(python)

        def salvar() -> None:
            texto_pasta = pasta_var.get().strip().strip('"')
            pasta = Path(texto_pasta).expanduser() if texto_pasta else None
            if not pasta or not (pasta / APP_PY).is_file():
                messagebox.showerror(
                    "Pasta inválida",
                    f"Selecione a pasta que contém o arquivo {APP_PY}.",
                    parent=janela,
                )
                return
            texto_python = python_var.get().strip().strip('"')
            if texto_python and not Path(texto_python).expanduser().is_file():
                messagebox.showerror(
                    "Python inválido",
                    "O caminho informado para o Python não existe.",
                    parent=janela,
                )
                return
            texto_porta = porta_var.get().strip()
            porta = 0
            if texto_porta:
                if not texto_porta.isdigit() or not (1 <= int(texto_porta) <= 65535):
                    messagebox.showerror(
                        "Porta inválida", "Informe um número entre 1 e 65535.", parent=janela
                    )
                    return
                porta = int(texto_porta)

            anterior = self._pasta.resolve() if self._pasta else None
            mudou = pasta.resolve() != anterior or (porta or ler_porta(pasta)) != self._porta
            em_execucao = self._processo is not None and self._processo.poll() is None

            self._pasta = pasta.resolve()
            self._python_config = texto_python
            self._config["pasta"] = str(self._pasta)
            self._config["python"] = texto_python
            self._config["porta"] = porta
            salvar_config(self._config)
            self._porta = porta or ler_porta(self._pasta)
            self._atualizar_rotulos()
            janela.destroy()
            self._log("Configurações salvas.", "ok")
            self._atualizar_status()
            self._atualizar_info_git()
            if mudou and em_execucao:
                messagebox.showwarning(
                    TITULO,
                    "As configurações mudaram, mas o CRM atual continua no processo anterior.\n"
                    "Use Reiniciar CRM para aplicar.",
                    parent=self,
                )

        rodape = ttk.Frame(quadro)
        rodape.grid(row=4, column=0, columnspan=3, sticky="e", pady=(12, 0))
        ttk.Button(rodape, text="Detectar automaticamente", command=detectar).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(rodape, text="Cancelar", command=janela.destroy).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(rodape, text="Salvar", command=salvar).pack(side="left")

        entrada_pasta.focus_set()

    # -- encerramento ---------------------------------------------------------
    def _ao_fechar(self) -> None:
        if self._ocupado:
            messagebox.showinfo(
                TITULO, "Aguarde a operação atual terminar antes de fechar.", parent=self
            )
            return
        if self._processo is not None and self._processo.poll() is None:
            if not messagebox.askyesno(
                "Fechar gerenciador",
                "O CRM continuará em execução.\n\nFechar apenas esta janela?",
                parent=self,
            ):
                return
        self._fechar_log_crm()
        self.destroy()


class _Tooltip:
    """Dica simples exibida ao passar o mouse sobre um botão."""

    def __init__(self, widget: tk.Widget, texto: str, atraso: int = 450) -> None:
        self._widget = widget
        self._texto = texto
        self._atraso = atraso
        self._janela: tk.Toplevel | None = None
        self._agendado: str | None = None
        widget.bind("<Enter>", self._agendar, add="+")
        widget.bind("<Leave>", self._esconder, add="+")
        widget.bind("<ButtonPress>", self._esconder, add="+")

    def _agendar(self, _evento=None) -> None:
        self._cancelar()
        self._agendado = self._widget.after(self._atraso, self._mostrar)

    def _cancelar(self) -> None:
        if self._agendado is not None:
            try:
                self._widget.after_cancel(self._agendado)
            except tk.TclError:
                pass
            self._agendado = None

    def _mostrar(self) -> None:
        self._agendado = None
        if self._janela is not None or not self._texto:
            return
        try:
            x = self._widget.winfo_rootx() + 12
            y = self._widget.winfo_rooty() + self._widget.winfo_height() + 6
        except tk.TclError:
            return
        janela = tk.Toplevel(self._widget)
        janela.wm_overrideredirect(True)
        janela.wm_geometry(f"+{x}+{y}")
        tk.Label(
            janela, text=self._texto, bg="#fffbe6", fg=COR_TEXTO,
            relief="solid", borderwidth=1, font=("Segoe UI", 8), padx=6, pady=3,
        ).pack()
        self._janela = janela

    def _esconder(self, _evento=None) -> None:
        self._cancelar()
        if self._janela is not None:
            self._janela.destroy()
            self._janela = None


def main() -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    app = GerenciadorCRM()
    app.mainloop()


if __name__ == "__main__":
    main()
