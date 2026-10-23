from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

DIAGNOSTICO_VERSAO = "1.0.0"
DATA_REFERENCIA = "2026-10-20"
PORTA_CRM = 5000
LIMITE_ARQUIVOS_ANEXOS = 50000
LIMITE_TEXTO = 96 * 1024
CRIAR_JANELA = getattr(subprocess, "CREATE_NO_WINDOW", 0)
SEM_PAUSA = False

TABELAS_ESPERADAS = [
    "propostas",
    "historico",
    "notificacoes_importantes",
    "notificacoes_leitura",
    "configuracoes",
    "anotacoes",
    "anexos",
    "status_etapas",
    "modelos_mensagens",
    "modelos_gerador_mensagens",
    "modelos_excluidos",
    "clientes",
    "tarefas",
    "nutricao_retornos",
    "dashboard_campos",
    "dashboard_valores_manuais",
    "dashboard_componentes",
]

COLUNAS_ESPERADAS: dict[str, list[str]] = {
    "propostas": [
        "id", "cliente_id", "nome", "cpf", "nascimento", "nb_matricula", "especie",
        "numero_proposta", "numero_port_vinculada", "numero_refin_vinculada",
        "portabilidade_id", "tipo_cliente", "banco_atual", "banco_destino",
        "banco_digitado", "produto", "promotora", "beneficio_bloqueado",
        "valor_caiu_promotora", "valor_sacado", "data_verificacao", "parcela_atual",
        "nova_parcela", "troco", "comissao_percentual", "comissao", "margem_apos",
        "status", "responsavel", "telefone", "endereco", "dados_bancarios",
        "data_criacao", "data_atualizacao", "data_encerramento", "proxima_acao",
        "data_retorno", "observacoes",
    ],
    "historico": ["id", "proposta_id", "data_hora", "status_anterior", "status_novo", "observacao"],
    "notificacoes_importantes": ["id", "proposta_id", "proposta_nome", "proposta_numero", "tipo", "titulo", "mensagem", "data_hora"],
    "notificacoes_leitura": ["id", "lido_ate"],
    "configuracoes": ["chave", "valor", "atualizado_em"],
    "anotacoes": ["id", "proposta_id", "data_hora", "texto"],
    "anexos": ["id", "proposta_id", "nome_original", "nome_arquivo", "caminho", "data_upload"],
    "status_etapas": ["id", "nome", "funil", "grupo", "ordem", "ativo"],
    "modelos_mensagens": ["nome", "texto", "ordem", "data_atualizacao"],
    "modelos_gerador_mensagens": ["nome", "texto", "ordem", "data_atualizacao"],
    "modelos_excluidos": ["contexto", "nome", "data_exclusao"],
    "clientes": ["id", "nome", "cpf", "nascimento", "nb_matricula", "especie", "telefone", "tipo_cliente", "endereco", "dados_bancarios", "data_criacao", "data_atualizacao"],
    "tarefas": ["id", "titulo", "descricao", "data_tarefa", "horario", "prioridade", "status", "categoria", "proposta_id", "criado_em", "concluido_em", "atualizado_em", "notificar", "notificado_em"],
    "nutricao_retornos": ["funil", "cliente_chave", "dia", "registrado_em"],
    "dashboard_campos": ["id", "nome", "tipo", "modalidade", "configuracao_json", "cor", "ordem", "ativo", "criado_em", "atualizado_em"],
    "dashboard_valores_manuais": ["campo_id", "mes", "valor", "atualizado_em"],
    "dashboard_componentes": ["chave", "nome", "cor", "ordem", "ativo", "atualizado_em"],
}

COLUNAS_MIGRADAS: dict[str, set[str]] = {
    "propostas": {
        "cliente_id", "numero_proposta", "numero_port_vinculada", "numero_refin_vinculada",
        "portabilidade_id", "comissao", "comissao_percentual", "promotora",
        "beneficio_bloqueado", "banco_digitado", "valor_caiu_promotora", "valor_sacado",
        "data_verificacao", "data_encerramento", "endereco", "dados_bancarios",
        "especie", "nascimento",
    },
    "clientes": {"nascimento", "especie"},
    "status_etapas": {"funil"},
    "nutricao_retornos": {"funil"},
    "tarefas": {
        "titulo", "descricao", "data_tarefa", "horario", "prioridade", "status",
        "categoria", "proposta_id", "criado_em", "concluido_em", "atualizado_em",
        "notificar", "notificado_em",
    },
}

_PADRAO_SEGREDO = re.compile(
    r"(?im)^(\s*(?:@?\s*set\s+\"?|export\s+)?)"
    r"([A-Za-z_][A-Za-z0-9_]*(?:SECRET|TOKEN|PASSWORD|PASS|SENHA|PRIVATE_KEY|ACCESS_KEY)[A-Za-z0-9_]*)"
    r"\s*=\s*(.*)$"
)


def agora_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def formatar_bytes(valor: Any) -> str:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return "desconhecido"
    for unidade in ("B", "KB", "MB", "GB"):
        if numero < 1024 or unidade == "GB":
            return f"{numero:.1f} {unidade}" if unidade != "B" else f"{int(numero)} B"
        numero /= 1024
    return f"{numero:.1f} GB"


def sha256_arquivo(caminho: Path | str, normalizar: bool = False) -> str | None:
    try:
        if normalizar:
            dados = Path(caminho).read_bytes().replace(b"\r\n", b"\n")
            return hashlib.sha256(dados).hexdigest()
        digest = hashlib.sha256()
        with open(caminho, "rb") as arquivo:
            for bloco in iter(lambda: arquivo.read(1024 * 1024), b""):
                digest.update(bloco)
        return digest.hexdigest()
    except OSError:
        return None


def contar_linhas(caminho: Path | str) -> int | None:
    try:
        with open(caminho, "rb") as arquivo:
            return sum(1 for _ in arquivo)
    except OSError:
        return None


def ler_texto(caminho: Path | str, limite: int = LIMITE_TEXTO) -> str | None:
    try:
        dados = Path(caminho).read_bytes()[:limite]
    except OSError:
        return None
    if b"\x00" in dados[:4096]:
        return None
    try:
        return dados.decode("utf-8-sig")
    except UnicodeDecodeError:
        pass
    try:
        return dados.decode("cp1252")
    except UnicodeDecodeError:
        return dados.decode("latin-1", errors="replace")


def redigir_segredos(texto: str | None) -> str | None:
    if not texto:
        return texto
    texto = _PADRAO_SEGREDO.sub(lambda m: f"{m.group(1)}{m.group(2)}=***", texto)
    texto = re.sub(r"(?i)(password|senha|token|secret|api[_-]?key)\s*[:=]\s*\S+", r"\1=***", texto)
    return texto


def redigir_variaveis(variaveis: dict[str, str]) -> dict[str, str]:
    padrao = re.compile(r"(?i)(SECRET|TOKEN|PASSWORD|PASS|SENHA|PRIVATE_KEY|ACCESS_KEY)")
    return {chave: ("***" if padrao.search(chave) else valor) for chave, valor in variaveis.items()}


def redigir_url(url: str) -> str:
    return re.sub(r"(https?://)[^/@\s]+@", r"\1***@", url)


def redigir_caminho_usuario(texto: str) -> str:
    try:
        home = str(Path.home())
    except OSError:
        home = ""
    for variante in {home, home.replace("\\", "/")}:
        if variante:
            texto = texto.replace(variante, "%USERPROFILE%")
    usuario = os.environ.get("USERNAME")
    if usuario:
        texto = re.sub(r"(?i)([A-Z]:\\Users\\)" + re.escape(usuario), r"\1<usuario>", texto)
    return texto


def redigir_dados(obj: Any) -> Any:
    if isinstance(obj, str):
        return redigir_caminho_usuario(obj)
    if isinstance(obj, list):
        return [redigir_dados(item) for item in obj]
    if isinstance(obj, dict):
        return {chave: redigir_dados(valor) for chave, valor in obj.items()}
    return obj


