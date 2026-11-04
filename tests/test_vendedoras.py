"""Separação por vendedora com banco temporário (sem tocar no operacional)."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


def carregar_modulo(banco: Path):
    os.environ["CRM_DATABASE"] = str(banco)
    spec = importlib.util.spec_from_file_location("crm_vendedora_teste", Path(__file__).resolve().parents[1] / "app.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


class VendedorasTest(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.crm = carregar_modulo(Path(self.pasta.name) / "teste.db")
        self.crm.app.config.update(TESTING=True, SECRET_KEY="teste-vendedoras")
        self.contexto = self.crm.app.app_context()
        self.contexto.push()
        self.crm.init_db()
        self.db = self.crm.get_db()
        self.db.execute(
            """
            INSERT INTO propostas (nome, cpf, tipo_cliente, produto, comissao, status,
                                   responsavel, data_criacao, data_atualizacao)
            VALUES ('Cliente Oliana', '111', 'INSS', 'Portabilidade', 100, 'Pago', 'Oliana',
                    '2026-11-02 10:00:00', '2026-11-02 10:00:00')
            """
        )
        self.db.execute(
            """
            INSERT INTO propostas (nome, cpf, tipo_cliente, produto, comissao, status,
                                   responsavel, data_criacao, data_atualizacao)
            VALUES ('Cliente Tatiana', '222', 'INSS', 'Portabilidade', 250, 'Pago', 'Tatiana',
                    '2026-11-02 10:00:00', '2026-11-02 10:00:00')
            """
        )
        self.db.commit()

    def tearDown(self):
        self.contexto.pop()
        os.environ.pop("CRM_DATABASE", None)
        self.pasta.cleanup()

    def selecionar(self, cliente, nome):
        resposta = cliente.post("/vendedora/selecionar", data={"vendedora": nome, "next": "/funil"})
        self.assertEqual(resposta.status_code, 302)

    def test_historico_e_filtro_por_vendedora(self):
        self.assertEqual(
            [item["nome"] for item in self.crm.listar_vendedoras(apenas_ativas=True)],
            ["Oliana", "Tatiana"],
        )
        with self.crm.app.test_client() as cliente:
            # Sem escolha explícita, o navegador começa na Oliana.
            pagina = cliente.get("/dashboard?mes=2026-11").get_data(as_text=True)
            self.assertIn("100,00", pagina)
            self.assertNotIn("250,00", pagina)

            self.selecionar(cliente, "Tatiana")
            pagina = cliente.get("/dashboard?mes=2026-11").get_data(as_text=True)
            self.assertIn("250,00", pagina)
            self.assertNotIn("100,00", pagina)

            busca = cliente.get("/api/propostas/buscar?q=Cliente").get_json()
            self.assertEqual([item["nome"] for item in busca], ["Cliente Tatiana"])

            with self.crm.app.test_request_context("/proposta/nova"):
                self.crm.session["vendedora_atual"] = "Tatiana"
                self.assertEqual(self.crm.proposta_vazia()["responsavel"], "Tatiana")

    def test_dashboard_somente_mes_mantem_filtro_da_vendedora(self):
        self.db.execute(
            """INSERT INTO propostas (nome, cpf, tipo_cliente, produto, comissao, status,
                                      responsavel, data_criacao, data_atualizacao)
               VALUES ('CIP Tatiana', '666', 'INSS', 'Portabilidade', 77, 'Aguardando CIP',
                       'Tatiana', '2026-11-02 10:00:00', '2026-11-02 10:00:00')"""
        )
        self.db.execute(
            """INSERT INTO propostas (nome, cpf, tipo_cliente, produto, comissao, status,
                                      responsavel, data_criacao, data_atualizacao)
               VALUES ('CIP mes anterior', '777', 'INSS', 'Portabilidade', 999, 'Aguardando CIP',
                       'Tatiana', '2026-10-02 10:00:00', '2026-10-02 10:00:00')"""
        )
        self.db.commit()

        with self.crm.app.test_request_context("/dashboard"):
            self.crm.session["vendedora_atual"] = "Tatiana"
            dados = self.crm.consulta_dashboard("2026-11", incluir_anteriores=False)
        self.assertEqual(dados["comissao_prevista"], 77.0)

        with self.crm.app.test_request_context("/dashboard"):
            self.crm.session["vendedora_atual"] = "Oliana"
            dados = self.crm.consulta_dashboard("2026-11", incluir_anteriores=False)
        self.assertEqual(dados["comissao_prevista"], 0.0)

    def test_migracao_atribui_historico_sem_vendedora_a_oliana(self):
        self.db.execute(
            """INSERT INTO propostas (nome, cpf, tipo_cliente, produto, status, responsavel,
                                      data_criacao, data_atualizacao)
               VALUES ('Sem vendedora', '333', 'INSS', 'Portabilidade', 'Novo lead', '',
                       '2026-11-02 10:00:00', '2026-11-02 10:00:00')"""
        )
        self.db.execute(
            """INSERT INTO propostas (nome, cpf, tipo_cliente, produto, status, responsavel,
                                      data_criacao, data_atualizacao)
               VALUES ('Nome antigo', '444', 'INSS', 'Portabilidade', 'Novo lead', 'TATY',
                       '2026-11-02 10:00:00', '2026-11-02 10:00:00')"""
        )
        self.db.commit()
        self.crm.init_db()
        responsaveis = {
            linha["nome"]: linha["responsavel"]
            for linha in self.db.execute(
                "SELECT nome, responsavel FROM propostas WHERE nome IN ('Sem vendedora', 'Nome antigo', 'Cliente Tatiana')"
            )
        }
        self.assertEqual(responsaveis["Sem vendedora"], "Oliana")
        self.assertEqual(responsaveis["Nome antigo"], "Oliana")
        self.assertEqual(responsaveis["Cliente Tatiana"], "Tatiana")

    def test_cadastro_renomeacao_e_desativacao(self):
        with self.crm.app.test_client() as cliente:
            cliente.post("/configuracoes", data={"acao": "adicionar_vendedora", "nome": "Nova Vendedora"})
            nova = self.db.execute("SELECT * FROM vendedoras WHERE nome = 'Nova Vendedora'").fetchone()
            self.assertIsNotNone(nova)
            self.db.execute("UPDATE propostas SET responsavel = 'Nova Vendedora' WHERE nome = 'Cliente Tatiana'")
            self.db.commit()

            cliente.post(
                "/configuracoes",
                data={"acao": "renomear_vendedora", "vendedora_id": nova["id"], "nome": "Vendedora Renomeada"},
            )
            self.assertIsNotNone(
                self.db.execute("SELECT 1 FROM vendedoras WHERE nome = 'Vendedora Renomeada'").fetchone()
            )
            self.assertEqual(
                self.db.execute("SELECT responsavel FROM propostas WHERE nome = 'Cliente Tatiana'").fetchone()["responsavel"],
                "Vendedora Renomeada",
            )

            cliente.post("/configuracoes", data={"acao": "alternar_vendedora", "vendedora_id": nova["id"]})
            self.assertEqual(
                self.db.execute("SELECT ativo FROM vendedoras WHERE id = ?", (nova["id"],)).fetchone()["ativo"],
                0,
            )

    def test_renomear_oliana_nao_recria_oliana_ao_reiniciar(self):
        self.db.execute(
            "INSERT OR REPLACE INTO configuracoes (chave, valor, atualizado_em) VALUES ('saldo_em_conta:Oliana', '123', ?)",
            (self.crm.agora_iso(),),
        )
        self.db.commit()
        oliana_id = self.db.execute("SELECT id FROM vendedoras WHERE nome = 'Oliana'").fetchone()["id"]
        with self.crm.app.test_client() as cliente:
            cliente.post(
                "/configuracoes",
                data={"acao": "renomear_vendedora", "vendedora_id": oliana_id, "nome": "Oliana Renomeada"},
            )

        self.crm.init_db()

        self.assertEqual(
            [linha["nome"] for linha in self.db.execute("SELECT nome FROM vendedoras ORDER BY ordem")],
            ["Oliana Renomeada", "Tatiana"],
        )
        self.assertEqual(
            self.db.execute("SELECT responsavel FROM propostas WHERE nome = 'Cliente Oliana'").fetchone()["responsavel"],
            "Oliana Renomeada",
        )
        self.assertEqual(
            self.db.execute(
                "SELECT valor FROM configuracoes WHERE chave = 'saldo_em_conta:Oliana Renomeada'"
            ).fetchone()["valor"],
            "123",
        )

    def test_refin_herda_vendedora_da_portabilidade(self):
        self.db.execute(
            """INSERT INTO propostas (nome, cpf, tipo_cliente, produto, numero_proposta, status,
                                      responsavel, data_criacao, data_atualizacao)
               VALUES ('Portabilidade Tatiana', '555', 'INSS', 'Portabilidade com Refinanciamento',
                       '900001', 'Novo lead', 'Tatiana', '2026-11-03 10:00:00', '2026-11-03 10:00:00')"""
        )
        self.db.commit()
        port_id = self.db.execute("SELECT id FROM propostas WHERE numero_proposta = '900001'").fetchone()["id"]

        with self.crm.app.test_client() as cliente:
            self.selecionar(cliente, "Tatiana")
            resposta = cliente.post(f"/proposta/{port_id}/criar-refin-vinculado")
            self.assertEqual(resposta.status_code, 302)

        refin = self.db.execute(
            "SELECT * FROM propostas WHERE numero_port_vinculada = '900001'"
        ).fetchone()
        self.assertIsNotNone(refin)
        self.assertEqual(refin["produto"], "Refinanciamento")
        self.assertEqual(refin["responsavel"], "Tatiana")


if __name__ == "__main__":
    unittest.main()
