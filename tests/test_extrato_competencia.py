"""Regressão da contagem de competências, sem acessar o banco operacional."""
import ast
import calendar
import re
import unittest
from datetime import date
from pathlib import Path
from typing import Any


source = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))
helpers = {"limpar_texto", "celula_extrato", "competencia_mes", "dia_do_mes",
           "primeiro_desconto_extrato", "parcelas_pagas_ate_competencia"}
namespace = {"re": re, "date": date, "calendar": calendar, "Any": Any}
exec(compile(ast.Module(body=[node for node in source.body if isinstance(node, ast.FunctionDef)
                              and node.name in helpers], type_ignores=[]), "app.py", "exec"), namespace)
calcular = namespace["parcelas_pagas_ate_competencia"]


class CompetenciaTest(unittest.TestCase):
    def test_exclui_competencia_atual_antes_do_pagamento(self):
        casos = [
            ("10/2024", 82, date(2026, 9, 17), None, 23),
            ("10/2024", 72, date(2026, 9, 17), 25, 23),
            ("09/2026", 96, date(2026, 9, 17), None, 0),
            ("10/2026", 96, date(2026, 9, 17), None, 0),
            ("12/2025", 12, date(2026, 1, 1), None, 1),
            ("01/2020", 12, date(2026, 9, 17), None, 12),
            ("", 72, date(2026, 9, 17), None, 0),
            ("10/2024", 0, date(2026, 9, 17), None, 0),
            ("10/2024", 82, date(2026, 9, 25), 25, 23),
            ("10/2024", 82, date(2026, 9, 26), 25, 24),
            ("09/2026", 96, date(2026, 9, 17), 15, 1),
            ("10/2024", 82, date(2026, 2, 28), 31, 16),
        ]
        for inicio, total, referencia, dia_pagamento, esperado in casos:
            with self.subTest(inicio=inicio, total=total, referencia=referencia, dia=dia_pagamento):
                self.assertEqual(calcular(inicio, total, referencia, dia_pagamento), esperado)

    def test_primeiro_desconto_evita_parcela_a_mais(self):
        # Casos reais do extrato: a competência começava um mês antes do
        # primeiro desconto e o leitor somava uma parcela ainda não paga.
        casos = [
            ("08/12/2026", 108, date(2026, 11, 5), 0),
            ("08/04/2026", 96, date(2026, 11, 5), 7),
            ("10/03/2026", 96, date(2026, 11, 5), 8),
            ("10/09/2025", 96, date(2026, 11, 5), 14),
            ("07/04/2025", 96, date(2026, 11, 5), 19),
            ("10/09/2025", 96, date(2026, 11, 10), 14),
            ("10/09/2025", 96, date(2026, 11, 11), 15),
        ]
        for inicio, total, referencia, esperado in casos:
            with self.subTest(inicio=inicio, referencia=referencia):
                self.assertEqual(calcular(inicio, total, referencia), esperado)

    def test_extrai_data_do_primeiro_desconto_da_linha(self):
        self.assertEqual(namespace["dia_do_mes"]("08/12/26"), 8)
        self.assertEqual(namespace["competencia_mes"]("08/12/26"), date(2026, 12, 1))
        self.assertIsNone(namespace["dia_do_mes"]("11/2026"))

        linha = [""] * 18
        linha[4] = "16/10/26"
        linha[17] = "08/12/26"
        extrair = namespace["primeiro_desconto_extrato"]
        self.assertEqual(extrair(linha), "08/12/26")
        linha[17] = ""
        linha.append("08/12/26")
        self.assertEqual(extrair(linha), "08/12/26")
        self.assertEqual(extrair([""] * 18), "")


if __name__ == "__main__":
    unittest.main()