def executar(comando: list[str], timeout: int = 30) -> subprocess.CompletedProcess[str] | None:
    opcoes: dict[str, Any] = {
        "capture_output": True,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
        "timeout": timeout,
    }
    if os.name == "nt":
        opcoes["creationflags"] = CRIAR_JANELA
    try:
        return subprocess.run(comando, **opcoes)
    except (OSError, subprocess.SubprocessError):
        return None


def carregar_versoes() -> tuple[dict[str, list[dict[str, str]]], dict[str, Any]]:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    caminho = base / "versoes_conhecidas.json"
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        if isinstance(dados, dict) and isinstance(dados.get("versoes"), dict):
            return dados["versoes"], dados
    except (OSError, ValueError):
        pass
    return {}, {}


def expandir(valor: str, pasta: Path, variaveis: dict[str, str]) -> str:
    texto = str(valor)
    texto = re.sub(r"(?i)%~dp0", lambda _m: str(pasta) + os.sep, texto)
    superiores = {chave.upper(): val for chave, val in variaveis.items()}

    def substituir(match: re.Match[str]) -> str:
        nome = match.group(1)
        if nome.upper() == "CD":
            return str(pasta)
        return str(superiores.get(nome.upper(), match.group(0)))

    texto = re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", substituir, texto)
    return texto.strip().strip('"')


def resolver_caminho(valor: str | None, pasta: Path, variaveis: dict[str, str]) -> Path | None:
    if not valor:
        return None
    texto = expandir(valor, pasta, variaveis)
    if not texto:
        return None
    try:
        caminho = Path(texto).expanduser()
        if not caminho.is_absolute():
            caminho = pasta / caminho
        return caminho.resolve()
    except (OSError, ValueError):
        return None


def validar_crm(valor: str | Path) -> tuple[Path | None, list[Path]]:
    try:
        pasta = Path(valor).expanduser().resolve()
    except (OSError, ValueError):
        return None, []
    if (pasta / "app.py").is_file():
        return pasta, []
    candidatos: list[Path] = []
    try:
        for filho in pasta.iterdir():
            if filho.is_dir() and (filho / "app.py").is_file():
                candidatos.append(filho.resolve())
    except OSError:
        pass
    candidatos = sorted(set(candidatos), key=lambda item: item.name.lower())
    if len(candidatos) == 1:
        return candidatos[0], []
    return None, candidatos


def selecionar_pasta(args: argparse.Namespace) -> Path | None:
    if args.pasta:
        pasta, candidatos = validar_crm(args.pasta)
        if pasta:
            return pasta
        if candidatos:
            print("Encontrei mais de uma pasta com app.py:")
            for candidato in candidatos:
                print(f"  - {candidato}")
        else:
            print(f"Não encontrei app.py em: {args.pasta}")
        return None

    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path(__file__).resolve().parent
    for candidato in (base, Path.cwd()):
        pasta, _ = validar_crm(candidato)
        if pasta:
            return pasta

    escolhida: str | None = None
    try:
        import tkinter as tk
        from tkinter import filedialog

        raiz = tk.Tk()
        raiz.withdraw()
        try:
            raiz.attributes("-topmost", True)
        except Exception:
            pass
        escolhida = filedialog.askdirectory(
            title="Selecione a pasta do CRM (onde está o app.py)",
            mustexist=True,
        )
        raiz.destroy()
    except Exception:
        escolhida = None

    for tentativa in range(3):
        if tentativa > 0 or not escolhida:
            try:
                escolhida = input("Digite a pasta do CRM (onde está o app.py): ").strip()
            except EOFError:
                return None
        if not escolhida:
            return None
        pasta, candidatos = validar_crm(escolhida)
        if pasta:
            return pasta
        if candidatos:
            print("Encontrei estas pastas com app.py:")
            for candidato in candidatos:
                print(f"  - {candidato}")
        else:
            print("Não encontrei app.py nessa pasta.")
        escolhida = None
    return None


def parse_env(texto: str) -> dict[str, str]:
    variaveis: dict[str, str] = {}
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("#"):
            continue
        if linha.lower().startswith("export "):
            linha = linha[7:].strip()
        if "=" not in linha:
            continue
        chave, valor = linha.split("=", 1)
        chave = chave.strip()
        valor = valor.strip().strip('"').strip("'")
        if chave:
            variaveis[chave] = valor
    return variaveis


def parse_bat(texto: str) -> dict[str, str]:
    variaveis: dict[str, str] = {}
    padrao = re.compile(
        r'(?i)^@?\s*set\s+(?:"([^"]+)=([^"]*)"|([^=\s]+)=(.*))$'
    )
    for linha in texto.splitlines():
        linha = linha.strip()
        if not linha or linha.startswith("::") or re.match(r"(?i)^rem\b", linha):
            continue
        match = padrao.match(linha)
        if not match:
            continue
        if match.group(1) is not None:
            chave, valor = match.group(1), match.group(2)
        else:
            chave, valor = match.group(3), match.group(4)
        chave = chave.strip()
        if chave:
            variaveis[chave] = valor.strip()
    return variaveis


def coletar_fontes(pasta: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, str]]:
    processo_raw = {chave: valor for chave, valor in os.environ.items() if chave.startswith("CRM_")}

    dotenv_raw: dict[str, str] = {}
    dotenv_path = pasta / ".env"
    dotenv_publico: dict[str, Any] = {"arquivo": str(dotenv_path), "existe": dotenv_path.is_file(), "variaveis": {}}
    if dotenv_path.is_file():
        texto = ler_texto(dotenv_path)
        if texto:
            dotenv_raw = parse_env(texto)
            dotenv_publico["variaveis"] = redigir_variaveis(dotenv_raw)

    bats: list[dict[str, Any]] = []
    arquivos_bat = sorted(
        list(pasta.glob("*.bat")) + list(pasta.glob("*.cmd")),
        key=lambda item: item.name.lower(),
    )
    for caminho in arquivos_bat[:20]:
        texto = ler_texto(caminho)
        if texto is None:
            continue
        variaveis = parse_bat(texto)
        try:
            tamanho = caminho.stat().st_size
        except OSError:
            tamanho = None
        bats.append(
            {
                "nome": caminho.name,
                "tamanho": tamanho,
                "conteudo_redigido": redigir_segredos(texto),
                "variaveis": redigir_variaveis(variaveis),
                "invoca_app": bool(re.search(r"(?i)\bapp\.py\b", texto)),
                "variaveis_raw": variaveis,
            }
        )

    bat_raw: dict[str, str] = {}
    bat_origem: dict[str, str] = {}
    for item in sorted(bats, key=lambda b: (b["nome"].lower() == "crm.bat", b["nome"].lower())):
        for chave, valor in item["variaveis_raw"].items():
            bat_raw[chave] = valor
            bat_origem[chave] = item["nome"]

    bats_publicos = [
        {chave: valor for chave, valor in item.items() if chave != "variaveis_raw"}
        for item in bats
    ]
    fontes_publicas = {
        "processo": redigir_variaveis(processo_raw),
        "dotenv": dotenv_publico,
        "bat": redigir_variaveis(bat_raw),
        "bats": bats_publicos,
    }
    fontes_raw = {
        "processo": processo_raw,
        "dotenv": dotenv_raw,
        "bat": bat_raw,
        "bat_origem": bat_origem,
    }
    variaveis_expansao = {**os.environ, **bat_raw, **dotenv_raw, **processo_raw}
    return fontes_publicas, fontes_raw, variaveis_expansao


def resolver_config(nome: str, fontes_raw: dict[str, Any]) -> tuple[str | None, str | None]:
    for chave, rotulo in (("processo", "variável de ambiente"), ("dotenv", ".env"), ("bat", "arquivo .bat")):
        valor = fontes_raw.get(chave, {}).get(nome)
        if valor:
            if chave == "bat":
                rotulo = fontes_raw.get("bat_origem", {}).get(nome, rotulo)
            return str(valor), str(rotulo)
    return None, None


