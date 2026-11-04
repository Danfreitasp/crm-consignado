"""Comissões pagas e ainda não sacadas são migradas para o mês atual."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


def carregar_modulo(banco: Path):
    os.environ["CRM_DATABASE"] = str(banco)
    spec = importlib.util.spec_from_file_location(
        "crm_encerradas_carryover_teste",
        Path(__file__).resolve().parents[1] / "app.py",
    )
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def mes_anterior(mes: str) -> str:
    ano, numero_mes = (int(parte) for parte in mes.split("-"))
    if numero_mes == 1:
        return f"{ano - 1}-12"
    return f"{ano}-{numero_mes - 1:02d}"


class EncerradasCarryoverTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.crm = carregar_modulo(Path(self.pasta.name) / "teste.db")
        self.crm.app.config.update(TESTING=True, SECRET_KEY="teste-encerradas-carryover")
        self.contexto = self.crm.app.app_context()
        self.contexto.push()
        self.crm.init_db()
        self.db = self.crm.get_db()
        self.mes_atual = self.crm.mes_atual()
        self.mes_anterior = mes_anterior(self.mes_atual)

    def tearDown(self):
        self.contexto.pop()
        os.environ.pop("CRM_DATABASE", None)
        self.pasta.cleanup()

    def inserir_proposta(
        self,
        nome: str,
        mes: str,
        comissao: float,
        status: str = "Pago",
        valor_sacado: str = "NÃO",
        valor_caiu_promotora: str = "SIM",
        produto: str = "Portabilidade",
        numero_proposta: str = "",
        numero_port_vinculada: str = "",
        portabilidade_id: int | None = None,
    ) -> int:
        cursor = self.db.execute(
            """
            INSERT INTO propostas (
                nome, cpf, tipo_cliente, produto, comissao, status, responsavel,
                valor_sacado, valor_caiu_promotora, numero_proposta,
                numero_port_vinculada, portabilidade_id,
                data_criacao, data_atualizacao, data_encerramento
            )
            VALUES (?, '000', 'INSS', ?, ?, ?, 'Oliana', ?, ?, ?, ?, ?,
                    ?, ?, ?)
            """,
            (
                nome,
                produto,
                comissao,
                status,
                valor_sacado,
                valor_caiu_promotora,
                numero_proposta,
                numero_port_vinculada,
                portabilidade_id,
                f"{mes}-01 09:00:00",
                f"{mes}-10 10:00:00",
                f"{mes}-10 10:00:00" if status != "Aguardando CIP" else None,
            ),
        )
        self.db.commit()
        return cursor.lastrowid

    def dashboard(self, mes: str, incluir_anteriores: bool = True):
        with self.crm.app.test_request_context("/dashboard"):
            self.crm.session["vendedora_atual"] = "Oliana"
            return self.crm.consulta_dashboard(mes, incluir_anteriores)

    def test_paga_nao_sacada_de_mes_anterior_migra_para_o_mes_atual(self):
        self.inserir_proposta("Paga pendente", self.mes_anterior, 100)

        atual = self.dashboard(self.mes_atual)
        self.assertEqual(atual["pagas"], 1)
        self.assertEqual(atual["pagas_anteriores"], 1)
        self.assertEqual(atual["comissao_paga"], 100.0)
        self.assertEqual(atual["valor_a_sacar"], 100.0)
        self.assertEqual(atual["falta_cair_promotora"], 0.0)

        original = self.dashboard(self.mes_anterior)
        self.assertEqual(original["pagas"], 0)
        self.assertEqual(original["comissao_paga"], 0.0)

    def test_falta_cair_de_mes_anterior_migra_para_o_mes_atual(self):
        self.inserir_proposta(
            "Falta cair",
            self.mes_anterior,
            70,
            valor_caiu_promotora="NÃO",
        )

        atual = self.dashboard(self.mes_atual)
        self.assertEqual(atual["pagas"], 1)
        self.assertEqual(atual["falta_cair_promotora"], 70.0)
        self.assertEqual(atual["valor_a_sacar"], 0.0)

    def test_paga_sacada_nao_entra_no_mes_atual(self):
        self.inserir_proposta(
            "Já sacada",
            self.mes_anterior,
            50,
            valor_sacado="SIM",
        )

        atual = self.dashboard(self.mes_atual)
        self.assertEqual(atual["pagas"], 0)
        self.assertEqual(atual["pagas_anteriores"], 0)
        self.assertEqual(atual["comissao_paga"], 0.0)
        self.assertEqual(atual["valor_ja_sacado"], 0.0)

        original = self.dashboard(self.mes_anterior)
        self.assertEqual(original["pagas"], 1)
        self.assertEqual(original["comissao_paga"], 50.0)
        self.assertEqual(original["valor_ja_sacado"], 50.0)

    def test_perdida_de_mes_anterior_nao_entra_no_mes_atual(self):
        self.inserir_proposta(
            "Perdida antiga",
            self.mes_anterior,
            30,
            status="Perdido / Cancelado",
        )

        self.assertEqual(self.dashboard(self.mes_atual)["perdidas"], 0)
        self.assertEqual(self.dashboard(self.mes_anterior)["perdidas"], 1)

    def test_somente_mes_nao_remove_comissao_pendente_anterior(self):
        self.inserir_proposta(
            "Ativa antiga",
            self.mes_anterior,
            40,
            status="Aguardando CIP",
            valor_sacado="NÃO",
            valor_caiu_promotora="NÃO",
        )
        self.inserir_proposta("Paga pendente", self.mes_anterior, 100)

        sem_anteriores = self.dashboard(self.mes_atual, incluir_anteriores=False)
        self.assertEqual(sem_anteriores["total"], 0)
        self.assertEqual(sem_anteriores["pagas"], 1)
        self.assertEqual(sem_anteriores["comissao_paga"], 100.0)

        com_anteriores = self.dashboard(self.mes_atual, incluir_anteriores=True)
        self.assertEqual(com_anteriores["total"], 1)
        self.assertEqual(com_anteriores["pagas"], 1)
        self.assertEqual(com_anteriores["comissao_paga"], 100.0)

    def test_port_e_refin_pendentes_contam_uma_operacao(self):
        port_id = self.inserir_proposta(
            "Port pendente",
            self.mes_anterior,
            100,
            produto="Portabilidade com Refinanciamento",
            numero_proposta="900001",
        )
        self.inserir_proposta(
            "Refin pendente",
            self.mes_anterior,
            20,
            produto="Refinanciamento",
            numero_proposta="900002",
            numero_port_vinculada="900001",
            portabilidade_id=port_id,
        )

        atual = self.dashboard(self.mes_atual)
        self.assertEqual(atual["pagas"], 1)
        self.assertEqual(atual["comissao_paga"], 120.0)

        original = self.dashboard(self.mes_anterior)
        self.assertEqual(original["pagas"], 0)
        self.assertEqual(original["comissao_paga"], 0.0)

    def test_rota_encerradas_mostra_pendentes_no_mes_atual(self):
        self.inserir_proposta("Paga pendente", self.mes_anterior, 100)

        with self.crm.app.test_client() as cliente:
            with cliente.session_transaction() as sessao:
                sessao["vendedora_atual"] = "Oliana"
            atual = cliente.get(f"/encerradas?mes={self.mes_atual}").get_data(as_text=True)
            original = cliente.get(f"/encerradas?mes={self.mes_anterior}").get_data(as_text=True)

        self.assertIn("Paga pendente", atual)
        self.assertNotIn("Paga pendente", original)


if __name__ == "__main__":
    unittest.main()
