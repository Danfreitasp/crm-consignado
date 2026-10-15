"""Regressão da complementação de dados do Corban, sem acessar o banco.

Extrai apenas as funções puras do app.py para validar a prioridade dos dados:
cadastro do cliente > dados do extrato > dados do Corban.
"""
import ast
import re
import sqlite3
import unittest
from pathlib import Path
from typing import Any


source = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))

funcoes = {
    "limpar_texto",
    "formatar_cpf",
    "normalizar_matricula",
    "normalizar_dados_corban",
    "complementar_proposta_com_corban",
}
constantes = {"CAMPOS_CORBAN", "ROTULOS_CORBAN"}

corpo = []
for node in source.body:
    if isinstance(node, ast.FunctionDef) and node.name in funcoes:
        corpo.append(node)
    elif isinstance(node, ast.Assign) and any(
        isinstance(alvo, ast.Name) and alvo.id in constantes for alvo in node.targets
    ):
        corpo.append(node)

namespace = {"re": re, "sqlite3": sqlite3, "Any": Any}
exec(compile(ast.Module(body=corpo, type_ignores=[]), "app.py", "exec"), namespace)

complementar = namespace["complementar_proposta_com_corban"]


class CorbanComplementoTest(unittest.TestCase):
    def test_preenche_somente_campos_vazios_preservando_extrato(self):
        proposta = {"nome": "", "cpf": "", "endereco": "RUA DO EXTRATO, 10", "dados_bancarios": ""}
        corban = {"nome": "Maria", "cpf": "123.456.789-09", "endereco": "RUA DO CORBAN, 20", "dados_bancarios": "BANCO X"}
        resultado = complementar(proposta, corban, {})
        self.assertTrue(resultado["encontrado"])
        self.assertEqual(resultado["campos"]["nome"], "Maria")
        self.assertEqual(resultado["campos"]["dados_bancarios"], "BANCO X")
        self.assertNotIn("endereco", resultado["campos"])
        self.assertIn("endereco", resultado["ignorados"])

    def test_preserva_cadastro_do_cliente(self):
        proposta = {"nome": "", "endereco": "", "dados_bancarios": ""}
        corban = {"nome": "Maria", "endereco": "RUA CORBAN", "dados_bancarios": "BANCO X"}
        cadastro = {"nome": "Maria Cadastro", "endereco": "RUA CADASTRO"}
        resultado = complementar(proposta, corban, cadastro)
        self.assertNotIn("nome", resultado["campos"])
        self.assertNotIn("endereco", resultado["campos"])
        self.assertEqual(resultado["campos"]["dados_bancarios"], "BANCO X")

    def test_cpf_divergente_descarta_dados_do_corban(self):
        proposta = {"cpf": "111.111.111-11", "endereco": ""}
        corban = {"cpf": "222.222.222-22", "endereco": "RUA CORBAN"}
        resultado = complementar(proposta, corban, {})
        self.assertFalse(resultado["encontrado"])
        self.assertEqual(resultado["campos"], {})

    def test_cliente_nao_encontrado_sem_dados(self):
        resultado = complementar({"endereco": ""}, {}, {})
        self.assertFalse(resultado["encontrado"])
        self.assertEqual(resultado["campos"], {})
        self.assertIn("Nenhum dado adicional", resultado["mensagem"])

    def test_preenche_cpf_e_normaliza_matricula(self):
        resultado = complementar({"cpf": "", "nb_matricula": ""}, {"cpf": "12345678909", "nb": "123.456.789-0"}, {})
        self.assertEqual(resultado["campos"]["cpf"], "123.456.789-09")
        self.assertEqual(resultado["campos"]["nb_matricula"], "1234567890")

    def test_telefone_nunca_vem_do_corban(self):
        resultado = complementar({"telefone": ""}, {"nome": "Maria", "telefone": "27999999999"}, {})
        self.assertNotIn("telefone", resultado["campos"])

    def test_cpf_do_cadastro_compara_sem_mascara(self):
        proposta = {"cpf": "", "endereco": ""}
        corban = {"cpf": "123.456.789-09", "endereco": "RUA CORBAN"}
        cadastro = {"cpf": "12345678909"}
        resultado = complementar(proposta, corban, cadastro)
        self.assertNotIn("cpf", resultado["campos"])
        self.assertEqual(resultado["campos"]["endereco"], "RUA CORBAN")

    def test_nada_a_preencher_mantem_dados_atuais(self):
        proposta = {"nome": "Maria", "endereco": "RUA EXTRATO"}
        corban = {"nome": "Maria Corban", "endereco": "RUA CORBAN"}
        resultado = complementar(proposta, corban, {})
        self.assertEqual(resultado["campos"], {})
        self.assertTrue(resultado["encontrado"])


if __name__ == "__main__":
    unittest.main()