def resolver_banco(
    pasta: Path, fontes_raw: dict[str, Any], variaveis: dict[str, str]
) -> tuple[Path | None, str | None, list[dict[str, Any]]]:
    candidatos: list[dict[str, Any]] = []
    valor, origem = resolver_config("CRM_DATABASE", fontes_raw)
    if valor:
        caminho = resolver_caminho(valor, pasta, variaveis)
        if caminho:
            candidatos.append({"caminho": caminho, "origem": origem})

    candidatos.append({"caminho": (pasta / "database.db").resolve(), "origem": "pasta do CRM"})
    candidatos.append({"caminho": (pasta / "instance" / "database.db").resolve(), "origem": "pasta instance"})

    vistos: set[str] = set()
    unicos: list[dict[str, Any]] = []
    for candidato in candidatos:
        chave = str(candidato["caminho"]).lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        candidato["existe"] = candidato["caminho"].is_file()
        unicos.append(candidato)

    for candidato in unicos:
        if candidato["existe"]:
            return candidato["caminho"], candidato["origem"], unicos

    achados: list[Path] = []
    for padrao in ("*.db", "*.sqlite", "*.sqlite3"):
        try:
            achados.extend(p for p in pasta.glob(padrao) if p.is_file())
        except OSError:
            pass
    achados = sorted(set(achados), key=lambda item: item.stat().st_size, reverse=True)
    for caminho in achados:
        if caminho.name.lower() == "database_copia.db":
            continue
        candidato = {"caminho": caminho.resolve(), "origem": "busca automática", "existe": True}
        unicos.append(candidato)
        return candidato["caminho"], candidato["origem"], unicos

    return None, None, unicos


def resolver_anexos(
    pasta: Path, fontes_raw: dict[str, Any], variaveis: dict[str, str], banco: dict[str, Any]
) -> tuple[Path | None, str | None, list[dict[str, Any]]]:
    candidatos: list[dict[str, Any]] = []
    valor_db = (banco.get("configuracoes") or {}).get("anexos_base_dir")
    if valor_db:
        caminho = resolver_caminho(str(valor_db), pasta, variaveis)
        if caminho:
            candidatos.append({"caminho": caminho, "origem": "Configurações do CRM"})

    valor, origem = resolver_config("CRM_ANEXOS_DIR", fontes_raw)
    if valor:
        caminho = resolver_caminho(valor, pasta, variaveis)
        if caminho:
            candidatos.append({"caminho": caminho, "origem": origem})

    for nome in ("documentos", "anexos", "uploads", "clientes"):
        candidatos.append({"caminho": (pasta / nome).resolve(), "origem": f"pasta {nome}"})

    vistos: set[str] = set()
    unicos: list[dict[str, Any]] = []
    for candidato in candidatos:
        chave = str(candidato["caminho"]).lower()
        if chave in vistos:
            continue
        vistos.add(chave)
        candidato["existe"] = candidato["caminho"].exists()
        unicos.append(candidato)

    for candidato in unicos:
        if candidato["existe"]:
            return candidato["caminho"], candidato["origem"], unicos
    return (unicos[0]["caminho"] if unicos else None), None, unicos


def caminho_uri(caminho: Path) -> str:
    texto = str(Path(caminho).resolve()).replace("\\", "/")
    return "file:" + quote(texto, safe="/:") + "?mode=ro"


def quotar_identificador(nome: str) -> str:
    return '"' + nome.replace('"', '""') + '"'


