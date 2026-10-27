"""Testes do gerenciador do CRM (funções sem interface).

Não iniciam o CRM, não acessam o banco e não dependem de rede.
"""
import socket
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gerenciador_crm as gerenciador


class TestDescobertaDoProjeto(unittest.TestCase):
    def test_ler_porta_encontra_valor_do_app_run(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "app.py").write_text(
                "if __name__ == '__main__':\n"
                "    app.run(host='0.0.0.0', port=6100, debug=False)\n",
                encoding="utf-8",
            )
            self.assertEqual(gerenciador.ler_porta(raiz), 6100)

    def test_ler_porta_usa_padrao_sem_arquivo(self) -> None:
        self.assertEqual(gerenciador.ler_porta(None), gerenciador.PORTA_PADRAO)
        with tempfile.TemporaryDirectory() as pasta:
            self.assertEqual(gerenciador.ler_porta(Path(pasta)), gerenciador.PORTA_PADRAO)

    def test_porta_configurada_ignora_valores_invalidos(self) -> None:
        self.assertEqual(gerenciador.porta_configurada({"porta": 5001}), 5001)
        self.assertEqual(gerenciador.porta_configurada({"porta": "5002"}), 5002)
        self.assertEqual(gerenciador.porta_configurada({}), 0)
        self.assertEqual(gerenciador.porta_configurada({"porta": 0}), 0)
        self.assertEqual(gerenciador.porta_configurada({"porta": 70000}), 0)
        self.assertEqual(gerenciador.porta_configurada({"porta": "abc"}), 0)

    def test_detectar_pasta_pelo_app_py(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            (raiz / "app.py").write_text("", encoding="utf-8")
            self.assertEqual(gerenciador.detectar_pasta_projeto(pasta_exe=raiz), raiz.resolve())

    def test_detectar_prioriza_pasta_configurada(self) -> None:
        with tempfile.TemporaryDirectory() as configurada, tempfile.TemporaryDirectory() as outra:
            (Path(configurada) / "app.py").write_text("", encoding="utf-8")
            (Path(outra) / "app.py").write_text("", encoding="utf-8")
            encontrada = gerenciador.detectar_pasta_projeto(
                pasta_config=configurada, pasta_exe=Path(outra)
            )
            self.assertEqual(encontrada, Path(configurada).resolve())


class TestPython(unittest.TestCase):
    def test_localizar_python_do_ambiente_virtual(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            scripts = raiz / ".venv" / "Scripts"
            scripts.mkdir(parents=True)
            executavel = scripts / "python.exe"
            executavel.write_text("", encoding="utf-8")
            caminho, origem = gerenciador.localizar_python(raiz)
            self.assertEqual(Path(caminho), executavel)
            self.assertIn(".venv", origem)

    def test_localizar_python_configurado_tem_prioridade(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            scripts = raiz / ".venv" / "Scripts"
            scripts.mkdir(parents=True)
            (scripts / "python.exe").write_text("", encoding="utf-8")
            escolhido = raiz / "python-custom.exe"
            escolhido.write_text("", encoding="utf-8")
            caminho, origem = gerenciador.localizar_python(raiz, str(escolhido))
            self.assertEqual(Path(caminho), escolhido)
            self.assertEqual(origem, "configurado")

    def test_processo_e_python(self) -> None:
        self.assertTrue(gerenciador.processo_e_python("python.exe"))
        self.assertTrue(gerenciador.processo_e_python("pythonw.exe"))
        self.assertTrue(gerenciador.processo_e_python("py.exe"))
        self.assertFalse(gerenciador.processo_e_python("chrome.exe"))
        self.assertFalse(gerenciador.processo_e_python(""))


class TestPorta(unittest.TestCase):
    def test_interpretar_netstat_filtra_porta_e_estado(self) -> None:
        saida = """
  Proto  Endereço local         Endereço externo       Estado           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1780
  TCP    0.0.0.0:5000           0.0.0.0:0              LISTENING       4321
  TCP    [::]:5000              [::]:0                 LISTENING       4322
  TCP    127.0.0.1:5000         127.0.0.1:52344        ESTABLISHED     9000
  TCP    0.0.0.0:5001           0.0.0.0:0              LISTENING       777
"""
        self.assertEqual(gerenciador.interpretar_netstat(saida, 5000), [4321, 4322])
        self.assertEqual(gerenciador.interpretar_netstat(saida, 5001), [777])
        self.assertEqual(gerenciador.interpretar_netstat(saida, 8080), [])

    def test_porta_aberta_reflete_o_socket(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.bind(("127.0.0.1", 0))
            servidor.listen(1)
            porta = servidor.getsockname()[1]
            self.assertTrue(gerenciador.porta_aberta(porta))
        self.assertFalse(gerenciador.porta_aberta(porta))


class TestGit(unittest.TestCase):
    def test_interpretar_status_git(self) -> None:
        saida = "\n".join(
            [
                "# branch.oid abcdef",
                "# branch.head main",
                "# branch.upstream origin/main",
                "# branch.ab +2 -3",
                "1 .M N... 100644 100644 100644 aaa bbb app.py",
                "? novo.txt",
                "",
            ]
        )
        dados = gerenciador.interpretar_status_git(saida)
        self.assertEqual(dados["branch"], "main")
        self.assertEqual(dados["upstream"], "origin/main")
        self.assertEqual(dados["ahead"], 2)
        self.assertEqual(dados["behind"], 3)
        self.assertEqual(dados["alterados"], 1)
        self.assertEqual(dados["nao_rastreados"], 1)

    def test_resumo_git_sem_repositorio(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            self.assertIn("sem repositório", gerenciador.resumo_git(Path(pasta)))
        self.assertIn("sem repositório", gerenciador.resumo_git(None))

    def test_alteracoes_relevantes(self) -> None:
        self.assertTrue(gerenciador.alteracoes_relevantes(["app.py"]))
        self.assertTrue(gerenciador.alteracoes_relevantes(["requirements.txt"]))
        self.assertTrue(gerenciador.alteracoes_relevantes(["static/script.js"]))
        self.assertTrue(gerenciador.alteracoes_relevantes(["templates/base.html"]))
        self.assertTrue(gerenciador.alteracoes_relevantes(["data/modelos_mensagens.json"]))
        self.assertFalse(gerenciador.alteracoes_relevantes(["README.md", "tests/test_x.py"]))
        self.assertFalse(gerenciador.alteracoes_relevantes([]))


class TestLogsEConfig(unittest.TestCase):
    def test_config_ida_e_volta(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            with mock.patch.object(gerenciador, "pasta_dados", return_value=Path(pasta)):
                gerenciador.salvar_config({"pasta": "C:/crm", "porta": 5000})
                self.assertEqual(
                    gerenciador.carregar_config(), {"pasta": "C:/crm", "porta": 5000}
                )

    def test_config_invalida_vira_dicionario_vazio(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            with mock.patch.object(gerenciador, "pasta_dados", return_value=Path(pasta)):
                gerenciador.caminho_config().write_text("{invalido", encoding="utf-8")
                self.assertEqual(gerenciador.carregar_config(), {})

    def test_rotacionar_log(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "crm.log"
            arquivo.write_text("x" * 2048, encoding="utf-8")
            gerenciador.rotacionar_log(arquivo, limite=1024)
            self.assertFalse(arquivo.exists())
            self.assertTrue((Path(pasta) / "crm.1.log").is_file())

    def test_rotacionar_log_pequeno_nao_muda(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "crm.log"
            arquivo.write_text("linha", encoding="utf-8")
            gerenciador.rotacionar_log(arquivo, limite=1024)
            self.assertTrue(arquivo.exists())

    def test_cauda_limita_linhas(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / "crm.log"
            arquivo.write_text("\n".join(f"linha {i}" for i in range(30)), encoding="utf-8")
            texto = gerenciador.cauda(arquivo, 5)
            self.assertEqual(texto.splitlines(), [f"linha {i}" for i in range(25, 30)])
        self.assertEqual(gerenciador.cauda(Path(pasta) / "nao-existe.log"), "")


if __name__ == "__main__":
    unittest.main()
