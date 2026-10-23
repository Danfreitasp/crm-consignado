from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SAIDA = Path(__file__).resolve().parent / "versoes_conhecidas.json"


def git(*args: str, texto: bool = True) -> str | bytes:
    comando = ["git", "-C", str(RAIZ), *args]
    if texto:
        return subprocess.check_output(
            comando, text=True, encoding="utf-8", errors="replace"
        ).strip()
    return subprocess.check_output(comando)


def main() -> int:
    if not (RAIZ / ".git").exists():
        if SAIDA.exists():
            print(f"Aviso: .git não encontrado. Mantendo {SAIDA}.")
            return 0
        print("Erro: .git não encontrado e o arquivo de versões ainda não existe.")
        return 1

    try:
        commits = git("log", "--format=%H", "--", "app.py").splitlines()
    except subprocess.CalledProcessError as exc:
        print(f"Erro ao consultar o histórico do Git: {exc}")
        return 1

    versoes: dict[str, list[dict[str, str]]] = {}
    for sha in commits:
        try:
            conteudo = git("show", f"{sha}:app.py", texto=False)
        except subprocess.CalledProcessError:
            continue
        if not isinstance(conteudo, bytes):
            continue
        normalizado = conteudo.replace(b"\r\n", b"\n")
        digest = hashlib.sha256(normalizado).hexdigest()
        data = str(git("show", "-s", "--format=%ad", "--date=short", sha))
        assunto = str(git("show", "-s", "--format=%s", sha))
        versoes.setdefault(digest, []).append(
            {"commit": sha[:12], "data": data, "assunto": assunto}
        )

    dados = {
        "gerado_em": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "repositorio": "Danfreitasp/crm-consignado",
        "total_commits_com_app": len(commits),
        "total_versoes": len(versoes),
        "versoes": dict(
            sorted(
                versoes.items(),
                key=lambda item: item[1][0]["data"] if item[1] else "",
                reverse=True,
            )
        ),
    }
    SAIDA.write_text(
        json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(f"Gerado {SAIDA} com {len(versoes)} versões de app.py.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