def coletar_banco(caminho: Path | None) -> dict[str, Any]:
    if caminho is None:
        return {"existe": False, "erro": "Banco de dados não localizado."}
    caminho = Path(caminho)
    info: dict[str, Any] = {"caminho": str(caminho), "existe": caminho.is_file()}
    if not info["existe"]:
        info["erro"] = "Arquivo não encontrado."
        return info
    try:
        stat = caminho.stat()
        info["tamanho"] = stat.st_size
        info["modificado_em"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        pass
    info["sha256"] = sha256_arquivo(caminho)

    conexao: sqlite3.Connection | None = None
    try:
        conexao = sqlite3.connect(caminho_uri(caminho), uri=True, timeout=5)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA query_only = ON")
        conexao.execute("PRAGMA busy_timeout = 5000")

        info["user_version"] = conexao.execute("PRAGMA user_version").fetchone()[0]
        info["application_id"] = conexao.execute("PRAGMA application_id").fetchone()[0]
        try:
            info["encoding"] = conexao.execute("PRAGMA encoding").fetchone()[0]
            info["journal_mode"] = conexao.execute("PRAGMA journal_mode").fetchone()[0]
        except sqlite3.Error:
            pass

        try:
            linhas_integridade = conexao.execute("PRAGMA integrity_check").fetchall()
            valores = [str(linha[0]) for linha in linhas_integridade]
            info["integridade"] = "\n".join(valores)[:4000]
        except sqlite3.Error as exc:
            info["integridade"] = f"erro: {exc}"

        try:
            violacoes = conexao.execute("PRAGMA foreign_key_check").fetchall()
            info["fk_violacoes"] = len(violacoes)
            info["fk_exemplos"] = [dict(linha) for linha in violacoes[:20]]
        except sqlite3.Error as exc:
            info["fk_violacoes"] = None
            info["fk_erro"] = str(exc)

        objetos = conexao.execute(
            "SELECT type, name, tbl_name, sql FROM sqlite_master "
            "WHERE type IN ('table','index','view','trigger') "
            "ORDER BY type, name"
        ).fetchall()
        info["objetos"] = [
            {"tipo": linha["type"], "nome": linha["name"], "tabela": linha["tbl_name"]}
            for linha in objetos
        ]
        info["schema_sql"] = "\n\n".join(
            linha["sql"].rstrip(";") + ";"
            for linha in objetos
            if linha["sql"]
            and linha["type"] in ("table", "index", "view", "trigger")
            and not str(linha["name"]).startswith("sqlite_")
        )

        tabelas: dict[str, Any] = {}
        for linha in objetos:
            if linha["type"] != "table" or str(linha["name"]).startswith("sqlite_"):
                continue
            nome = str(linha["name"])
            colunas = []
            try:
                for coluna in conexao.execute(f"PRAGMA table_info({quotar_identificador(nome)})").fetchall():
                    colunas.append(
                        {
                            "nome": coluna["name"],
                            "tipo": coluna["type"],
                            "notnull": bool(coluna["notnull"]),
                            "padrao": coluna["dflt_value"],
                            "pk": bool(coluna["pk"]),
                        }
                    )
            except sqlite3.Error as exc:
                colunas = [{"erro": str(exc)}]
            try:
                linhas_tabela = conexao.execute(
                    f"SELECT COUNT(*) FROM {quotar_identificador(nome)}"
                ).fetchone()[0]
            except sqlite3.Error:
                linhas_tabela = None
            indices = []
            try:
                for indice in conexao.execute(f"PRAGMA index_list({quotar_identificador(nome)})").fetchall():
                    chaves = set(indice.keys())
                    indices.append(
                        {
                            "nome": indice["name"],
                            "unico": bool(indice["unique"]),
                            "origem": indice["origin"],
                            "parcial": bool(indice["partial"]) if "partial" in chaves else False,
                        }
                    )
            except sqlite3.Error:
                pass
            tabelas[nome] = {"colunas": colunas, "linhas": linhas_tabela, "indices": indices}
        info["tabelas"] = tabelas
        info["contagens"] = {nome: dados.get("linhas") for nome, dados in tabelas.items()}

        configuracao: dict[str, str] = {}
        try:
            for linha in conexao.execute("SELECT chave, valor FROM configuracoes").fetchall():
                configuracao[str(linha["chave"])] = str(linha["valor"])
        except sqlite3.Error:
            pass
        info["configuracoes"] = {
            "chaves": sorted(configuracao),
            "anexos_base_dir": configuracao.get("anexos_base_dir"),
        }
    except sqlite3.Error as exc:
        info["erro"] = str(exc)
    finally:
        if conexao is not None:
            try:
                conexao.close()
            except sqlite3.Error:
                pass
    return info


def coletar_json_info(caminho: Path) -> dict[str, Any]:
    info: dict[str, Any] = {"caminho": str(caminho), "existe": caminho.is_file()}
    if not info["existe"]:
        return info
    try:
        stat = caminho.stat()
        info["tamanho"] = stat.st_size
        info["sha256"] = sha256_arquivo(caminho)
    except OSError:
        pass
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8-sig"))
        info["json_valido"] = True
        info["tipo"] = type(dados).__name__
        info["quantidade"] = len(dados) if isinstance(dados, (dict, list)) else None
    except (OSError, ValueError) as exc:
        info["json_valido"] = False
        info["erro"] = str(exc)
    return info


def coletar_app(pasta: Path, mapa_versoes: dict[str, list[dict[str, str]]]) -> dict[str, Any]:
    caminho = pasta / "app.py"
    info: dict[str, Any] = {"caminho": str(caminho), "existe": caminho.is_file()}
    if not info["existe"]:
        return info
    try:
        stat = caminho.stat()
        info["tamanho"] = stat.st_size
        info["modificado_em"] = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    except OSError:
        pass
    info["sha256"] = sha256_arquivo(caminho)
    info["sha256_normalizado"] = sha256_arquivo(caminho, normalizar=True)
    info["linhas"] = contar_linhas(caminho)

    versoes = mapa_versoes.get(info["sha256_normalizado"] or "", [])
    info["versoes"] = versoes
    info["versao_conhecida"] = bool(versoes)

    requirements = pasta / "requirements.txt"
    info["requirements"] = ler_texto(requirements) if requirements.is_file() else None

    info["data"] = {
        "modelos_mensagens.json": coletar_json_info(pasta / "data" / "modelos_mensagens.json"),
        "inss_especies_beneficios.json": coletar_json_info(pasta / "data" / "inss_especies_beneficios.json"),
    }
    return info


def coletar_git(pasta: Path) -> dict[str, Any]:
    if not (pasta / ".git").exists():
        return {"repositorio_git": False}
    git = shutil.which("git")
    info: dict[str, Any] = {"repositorio_git": True, "git_disponivel": bool(git)}
    if not git:
        return info

    comando = [git, "-C", str(pasta)]
    processo = executar(comando + ["log", "-1", "--format=%H%n%ad%n%s", "--date=iso"], timeout=15)
    if processo and processo.returncode == 0:
        linhas = processo.stdout.splitlines()
        if len(linhas) >= 3:
            info["commit"] = linhas[0].strip()
            info["data"] = linhas[1].strip()
            info["assunto"] = linhas[2].strip()
    else:
        info["erro_log"] = ((processo.stderr or processo.stdout).strip() if processo else "git não executou")

    processo = executar(comando + ["status", "--porcelain"], timeout=20)
    if processo and processo.returncode == 0:
        linhas = [linha for linha in processo.stdout.splitlines() if linha.strip()]
        info["modificados"] = sum(1 for linha in linhas if not linha.startswith("??"))
        info["nao_rastreados"] = sum(1 for linha in linhas if linha.startswith("??"))
        info["sujo"] = bool(linhas)
    else:
        info["erro_status"] = ((processo.stderr or processo.stdout).strip() if processo else "git não executou")

    processo = executar(comando + ["remote", "get-url", "origin"], timeout=10)
    if processo and processo.returncode == 0:
        info["remoto"] = redigir_url(processo.stdout.strip())
    return info


def coletar_python(pasta: Path) -> dict[str, Any]:
    candidatos: list[dict[str, Any]] = []
    vistos: set[tuple[str, ...]] = set()

    def adicionar(rotulo: str, comando: list[str], existe: bool) -> None:
        chave = tuple(comando)
        if chave in vistos:
            return
        vistos.add(chave)
        candidatos.append({"rotulo": rotulo, "comando": comando, "existe": existe})

    for relativo in (
        ".venv/Scripts/python.exe",
        "venv/Scripts/python.exe",
        "env/Scripts/python.exe",
        ".venv/bin/python",
        "venv/bin/python",
        "env/bin/python",
    ):
        caminho = pasta / relativo
        adicionar(relativo, [str(caminho)], caminho.is_file())

    for nome in ("python", "python3"):
        caminho = shutil.which(nome)
        if caminho:
            adicionar(nome, [caminho], True)
    py = shutil.which("py")
    if py:
        adicionar("py -3", [py, "-3"], True)

    selecionado: dict[str, Any] | None = None
    for candidato in candidatos:
        if not candidato["existe"]:
            continue
        processo = executar(candidato["comando"] + ["--version"], timeout=15)
        if processo is None:
            candidato["erro"] = "não executou"
            continue
        texto = ((processo.stdout or "") + (processo.stderr or "")).strip()
        candidato["versao"] = texto
        if processo.returncode == 0 and "python" in texto.lower():
            selecionado = candidato
            break

    info: dict[str, Any] = {"candidatos": candidatos, "selecionado": None}
    if selecionado is None:
        info["erro"] = "Nenhum Python executável foi encontrado."
        return info

    base = list(selecionado["comando"])
    info["selecionado"] = {
        "rotulo": selecionado["rotulo"],
        "comando": selecionado["comando"],
        "executavel": " ".join(selecionado["comando"]),
        "versao": selecionado.get("versao"),
    }

    processo = executar(
        base + ["-c", "import sys, platform; print(sys.version); print(sys.executable); print(platform.platform())"],
        timeout=20,
    )
    if processo and processo.returncode == 0:
        info["selecionado"]["detalhes"] = processo.stdout.splitlines()

    processo = executar(base + ["-m", "pip", "--version"], timeout=20)
    if processo and processo.returncode == 0:
        info["pip"] = processo.stdout.strip()
    else:
        info["pip_erro"] = ((processo.stderr or processo.stdout).strip() if processo else "não executou")

    processo = executar(base + ["-m", "pip", "freeze"], timeout=90)
    if processo and processo.returncode == 0:
        info["pacotes"] = [linha.strip() for linha in processo.stdout.splitlines() if linha.strip()]
    else:
        info["pacotes_erro"] = ((processo.stderr or processo.stdout).strip() if processo else "não executou")

    codigo = (
        "import importlib.metadata as m\n"
        "for nome in ('Flask','openpyxl','pdfplumber','Werkzeug','Pillow','pdfminer.six','pypdfium2'):\n"
        "    try:\n"
        "        print(f'{nome}=={m.version(nome)}')\n"
        "    except Exception:\n"
        "        print(f'{nome}=AUSENTE')\n"
    )
    processo = executar(base + ["-c", codigo], timeout=30)
    if processo and processo.returncode == 0:
        info["versoes_pacotes"] = [linha.strip() for linha in processo.stdout.splitlines() if linha.strip()]
    else:
        info["versoes_pacotes_erro"] = ((processo.stderr or processo.stdout).strip() if processo else "não executou")

    return info


def coletar_ambiente() -> dict[str, Any]:
    crm = redigir_variaveis(
        {chave: valor for chave, valor in os.environ.items() if chave.startswith("CRM_")}
    )
    extras = {
        chave: os.environ[chave]
        for chave in ("VIRTUAL_ENV", "PYTHONPATH", "FLASK_ENV", "FLASK_DEBUG")
        if os.environ.get(chave)
    }
    return {
        "crm": crm,
        "extras": extras,
        "crm_secret_key_definida": bool(os.environ.get("CRM_SECRET_KEY")),
    }


def coletar_inicializacao(pasta: Path, fontes_publicas: dict[str, Any]) -> dict[str, Any]:
    bats = fontes_publicas.get("bats", [])
    scripts: list[dict[str, Any]] = []
    for padrao in ("*.ps1", "*.vbs"):
        try:
            arquivos = sorted(pasta.glob(padrao), key=lambda item: item.name.lower())[:10]
        except OSError:
            arquivos = []
        for caminho in arquivos:
            texto = ler_texto(caminho)
            try:
                tamanho = caminho.stat().st_size
            except OSError:
                tamanho = None
            scripts.append(
                {
                    "nome": caminho.name,
                    "tamanho": tamanho,
                    "conteudo_redigido": redigir_segredos(texto) if texto else None,
                }
            )

    atalhos: list[str] = []
    try:
        atalhos = [caminho.name for caminho in sorted(pasta.glob("*.lnk"))[:20]]
    except OSError:
        pass

    startup: list[str] = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        pasta_startup = Path(appdata) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup"
        if pasta_startup.is_dir():
            try:
                startup = [caminho.name for caminho in sorted(pasta_startup.iterdir())][:30]
            except OSError:
                pass

    crm_bat = next((item for item in bats if item["nome"].lower() == "crm.bat"), None)
    if crm_bat:
        provavel = "crm.bat"
    elif (pasta / ".venv").exists():
        provavel = "atalho/terminal usando .venv"
    elif (pasta / "venv").exists():
        provavel = "atalho/terminal usando venv"
    else:
        provavel = "não identificado"

    return {
        "bats": bats,
        "scripts": scripts,
        "atalhos": atalhos,
        "startup": startup,
        "crm_bat_existe": bool(crm_bat),
        "invoca_app": any(item.get("invoca_app") for item in bats),
        "provavel": provavel,
    }


def contar_pasta(caminho: Path, limite: int = 200000) -> tuple[int, int, bool]:
    quantidade = 0
    total = 0
    for raiz, diretorios, arquivos in os.walk(caminho):
        diretorios[:] = [nome for nome in diretorios if not (Path(raiz) / nome).is_symlink()]
        for nome in arquivos:
            arquivo = Path(raiz) / nome
            try:
                if arquivo.is_symlink():
                    continue
                total += arquivo.stat().st_size
                quantidade += 1
            except OSError:
                pass
            if quantidade >= limite:
                return quantidade, total, True
    return quantidade, total, False


def coletar_pasta(pasta: Path) -> dict[str, Any]:
    # Só nomes conhecidos entram no relatório. Arquivos soltos na raiz podem
    # ter nomes de clientes e não são necessários para o diagnóstico.
    nomes_conhecidos = {
        "app.py", "requirements.txt", "README.md", "DESIGN_SYSTEM.md",
        "SECURITY.md", "AGENTS.md", "database.db", "crm.bat", ".env",
        "templates", "static", "data", "integrations", "backups",
        "documentos", "anexos", "uploads", ".venv", "venv", "env",
        ".git", "__pycache__", "tests", "instance",
        "crm-diagnostico.exe", "crm-diagnostico.zip",
    }
    entradas: list[dict[str, Any]] = []
    outros = 0
    try:
        for caminho in sorted(pasta.iterdir(), key=lambda item: item.name.lower()):
            if caminho.name not in nomes_conhecidos:
                outros += 1
                continue
            item: dict[str, Any] = {
                "nome": caminho.name,
                "tipo": "pasta" if caminho.is_dir() else "arquivo",
            }
            if caminho.is_file():
                try:
                    item["tamanho"] = caminho.stat().st_size
                except OSError:
                    pass
            entradas.append(item)
    except OSError as exc:
        entradas = [{"erro": str(exc)}]

    contagens: dict[str, Any] = {}
    for nome in ("static", "templates", "data", "integrations"):
        caminho = pasta / nome
        if caminho.is_dir():
            quantidade, total, truncado = contar_pasta(caminho)
            contagens[nome] = {"arquivos": quantidade, "bytes": total, "truncado": truncado}

    presentes = {
        nome: (pasta / nome).exists()
        for nome in (
            "app.py", "requirements.txt", "README.md", "database.db", "templates",
            "static", "data", "integrations", "backups", "documentos", ".venv",
            ".git", "crm.bat", ".env",
        )
    }
    return {
        "entradas": entradas,
        "outros_arquivos_na_raiz": outros,
        "contagens": contagens,
        "presentes": presentes,
    }


def coletar_anexos(caminho: Path | None) -> dict[str, Any]:
    if caminho is None:
        return {"existe": False}
    caminho = Path(caminho)
    info: dict[str, Any] = {"caminho": str(caminho), "existe": caminho.exists()}
    if not info["existe"]:
        return info
    if caminho.is_file():
        try:
            info.update({"tipo": "arquivo", "arquivos": 1, "bytes": caminho.stat().st_size})
        except OSError:
            info["tipo"] = "arquivo"
        return info

    quantidade = 0
    total = 0
    truncado = False
    extensoes: Counter[str] = Counter()
    try:
        for raiz, diretorios, arquivos in os.walk(caminho):
            diretorios[:] = [nome for nome in diretorios if not (Path(raiz) / nome).is_symlink()]
            for nome in arquivos:
                arquivo = Path(raiz) / nome
                try:
                    if arquivo.is_symlink():
                        continue
                    total += arquivo.stat().st_size
                except OSError:
                    continue
                quantidade += 1
                extensao = arquivo.suffix.lower() or "(sem extensao)"
                extensao = re.sub(r"[^a-z0-9.]", "", extensao)[:15] or "(outros)"
                extensoes[extensao] += 1
                if quantidade >= LIMITE_ARQUIVOS_ANEXOS:
                    truncado = True
                    break
            if truncado:
                break
    except OSError as exc:
        info["erro"] = str(exc)

    info.update(
        {
            "tipo": "pasta",
            "arquivos": quantidade,
            "bytes": total,
            "extensoes": dict(extensoes.most_common(15)),
            "truncado": truncado,
        }
    )
    return info


def verificar_porta() -> dict[str, Any]:
    try:
        with socket.create_connection(("127.0.0.1", PORTA_CRM), timeout=1.5):
            return {"porta": PORTA_CRM, "aberta": True, "codigo": 0}
    except ConnectionRefusedError as exc:
        return {
            "porta": PORTA_CRM,
            "aberta": False,
            "codigo": getattr(exc, "winerror", None) or 10061,
        }
    except TimeoutError:
        return {
            "porta": PORTA_CRM,
            "aberta": False,
            "codigo": "timeout",
            "erro": "tempo esgotado ao conectar",
        }
    except OSError as exc:
        return {
            "porta": PORTA_CRM,
            "aberta": False,
            "codigo": getattr(exc, "winerror", None) or exc.errno,
            "erro": str(exc),
        }


def coletar_processos_python() -> dict[str, Any]:
    if os.name != "nt":
        return {"disponivel": False}

    def tasklist(imagem: str) -> list[int]:
        processo = executar(
            ["tasklist", "/FI", f"IMAGENAME eq {imagem}", "/FO", "CSV", "/NH"],
            timeout=10,
        )
        if not processo or processo.returncode != 0:
            return []
        pids: list[int] = []
        for linha in processo.stdout.splitlines():
            linha = linha.strip()
            if not linha or linha.startswith("INFO:"):
                continue
            try:
                partes = next(csv.reader([linha]))
            except (csv.Error, StopIteration):
                continue
            if len(partes) >= 2 and partes[1].strip().isdigit():
                pids.append(int(partes[1].strip()))
        return pids

    proprio_pid = os.getpid()
    return {
        "disponivel": True,
        "python": [pid for pid in tasklist("python.exe") if pid != proprio_pid],
        "pythonw": [pid for pid in tasklist("pythonw.exe") if pid != proprio_pid],
    }


def verificar_esquema(banco: dict[str, Any]) -> dict[str, Any]:
    if banco.get("erro"):
        return {"ok": None, "erro": banco["erro"]}
    tabelas = banco.get("tabelas") or {}
    ausentes = [nome for nome in TABELAS_ESPERADAS if nome not in tabelas]
    colunas_ausentes: dict[str, list[dict[str, Any]]] = {}
    sem_migracao: list[str] = []

    for tabela, esperadas in COLUNAS_ESPERADAS.items():
        if tabela not in tabelas:
            continue
        presentes = {coluna.get("nome") for coluna in tabelas[tabela].get("colunas", [])}
        faltando: list[dict[str, Any]] = []
        for coluna in esperadas:
            if coluna in presentes:
                continue
            automatica = coluna in COLUNAS_MIGRADAS.get(tabela, set())
            faltando.append({"coluna": coluna, "migracao_automatica": automatica})
            if not automatica:
                sem_migracao.append(f"{tabela}.{coluna}")
        if faltando:
            colunas_ausentes[tabela] = faltando

    if sem_migracao:
        risco = "alto"
    elif ausentes:
        risco = "medio"
    else:
        risco = "baixo"

    return {
        "ok": not sem_migracao,
        "referencia": DATA_REFERENCIA,
        "tabelas_ausentes": ausentes,
        "colunas_ausentes": colunas_ausentes,
        "sem_migracao_automatica": sem_migracao,
        "risco": risco,
    }


def gerar_relatorio_txt(dados: dict[str, Any], destino: Path) -> str:
    linhas: list[str] = []

    def adicionar(texto: str = "") -> None:
        linhas.append(texto)

    adicionar("=" * 70)
    adicionar("CRM CONSIGNADO - DIAGNÓSTICO")
    adicionar("=" * 70)
    adicionar(f"Gerado em: {dados.get('diagnostico', {}).get('gerado_em')}")
    adicionar(f"Computador: {dados.get('computador', {}).get('hostname')}")
    adicionar(f"Sistema: {dados.get('computador', {}).get('sistema')}")
    adicionar(f"Pasta do CRM: {dados.get('pasta_crm')}")
    adicionar()

    app = dados.get("app") or {}
    adicionar("IDENTIFICAÇÃO DA VERSÃO")
    adicionar(f"  app.py: {app.get('sha256')}")
    adicionar(f"  Linhas: {app.get('linhas')} | Tamanho: {formatar_bytes(app.get('tamanho'))}")
    versoes = app.get("versoes") or []
    if versoes:
        adicionar("  Último commit que alterou o app.py:")
        for versao in versoes[:5]:
            adicionar(f"    - {versao.get('commit')} ({versao.get('data')}): {versao.get('assunto')}")
    else:
        adicionar("  Não corresponde a nenhuma versão publicada conhecida.")
        adicionar("  Pode ser anterior à publicação do repositório ou ter sido modificada.")
    adicionar()

    banco = dados.get("banco") or {}
    localizacao = dados.get("banco_localizacao") or {}
    adicionar("BANCO DE DADOS")
    adicionar(f"  Arquivo: {banco.get('caminho')}")
    adicionar(f"  Localizado por: {localizacao.get('origem')}")
    adicionar(f"  Tamanho: {formatar_bytes(banco.get('tamanho'))}")
    adicionar(f"  user_version: {banco.get('user_version')} | application_id: {banco.get('application_id')}")
    adicionar(f"  integrity_check: {banco.get('integridade')}")
    adicionar(f"  foreign_key_check: {banco.get('fk_violacoes')} violação(ões)")
    if banco.get("erro"):
        adicionar(f"  ERRO: {banco.get('erro')}")
    tabelas = banco.get("tabelas") or {}
    if tabelas:
        adicionar(f"  Tabelas encontradas: {len(tabelas)}")
        for nome, info in sorted(tabelas.items()):
            adicionar(f"    - {nome}: {info.get('linhas')} linha(s), {len(info.get('colunas', []))} coluna(s)")
    adicionar()

    esquema = dados.get("esquema") or {}
    adicionar("COMPATIBILIDADE DO ESQUEMA")
    adicionar(f"  Referência: versão atual do repositório ({esquema.get('referencia')})")
    adicionar(f"  Risco: {esquema.get('risco')}")
    ausentes = esquema.get("tabelas_ausentes") or []
    if ausentes:
        adicionar(f"  Tabelas ausentes (serão criadas pelo app): {', '.join(ausentes)}")
    colunas_ausentes = esquema.get("colunas_ausentes") or {}
    if colunas_ausentes:
        for tabela, colunas in sorted(colunas_ausentes.items()):
            for coluna in colunas:
                marca = "migração automática" if coluna.get("migracao_automatica") else "SEM migração automática"
                adicionar(f"  Coluna ausente: {tabela}.{coluna.get('coluna')} ({marca})")
    if not ausentes and not colunas_ausentes:
        adicionar("  Estrutura compatível com a versão atual.")
    adicionar()

    python_info = dados.get("python") or {}
    selecionado = python_info.get("selecionado") or {}
    adicionar("PYTHON E DEPENDÊNCIAS")
    adicionar(f"  Python selecionado: {selecionado.get('rotulo')} ({selecionado.get('versao')})")
    adicionar(f"  Executável: {selecionado.get('executavel')}")
    adicionar(f"  pip: {python_info.get('pip') or python_info.get('pip_erro')}")
    pacotes = python_info.get("pacotes") or []
    adicionar(f"  Pacotes instalados: {len(pacotes)}")
    for linha in python_info.get("versoes_pacotes") or []:
        adicionar(f"    - {linha}")
    adicionar()

    inicializacao = dados.get("inicializacao") or {}
    adicionar("INICIALIZAÇÃO")
    adicionar(f"  Forma provável: {inicializacao.get('provavel')}")
    adicionar(f"  crm.bat existe: {inicializacao.get('crm_bat_existe')}")
    adicionar(f"  Algum .bat invoca app.py: {inicializacao.get('invoca_app')}")
    for item in inicializacao.get("bats") or []:
        if item.get("variaveis"):
            adicionar(f"  {item.get('nome')}: {item.get('variaveis')}")
    for nome, valor in (dados.get("ambiente", {}).get("crm") or {}).items():
        adicionar(f"  {nome}={valor}")
    git_info = dados.get("git") or {}
    if git_info.get("repositorio_git"):
        adicionar(f"  Git: commit {git_info.get('commit')} ({git_info.get('data')})")
        adicionar(f"  Git sujo: {git_info.get('sujo')} | modificados: {git_info.get('modificados')} | não rastreados: {git_info.get('nao_rastreados')}")
        if git_info.get("remoto"):
            adicionar(f"  Remoto: {git_info.get('remoto')}")
    adicionar()

    inventario = dados.get("inventario") or {}
    adicionar("INVENTÁRIO")
    for nome, info in sorted((inventario.get("contagens") or {}).items()):
        adicionar(
            f"  {nome}: {info.get('arquivos')} arquivo(s), {formatar_bytes(info.get('bytes'))}"
        )
    adicionar(
        f"  Outros arquivos/pastas na raiz: {inventario.get('outros_arquivos_na_raiz', 0)} "
        "(nomes não incluídos)"
    )
    adicionar()

    anexos = dados.get("anexos") or {}
    localizacao_anexos = dados.get("anexos_localizacao") or {}
    adicionar("ANEXOS")
    adicionar(f"  Pasta: {anexos.get('caminho')}")
    adicionar(f"  Localizada por: {localizacao_anexos.get('origem')}")
    adicionar(f"  Existe: {anexos.get('existe')} | Arquivos: {anexos.get('arquivos')} | Tamanho: {formatar_bytes(anexos.get('bytes'))}")
    if anexos.get("extensoes"):
        adicionar(f"  Extensões: {anexos.get('extensoes')}")
    adicionar()

    porta = dados.get("porta") or {}
    processos = dados.get("processos_python") or {}
    adicionar("STATUS DE EXECUÇÃO")
    adicionar(f"  Porta {PORTA_CRM} aberta: {porta.get('aberta')} (código {porta.get('codigo')})")
    adicionar(f"  Processos python.exe: {processos.get('python')}")
    adicionar(f"  Processos pythonw.exe: {processos.get('pythonw')}")
    adicionar()

    avisos = dados.get("avisos") or []
    adicionar("AVISOS")
    if avisos:
        for aviso in avisos:
            adicionar(f"  - {aviso}")
    else:
        adicionar("  Nenhum.")
    adicionar()

    adicionar("ARQUIVOS GERADOS")
    adicionar(f"  Pasta: {redigir_caminho_usuario(str(destino))}")
    adicionar("  - relatorio.json")
    adicionar("  - relatorio.txt")
    adicionar("  - schema.sql")
    adicionar("  - pacotes.txt")
    adicionar("  - inicializacao.txt")
    adicionar("  - hashes.txt")
    adicionar("  - LEIA-ME.txt")
    adicionar("  - manifest.json")
    if (dados.get("banco") or {}).get("copia"):
        adicionar("  - database_copia.db (contém dados pessoais)")
    adicionar()
    adicionar("Nada foi alterado no CRM.")
    return "\n".join(linhas) + "\n"


def copiar_banco(origem: Path, destino: Path) -> dict[str, Any]:
    try:
        conexao_origem = sqlite3.connect(caminho_uri(origem), uri=True, timeout=10)
        try:
            conexao_origem.execute("PRAGMA query_only = ON")
            conexao_destino = sqlite3.connect(str(destino))
            try:
                conexao_origem.backup(conexao_destino)
                verificacao = conexao_destino.execute("PRAGMA integrity_check").fetchone()[0]
            finally:
                conexao_destino.close()
        finally:
            conexao_origem.close()
        return {
            "arquivo": destino.name,
            "tamanho": destino.stat().st_size,
            "sha256": sha256_arquivo(destino),
            "integridade": verificacao,
        }
    except (sqlite3.Error, OSError) as exc:
        try:
            if destino.exists():
                destino.unlink()
        except OSError:
            pass
        return {"erro": str(exc)}


def texto_leia_me(incluir_banco: bool) -> str:
    linhas = [
        "CRM CONSIGNADO - PACOTE DE DIAGNÓSTICO",
        "",
        "Este pacote foi gerado por uma ferramenta somente leitura.",
        "O CRM e o banco de dados não foram alterados.",
        "",
        "O que contém:",
        "- relatorio.json e relatorio.txt: informações técnicas da instalação.",
        "- schema.sql: estrutura do banco, sem os dados dos clientes.",
        "- pacotes.txt: dependências Python instaladas.",
        "- inicializacao.txt: conteúdo dos arquivos .bat/.cmd/.ps1/.vbs,",
        "  com senhas e chaves ocultadas.",
        "- hashes.txt e manifest.json: conferência de integridade dos arquivos.",
        "",
        "O relatório NÃO contém nomes, CPFs, telefones, anotações,",
        "mensagens ou outros dados dos clientes.",
        "A chave secreta do CRM também não é incluída.",
    ]
    if incluir_banco:
        linhas += [
            "",
            "ATENÇÃO: database_copia.db é uma cópia integral do banco,",
            "portanto contém dados pessoais dos clientes.",
            "Envie o pacote por um canal seguro e apague a cópia depois do uso.",
        ]
    linhas += [
        "",
        "Envie o arquivo .zip para a pessoa responsável pela atualização.",
        "Se tiver dúvida, não envie o pacote para terceiros.",
        "",
    ]
    return "\n".join(linhas)


def gerar_saida(dados: dict[str, Any], pasta_saida: Path, incluir_banco: bool) -> dict[str, Any]:
    pasta_saida = Path(pasta_saida).expanduser()
    pasta_saida.mkdir(parents=True, exist_ok=True)

    host = re.sub(r"[^A-Za-z0-9_-]+", "-", platform.node() or "pc")[:32] or "pc"
    nome = f"crm-diagnostico-{host}-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    destino = pasta_saida / nome
    contador = 2
    while destino.exists():
        destino = pasta_saida / f"{nome}-{contador}"
        contador += 1
    destino.mkdir(parents=True)

    if incluir_banco:
        caminho_db = (dados.get("banco") or {}).get("caminho")
        if caminho_db and Path(caminho_db).is_file():
            copia = copiar_banco(Path(caminho_db), destino / "database_copia.db")
            dados["banco"]["copia"] = copia
            if copia.get("erro"):
                dados.setdefault("avisos", []).append(
                    f"Não foi possível copiar o banco: {copia['erro']}"
                )
        else:
            dados.setdefault("avisos", []).append(
                "A cópia do banco foi solicitada, mas o banco não foi localizado."
            )

    dados_redigidos = redigir_dados(dados)

    (destino / "relatorio.json").write_text(
        json.dumps(dados_redigidos, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destino / "relatorio.txt").write_text(
        gerar_relatorio_txt(dados_redigidos, destino),
        encoding="utf-8",
    )

    schema = (dados_redigidos.get("banco") or {}).get("schema_sql") or ""
    (destino / "schema.sql").write_text(
        schema or "-- Esquema do banco não disponível.\n",
        encoding="utf-8",
    )

    python_info = dados_redigidos.get("python") or {}
    linhas_pacotes: list[str] = []
    if python_info.get("pip"):
        linhas_pacotes.append(python_info["pip"])
    linhas_pacotes.extend(python_info.get("versoes_pacotes") or [])
    linhas_pacotes.append("")
    linhas_pacotes.extend(python_info.get("pacotes") or [])
    if python_info.get("pacotes_erro"):
        linhas_pacotes.append(f"Erro ao listar pacotes: {python_info['pacotes_erro']}")
    (destino / "pacotes.txt").write_text("\n".join(linhas_pacotes) + "\n", encoding="utf-8")

    linhas_inicializacao: list[str] = []
    inicializacao = dados_redigidos.get("inicializacao") or {}
    for item in inicializacao.get("bats") or []:
        linhas_inicializacao.append(f"### {item.get('nome')}")
        linhas_inicializacao.append(item.get("conteudo_redigido") or "(vazio)")
        linhas_inicializacao.append("")
    for item in inicializacao.get("scripts") or []:
        linhas_inicializacao.append(f"### {item.get('nome')}")
        linhas_inicializacao.append(item.get("conteudo_redigido") or "(vazio)")
        linhas_inicializacao.append("")
    (destino / "inicializacao.txt").write_text(
        "\n".join(linhas_inicializacao) or "Nenhum script de inicialização encontrado.\n",
        encoding="utf-8",
    )

    linhas_hashes: list[str] = []
    app = dados_redigidos.get("app") or {}
    banco = dados_redigidos.get("banco") or {}
    linhas_hashes.append(f"app.py\t{app.get('sha256')}\t{app.get('tamanho')}")
    linhas_hashes.append(f"database.db\t{banco.get('sha256')}\t{banco.get('tamanho')}")
    for nome_json, info_json in (app.get("data") or {}).items():
        linhas_hashes.append(
            f"data/{nome_json}\t{info_json.get('sha256')}\t{info_json.get('tamanho')}"
        )
    if banco.get("copia"):
        copia = banco["copia"]
        linhas_hashes.append(
            f"{copia.get('arquivo')}\t{copia.get('sha256')}\t{copia.get('tamanho')}"
        )
    (destino / "hashes.txt").write_text("\n".join(linhas_hashes) + "\n", encoding="utf-8")

    (destino / "LEIA-ME.txt").write_text(texto_leia_me(incluir_banco), encoding="utf-8")

    arquivos_manifesto = []
    for caminho in sorted(destino.iterdir()):
        if not caminho.is_file() or caminho.name == "manifest.json":
            continue
        try:
            tamanho = caminho.stat().st_size
        except OSError:
            tamanho = None
        arquivos_manifesto.append(
            {
                "arquivo": caminho.name,
                "tamanho": tamanho,
                "sha256": sha256_arquivo(caminho),
            }
        )
    (destino / "manifest.json").write_text(
        json.dumps(
            {
                "gerado_em": agora_iso(),
                "diagnostico_versao": DIAGNOSTICO_VERSAO,
                "arquivos": arquivos_manifesto,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    zip_path = destino.with_name(destino.name + ".zip")
    contador_zip = 2
    while zip_path.exists():
        zip_path = destino.with_name(f"{destino.name}-{contador_zip}.zip")
        contador_zip += 1
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as arquivo_zip:
        for caminho in sorted(destino.rglob("*")):
            if caminho.is_file():
                arquivo_zip.write(caminho, arcname=f"{destino.name}/{caminho.relative_to(destino).as_posix()}")

    return {
        "pasta": str(destino),
        "zip": str(zip_path),
        "zip_tamanho": zip_path.stat().st_size,
        "zip_sha256": sha256_arquivo(zip_path),
    }


def imprimir_resumo(dados: dict[str, Any], resultado: dict[str, Any], incluir_banco: bool) -> None:
    app = dados.get("app") or {}
    banco = dados.get("banco") or {}
    python_info = dados.get("python") or {}
    print()
    print("=" * 70)
    print("DIAGNÓSTICO CONCLUÍDO")
    print("=" * 70)
    print(f"CRM: {dados.get('pasta_crm')}")
    versoes = app.get("versoes") or []
    if versoes:
        versao = versoes[0]
        print(f"Versão: {versao.get('commit')} ({versao.get('data')}) - {versao.get('assunto')}")
    else:
        print("Versão: não corresponde a nenhuma versão publicada conhecida.")
    print(f"Banco: {banco.get('caminho')}")
    print(f"Integridade do banco: {banco.get('integridade')}")
    print(f"Python: {(python_info.get('selecionado') or {}).get('versao')}")
    print(f"Porta {PORTA_CRM} aberta: {(dados.get('porta') or {}).get('aberta')}")
    print()
    print(f"Relatório: {resultado.get('pasta')}")
    print(f"ZIP: {resultado.get('zip')}")
    if incluir_banco:
        print()
        print("ATENÇÃO: o ZIP inclui uma cópia do banco com dados pessoais.")
        print("Envie por canal seguro e apague o arquivo depois do uso.")
    print()
    print("Nada foi alterado no CRM.")


def configurar_console() -> None:
    if os.name == "nt":
        try:
            import ctypes

            ctypes.windll.kernel32.SetConsoleOutputCP(65001)
            ctypes.windll.kernel32.SetConsoleCP(65001)
        except Exception:
            pass
    for fluxo in (sys.stdout, sys.stderr):
        try:
            fluxo.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except Exception:
            pass


def pausar() -> None:
    if SEM_PAUSA:
        return
    try:
        input("\nPressione Enter para sair...")
    except EOFError:
        pass


def saida_padrao() -> Path:
    home = Path.home()
    for nome in ("Documents", "Documentos", "Desktop", "Área de Trabalho"):
        candidato = home / nome
        if candidato.is_dir():
            return candidato / "CRM-Diagnostico"
    return home / "CRM-Diagnostico"


def main() -> int:
    global SEM_PAUSA

    configurar_console()

    parser = argparse.ArgumentParser(
        description=(
            "Diagnóstico somente leitura do CRM Consignado. "
            "Não altera o CRM, o banco nem os anexos."
        )
    )
    parser.add_argument("-p", "--pasta", help="Pasta do CRM (onde está o app.py).")
    parser.add_argument("-o", "--saida", help="Pasta onde o relatório será salvo.")
    parser.add_argument(
        "--incluir-banco",
        action="store_true",
        help="Inclui uma cópia do banco no pacote (contém dados pessoais).",
    )
    parser.add_argument("--sem-pausa", action="store_true", help="Não aguarda Enter ao final.")
    args = parser.parse_args()
    SEM_PAUSA = args.sem_pausa

    print("CRM Consignado - Diagnóstico somente leitura")
    print(f"Versão do diagnóstico: {DIAGNOSTICO_VERSAO}")
    print()

    mapa_versoes, meta_mapa = carregar_versoes()

    print("Localizando a pasta do CRM...")
    pasta = selecionar_pasta(args)
    if pasta is None:
        print("Não foi possível localizar o CRM.")
        pausar()
        return 1
    print(f"Pasta do CRM: {pasta}")

    print("Lendo arquivos de configuração...")
    fontes_publicas, fontes_raw, variaveis = coletar_fontes(pasta)

    print("Localizando o banco de dados...")
    caminho_banco, origem_banco, candidatos_banco = resolver_banco(pasta, fontes_raw, variaveis)
    print("Lendo o banco (somente leitura)...")
    banco = coletar_banco(caminho_banco)

    caminho_anexos, origem_anexos, candidatos_anexos = resolver_anexos(
        pasta, fontes_raw, variaveis, banco
    )

    print("Coletando dados da instalação...")
    app = coletar_app(pasta, mapa_versoes)
    git_info = coletar_git(pasta)
    python_info = coletar_python(pasta)
    ambiente = coletar_ambiente()
    inicializacao = coletar_inicializacao(pasta, fontes_publicas)
    inventario = coletar_pasta(pasta)
    anexos = coletar_anexos(caminho_anexos)
    porta = verificar_porta()
    processos = coletar_processos_python()
    esquema = verificar_esquema(banco)

    incluir_banco = args.incluir_banco
    if not incluir_banco and not SEM_PAUSA:
        print()
        print("Deseja incluir uma cópia do banco no pacote?")
        print("Ela permite testar a migração em uma cópia, mas contém dados pessoais.")
        try:
            resposta = input("Incluir cópia do banco? (s/N): ").strip().lower()
        except EOFError:
            resposta = ""
        incluir_banco = resposta in ("s", "sim", "y", "yes")

    avisos: list[str] = []
    if porta.get("aberta"):
        avisos.append(
            f"A porta {PORTA_CRM} está aberta. Feche o CRM antes de aplicar qualquer atualização."
        )
    elif porta.get("erro"):
        avisos.append(
            f"Não foi possível confirmar se a porta {PORTA_CRM} está em uso: {porta['erro']}."
        )
    if not banco.get("existe"):
        avisos.append("O banco de dados não foi localizado automaticamente.")
    if banco.get("erro"):
        avisos.append(f"Erro ao ler o banco: {banco['erro']}")
    if banco.get("integridade") and str(banco["integridade"]).strip().lower() != "ok":
        avisos.append("O PRAGMA integrity_check não retornou 'ok'.")
    if banco.get("fk_violacoes"):
        avisos.append(
            f"O banco tem {banco['fk_violacoes']} violação(ões) de chave estrangeira já existentes."
        )
    if esquema.get("sem_migracao_automatica"):
        avisos.append(
            "Há colunas ausentes sem migração automática no init_db atual: "
            + ", ".join(esquema["sem_migracao_automatica"])
        )
    if esquema.get("tabelas_ausentes"):
        avisos.append(
            "Há tabelas ausentes; o init_db atual deve criá-las, mas confirme se os dados antigos "
            "não estavam em outro formato."
        )
    if not app.get("versao_conhecida"):
        avisos.append(
            "O app.py não corresponde a nenhuma versão publicada conhecida. "
            "Pode ser uma versão anterior ao repositório ou ter sido modificada."
        )
    if not python_info.get("selecionado"):
        avisos.append("Nenhum Python executável foi encontrado.")
    if not (pasta / ".venv").exists() and not (pasta / "venv").exists():
        avisos.append(
            "Não foi encontrada pasta .venv/venv. O CRM pode estar usando o Python global."
        )
    if git_info.get("sujo"):
        avisos.append(
            "O repositório Git tem alterações locais. Isso pode indicar código modificado manualmente."
        )
    if processos.get("python") or processos.get("pythonw"):
        avisos.append(
            "Há processos Python em execução. Se algum for o CRM, feche-o antes de atualizar."
        )
    if incluir_banco:
        avisos.append(
            "A cópia do banco foi incluída no pacote e contém dados pessoais. "
            "Envie por canal seguro."
        )

    dados: dict[str, Any] = {
        "diagnostico": {
            "versao": DIAGNOSTICO_VERSAO,
            "gerado_em": agora_iso(),
            "data_referencia": DATA_REFERENCIA,
            "mapa_versoes": meta_mapa,
        },
        "computador": {
            "hostname": platform.node(),
            "sistema": platform.platform(),
        },
        "pasta_crm": str(pasta),
        "app": app,
        "banco": banco,
        "banco_localizacao": {
            "caminho": str(caminho_banco) if caminho_banco else None,
            "origem": origem_banco,
            "candidatos": [
                {"caminho": str(item["caminho"]), "origem": item["origem"], "existe": item["existe"]}
                for item in candidatos_banco
            ],
        },
        "anexos": anexos,
        "anexos_localizacao": {
            "caminho": str(caminho_anexos) if caminho_anexos else None,
            "origem": origem_anexos,
            "candidatos": [
                {"caminho": str(item["caminho"]), "origem": item["origem"], "existe": item["existe"]}
                for item in candidatos_anexos
            ],
        },
        "python": python_info,
        "ambiente": ambiente,
        "inicializacao": inicializacao,
        "inventario": inventario,
        "git": git_info,
        "porta": porta,
        "processos_python": processos,
        "esquema": esquema,
        "avisos": avisos,
    }

    print("Gerando relatório...")
    base_saida = Path(args.saida).expanduser() if args.saida else saida_padrao()
    resultado = gerar_saida(dados, base_saida, incluir_banco)
    imprimir_resumo(dados, resultado, incluir_banco)
    pausar()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nCancelado.")
        sys.exit(130)
    except Exception as exc:  # pragma: no cover - proteção para o executável
        print(f"\nErro inesperado: {exc}")
        import traceback

        traceback.print_exc()
        pausar()
        sys.exit(1)
