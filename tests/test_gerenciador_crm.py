"""Testes do gerenciador do CRM (funções sem interface).

Não iniciam o CRM, não acessam o banco e não dependem de rede.
"""
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import gerenciador_crm as gerenciador


class TestExecutavel(unittest.TestCase):
    def test_arquivo_do_executavel_quando_empacotado(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            exe = raiz / "GerenciadorCRM.exe"
            exe.write_text("", encoding="utf-8")
            with mock.patch.object(gerenciador.sys, "frozen", True, create=True), \
                    mock.patch.object(gerenciador.sys, "executable", str(exe)):
                alvo = gerenciador.arquivo_do_executavel(raiz)
            self.assertEqual(alvo, (exe.resolve(), "GerenciadorCRM.exe"))

    def test_arquivo_do_executavel_fora_do_projeto(self) -> None:
        with tempfile.TemporaryDirectory() as pasta, tempfile.TemporaryDirectory() as outra:
            exe = Path(outra) / "GerenciadorCRM.exe"
            exe.write_text("", encoding="utf-8")
            with mock.patch.object(gerenciador.sys, "frozen", True, create=True), \
                    mock.patch.object(gerenciador.sys, "executable", str(exe)):
                self.assertIsNone(gerenciador.arquivo_do_executavel(Path(pasta)))

    def test_sem_empacotamento_nao_ha_executavel(self) -> None:
        with mock.patch.object(gerenciador.sys, "frozen", False, create=True):
            self.assertIsNone(gerenciador.caminho_exe_atual())

    def test_liberar_e_restaurar_executavel(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / "GerenciadorCRM.exe"
            exe.write_text("versao antiga", encoding="utf-8")
            backup = gerenciador.liberar_executavel(exe)
            self.assertIsNotNone(backup)
            self.assertFalse(exe.exists())
            self.assertEqual(backup.read_text(encoding="utf-8"), "versao antiga")
            # simula o checkout do git devolvendo a versão antiga ao caminho original
            exe.write_text("versao restaurada pelo git", encoding="utf-8")
            gerenciador.restaurar_executavel(exe, backup)
            self.assertEqual(exe.read_text(encoding="utf-8"), "versao antiga")
            self.assertFalse(backup.exists())

    def test_remover_executavel_antigo(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / "GerenciadorCRM.exe"
            antigo = gerenciador.caminho_executavel_antigo(exe)
            antigo.write_text("x", encoding="utf-8")
            gerenciador.remover_executavel_antigo(exe)
            self.assertFalse(antigo.exists())
        gerenciador.remover_executavel_antigo(None)

    def test_liberar_usa_outro_nome_quando_backup_esta_em_uso(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / "GerenciadorCRM.exe"
            exe.write_text("versao nova", encoding="utf-8")
            antigo = gerenciador.caminho_executavel_antigo(exe)
            antigo.write_text("em uso", encoding="utf-8")
            with open(antigo, "rb"):
                backup = gerenciador.liberar_executavel(exe)
            self.assertIsNotNone(backup)
            self.assertNotEqual(backup, antigo)
            self.assertEqual(backup.read_text(encoding="utf-8"), "versao nova")
            self.assertTrue(antigo.exists())

    def test_restaurar_sem_backup_preserva_o_executavel(self) -> None:
        with tempfile.TemporaryDirectory() as pasta:
            exe = Path(pasta) / "GerenciadorCRM.exe"
            exe.write_text("versao atual", encoding="utf-8")
            gerenciador.restaurar_executavel(
                exe, gerenciador.caminho_executavel_antigo(exe)
            )
            self.assertEqual(exe.read_text(encoding="utf-8"), "versao atual")


class _GitFalso:
    """Substitui a classe na checagem de integridade sem abrir a interface."""

    def __init__(self, respostas: list[tuple[int, str]]) -> None:
        self.respostas = list(respostas)
        self.chamadas: list[list[str]] = []

    def _git(self, args: list[str], timeout: float = 60) -> subprocess.CompletedProcess:
        self.chamadas.append(args)
        codigo, saida = self.respostas.pop(0)
        return subprocess.CompletedProcess(args, codigo, saida, "")


class TestIntegridadeExecutavel(unittest.TestCase):
    def test_integro_quando_hash_confere(self) -> None:
        falso = _GitFalso([(0, "abc123\n"), (0, "abc123\n")])
        self.assertTrue(
            gerenciador.GerenciadorCRM._executavel_integro(falso, "GerenciadorCRM.exe")
        )
        self.assertEqual(falso.chamadas[0], ["rev-parse", "HEAD:GerenciadorCRM.exe"])
        self.assertEqual(
            falso.chamadas[1],
            ["hash-object", "--no-filters", "--", "GerenciadorCRM.exe"],
        )

    def test_diferente_quando_hash_nao_confere(self) -> None:
        falso = _GitFalso([(0, "abc123\n"), (0, "def456\n")])
        self.assertFalse(
            gerenciador.GerenciadorCRM._executavel_integro(falso, "GerenciadorCRM.exe")
        )

    def test_diferente_quando_git_falha(self) -> None:
        falso = _GitFalso([(128, "")])
        self.assertFalse(
            gerenciador.GerenciadorCRM._executavel_integro(falso, "GerenciadorCRM.exe")
        )


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

    def test_interpretar_netstat_com_estado_localizado(self) -> None:
        saida = """
  TCP    0.0.0.0:5000           0.0.0.0:0              ESCUTANDO       4321
  TCP    [::]:5000              [::]:0                 ESCUTANDO       4322
  TCP    26.55.49.88:50599      26.98.160.10:5000      TIME_WAIT       0
  TCP    127.0.0.1:5000         127.0.0.1:52344        ESTABLISHED     9000
"""
        self.assertEqual(gerenciador.interpretar_netstat(saida, 5000), [4321, 4322])

    def test_interpretar_netstat_ignora_pid_zero(self) -> None:
        saida = "  TCP    26.55.49.88:50599      26.98.160.10:5000      TIME_WAIT       0\n"
        self.assertEqual(gerenciador.interpretar_netstat(saida, 5000), [])

    def test_interpretar_netstat_aceita_estado_desconhecido(self) -> None:
        saida = "  TCP    10.0.0.2:5000          10.0.0.9:52344         DESCONHECIDO    4321\n"
        self.assertEqual(gerenciador.interpretar_netstat(saida, 5000), [4321])

    def test_pids_na_porta_usa_tabela_do_windows_primeiro(self) -> None:
        with mock.patch.object(gerenciador, "_pids_na_porta_tabela", return_value=[4321]), \
                mock.patch.object(gerenciador, "_rodar") as rodar:
            self.assertEqual(gerenciador.pids_na_porta(5000), [4321])
            rodar.assert_not_called()

    def test_pids_na_porta_cai_para_netstat(self) -> None:
        saida = "  TCP    0.0.0.0:5000           0.0.0.0:0              LISTENING       4321\n"
        netstat = subprocess.CompletedProcess([], 0, saida, "")
        with mock.patch.object(gerenciador, "_pids_na_porta_tabela", return_value=[]), \
                mock.patch.object(
                    gerenciador, "_pids_na_porta_powershell", return_value=[]
                ) as ps, \
                mock.patch.object(gerenciador, "_rodar", return_value=netstat):
            self.assertEqual(gerenciador.pids_na_porta(5000), [4321])
            ps.assert_not_called()

    def test_pids_na_porta_cai_para_powershell(self) -> None:
        vazio = subprocess.CompletedProcess([], 0, "", "")
        with mock.patch.object(gerenciador, "_pids_na_porta_tabela", return_value=[]), \
                mock.patch.object(
                    gerenciador, "_pids_na_porta_powershell", return_value=[987]
                ) as ps, \
                mock.patch.object(gerenciador, "_rodar", return_value=vazio):
            self.assertEqual(gerenciador.pids_na_porta(5000), [987])
            ps.assert_called_once_with(5000)

    def test_tabela_tcp_do_windows_encontra_socket_ipv4(self) -> None:
        if gerenciador.os.name != "nt":
            self.skipTest("exclusivo do Windows")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as servidor:
            servidor.bind(("127.0.0.1", 0))
            servidor.listen(1)
            porta = servidor.getsockname()[1]
            self.assertIn(
                gerenciador.os.getpid(), gerenciador._pids_na_porta_tabela(porta)
            )

    def test_tabela_tcp_do_windows_encontra_socket_ipv6(self) -> None:
        if gerenciador.os.name != "nt":
            self.skipTest("exclusivo do Windows")
        try:
            servidor = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        except OSError:
            self.skipTest("IPv6 indisponível")
        with servidor:
            servidor.bind(("::1", 0))
            servidor.listen(1)
            porta = servidor.getsockname()[1]
            self.assertIn(
                gerenciador.os.getpid(), gerenciador._pids_na_porta_tabela(porta)
            )


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
