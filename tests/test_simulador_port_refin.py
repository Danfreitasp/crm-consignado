"""Regressões financeiras sem abrir o banco operacional."""
import ast
import calendar
import unittest
from datetime import date, timedelta
from pathlib import Path
from typing import Any

source = ast.parse((Path(__file__).resolve().parents[1] / "app.py").read_text(encoding="utf-8"))
namespace = {"Any": Any, "calendar": calendar, "date": date, "timedelta": timedelta,
             "limpar_texto": lambda value: str(value or "").strip(),
             "montar_mensagem_simulador_port_refin": lambda *_: ""}
constants = {"INSS_PORT_REFIN_TABELAS", "INSS_PORT_REFIN_FATORES_LIQUIDOS", "INSS_PORT_REFIN_FATORES_MESMO_DIA"}
functions = {"datas_simulador_quali", "dias_fluxo_quali", "coeficiente_fluxo_quali", "taxa_fluxo_quali", "calcular_simulador_port_refin"}
nodes = [node for node in source.body
         if (isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in constants for t in node.targets))
         or (isinstance(node, ast.FunctionDef) and node.name in functions)]
exec(compile(ast.Module(body=nodes, type_ignores=[]), "app.py", "exec"), namespace)
calcular = namespace["calcular_simulador_port_refin"]


class PortRefinTest(unittest.TestCase):
    def test_newcorban_0710_fluxo_padrao_e_todas_taxas(self):
        for codigo, esperado in [("402", 5337.15), ("401", 4992.18), ("400", 4653.48),
                                 ("399", 4431.08), ("398", 4102.50), ("406", 3886.73)]:
            with self.subTest(tabela=codigo):
                result = calcular(dict(tabela_port_refin=codigo, parcela_atual=638.48,
                                      saldo_quitacao=24882.19, prazo_contrato=84, parcelas_pagas=25,
                                      data_simulacao="2026-10-07"))
                self.assertEqual(result["troco"], esperado)
                self.assertEqual(result["saldo_considerado"], 24882.19)
                self.assertTrue(result["operacao_viavel"])

    def test_newcorban_variacao_da_parcela(self):
        for parcela, esperado in [(900, 17372.51), (1000, 21974.58)]:
            result = calcular(dict(tabela_port_refin="402", parcela_atual=638.48,
                                  nova_parcela=parcela, saldo_quitacao=24882.19,
                                  prazo_contrato=84, parcelas_pagas=25, data_simulacao="2026-10-07"))
            # A estimativa líquida pode variar poucos centavos do arredondamento do banco.
            self.assertAlmostEqual(result["troco"], esperado, delta=.05)

    def test_datas_sugeridas_calendario_e_referencia(self):
        datas = namespace["datas_simulador_quali"](date(2026, 10, 7))
        self.assertEqual(datas["data_refinanciamento"], "2026-10-07")
        self.assertEqual(datas["primeiro_vencimento_refin"], "2026-12-07")
        self.assertEqual(namespace["datas_simulador_quali"](date(2027, 12, 31))["primeiro_vencimento_refin"], "2028-02-29")

    def dados(self, **changes):
        dados = dict(tabela_port_refin="402", parcela_atual=786.73, saldo_quitacao=36977.65,
                     prazo_contrato=96, parcelas_pagas=14, descontos_banco=None,
                     data_simulacao="2026-09-30", data_refinanciamento="2026-10-03",
                     primeiro_vencimento_port="2026-11-25", primeiro_vencimento_refin="2026-12-25")
        dados.update(changes)
        return dados

    def test_exemplo_banco_sem_troco_nao_libera_proposta(self):
        result = calcular(self.dados())
        self.assertEqual(result["valor_contrato"], 36999.06)
        self.assertEqual(result["saldo_considerado"], 37030.65)
        self.assertEqual(result["troco"], -31.59)
        self.assertFalse(result["operacao_viavel"])
        self.assertEqual(result["comissao_refinanciamento"], 0)

    def test_segunda_simulacao_confirmada_na_quali(self):
        result = calcular(self.dados(parcela_atual=484.52, saldo_quitacao=22338.04, parcelas_pagas=17))
        self.assertEqual(result["valor_contrato"], 22786.45)
        self.assertEqual(result["troco"], 402.38)
        self.assertTrue(result["operacao_viavel"])
        self.assertEqual(result["comissao_refinanciamento"], 9.86)

    def test_parcelas_e_taxas_conferidas_no_newcorban(self):
        for parcela, esperado in [(800, 572.50), (900, 5116.80), (1000, 9661.10)]:
            with self.subTest(parcela=parcela):
                self.assertEqual(calcular(self.dados(nova_parcela=parcela))["troco"], esperado)
        for codigo, esperado in [("401", 4627.96), ("400", 4148.03), ("399", 3832.94), ("398", 3367.44), ("406", 3061.77)]:
            with self.subTest(tabela=codigo):
                self.assertEqual(calcular(self.dados(tabela_port_refin=codigo, nova_parcela=900))["troco"], esperado)

    def test_descontos_manuais_substituem_estimativa_e_zero_e_explicito(self):
        self.assertEqual(calcular(self.dados(descontos_banco=53))["troco"], -31.59)
        self.assertEqual(calcular(self.dados(descontos_banco=0))["troco"], 21.41)
        self.assertFalse(calcular(self.dados(descontos_banco=-53))["operacao_viavel"])

    def test_todas_tabelas_atualizam_quitacao_integral(self):
        for codigo in namespace["INSS_PORT_REFIN_TABELAS"]:
            with self.subTest(tabela=codigo):
                self.assertEqual(calcular(self.dados(tabela_port_refin=codigo))["saldo_considerado"], 37030.65)

    def test_calculo_livre_e_margem_negativa(self):
        result = calcular(self.dados(tabela_port_refin="", coeficiente_port_refin=.02, novo_prazo=108,
                                    descontos_banco=53, margem_disponivel_importada=-100, deduzir_negativo="sim"))
        self.assertEqual(result["nova_parcela"], 686.73)
        self.assertEqual(result["valor_contrato"], 34336.5)
        self.assertEqual(result["troco"], -2694.15)

    def test_datas_invalidas_e_parcelas_restantes_obrigatorias(self):
        for changes in [dict(data_refinanciamento="2026-09-29"), dict(primeiro_vencimento_refin="2026-10-02"),
                        dict(data_simulacao="inválida"), dict(parcelas_pagas=96)]:
            with self.subTest(changes=changes):
                self.assertFalse(calcular(self.dados(**changes))["operacao_viavel"])
                self.assertTrue(calcular(self.dados(**changes))["erros"])

    def test_fluxo_ajusta_fim_de_mes_e_ano_bissexto(self):
        dias = namespace["dias_fluxo_quali"](date(2028, 1, 31), date(2028, 1, 1), 3)
        self.assertEqual(dias, [30, 59, 90])
        alterado = calcular(self.dados(primeiro_vencimento_refin="2027-01-25"))
        self.assertLess(alterado["valor_contrato"], 36999.06)


if __name__ == "__main__":
    unittest.main()
