"""Regressões da edição parcial de propostas em um banco temporário."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class EdicaoAutomaticaTest(unittest.TestCase):
    def setUp(self):
        pasta = self.enterContext(tempfile.TemporaryDirectory())
        self.enterContext(patch.dict(os.environ, {
            "CRM_DATABASE": str(Path(pasta) / "crm.db"),
            "CRM_ANEXOS_DIR": str(Path(pasta) / "anexos"),
        }))
        arquivo_app = Path(__file__).resolve().parents[1] / "app.py"
        spec = importlib.util.spec_from_file_location("crm_edicao_automatica_teste", arquivo_app)
        self.crm = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.crm)
        self.crm.app.config.update(TESTING=True)
        self.cliente = self.crm.app.test_client()
        resposta = self.cliente.post("/nova", data={
            "nome": "Cliente Teste", "cpf": "168.995.350-09", "nb_matricula": "00123",
            "telefone": "11900000000", "produto": "Portabilidade com Refinanciamento",
            "numero_proposta": "900001", "banco_atual": "Banco Origem",
            "refin_troco": "700,00", "refin_comissao_percentual": "2", "refin_comissao": "14,00",
        })
        self.assertEqual(resposta.status_code, 302)
        with self.crm.app.app_context():
            self.proposta_id = self.crm.get_db().execute(
                "SELECT id FROM propostas WHERE numero_proposta = '900001'"
            ).fetchone()["id"]
        self.rota = f"/proposta/{self.proposta_id}/editar"

    def salvar(self, status_http=200, **campos):
        resposta = self.cliente.patch(self.rota, data=campos)
        self.assertEqual(resposta.status_code, status_http, resposta.get_json())
        return resposta.get_json()

    def test_edicoes_parciais_preservam_campos_e_refin_vinculado(self):
        self.assertEqual(self.salvar(parcela_atual="1591,98")["valores"]["parcela_atual"], "R$ 1.591,98")
        self.salvar(promotora="Promotora Teste")
        self.salvar(refin_comissao="20,25")
        self.salvar(status="Pago")
        with self.crm.app.app_context():
            proposta = self.crm.buscar_proposta(self.proposta_id)
            self.assertEqual(proposta["parcela_atual"], 1591.98)
            self.assertEqual(proposta["banco_atual"], "Banco Origem")
            self.assertEqual(proposta["promotora"], "Promotora Teste")
            self.assertIsNotNone(proposta["data_encerramento"])
            refin = self.crm.buscar_propostas_vinculadas(proposta)
            self.assertEqual(len(refin), 1)
            self.assertEqual(refin[0]["troco"], 700)
            self.assertEqual(refin[0]["comissao_percentual"], 2)
            self.assertEqual(refin[0]["comissao"], 20.25)

    def test_rejeita_lote_invalido_e_reenvio_nao_duplica_anotacao(self):
        self.salvar(422, parcela_atual="valor inválido", observacoes="A descartar")
        self.salvar(400, cliente_id="42")
        self.salvar(observacoes="Anotação de teste")
        self.salvar(observacoes="Anotação de teste")
        with self.crm.app.app_context():
            db = self.crm.get_db()
            notas = db.execute("SELECT texto FROM anotacoes WHERE proposta_id = ?", (self.proposta_id,))
            self.assertEqual([nota["texto"] for nota in notas], ["Anotação de teste"])

    def test_nova_identidade_reaproveita_cadastro_sem_sobrescrever_os_dados(self):
        resposta = self.cliente.post("/nova", data={
            "nome": "Outro Cliente", "cpf": "390.533.447-05", "nb_matricula": "00456",
            "telefone": "11911112222", "produto": "Portabilidade", "numero_proposta": "900003",
        })
        self.assertEqual(resposta.status_code, 302)
        dados = self.salvar(cpf="390.533.447-05", nb_matricula="00456")["valores"]
        self.assertEqual(dados["nome"], "Outro Cliente")
        self.assertEqual(dados["telefone"], "11911112222")
        with self.crm.app.app_context():
            tel = self.crm.get_db().execute("SELECT telefone FROM propostas WHERE numero_proposta = '900003'")
            self.assertEqual(tel.fetchone()["telefone"], "11911112222")
