"""Regressão da contagem de competências, sem acessar o banco operacional."""
import ast
import re
import unittest
from datetime import date
from pathlib import Path
from typing import Any


source = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))
helpers = {"limpar_texto", "competencia_mes", "parcelas_pagas_ate_competencia"}
namespace = {"re": re, "date": date, "Any": Any}
exec(compile(ast.Module(body=[node for node in source.body if isinstance(node, ast.FunctionDef)
                              and node.name in helpers], type_ignores=[]), "app.py", "exec"), namespace)
calcular = namespace["parcelas_pagas_ate_competencia"]


class CompetenciaTest(unittest.TestCase):
    def test_competencias_inclusivas_e_limites(self):
        casos = [
            ("10/2024", 82, date(2026, 9, 17), 24),
            ("10/2024", 72, date(2026, 9, 17), 24),
            ("09/2026", 96, date(2026, 9, 17), 1),
            ("10/2026", 96, date(2026, 9, 17), 0),
            ("12/2025", 12, date(2026, 1, 1), 2),
            ("01/2020", 12, date(2026, 9, 17), 12),
            ("", 72, date(2026, 9, 17), 0),
            ("10/2024", 0, date(2026, 9, 17), 0),
        ]
        for inicio, total, referencia, esperado in casos:
            with self.subTest(inicio=inicio, total=total, referencia=referencia):
                self.assertEqual(calcular(inicio, total, referencia), esperado)


if __name__ == "__main__":
    unittest.main()
