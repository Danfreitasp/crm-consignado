"""Conecta a interface WPF às operações existentes do gerenciador."""
import json
import os
import ctypes
from pathlib import Path
import queue
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import gerenciador_crm as base

# O processo que precisa ser liberado em atualizações é a interface WPF.
exe_wpf = os.environ.get("CRM_GERENCIADOR_EXE")
if exe_wpf:
    base.caminho_exe_atual = lambda: Path(exe_wpf)


def enviar(tipo, **dados):
    print(json.dumps({"tipo": tipo, **dados}, ensure_ascii=False), flush=True)


class Motor(base.GerenciadorCRM):
    def _reiniciar_gerenciador(self):
        super()._reiniciar_gerenciador()
        try:
            self.winfo_exists()
        except base.tk.TclError:
            enviar("reiniciar")

    def _log(self, mensagem, nivel="info"):
        super()._log(mensagem, nivel)
        enviar("log", texto=mensagem, nivel=nivel)

    def _atualizar_status(self):
        super()._atualizar_status()
        if hasattr(self, "_rotulo_git"):
            self._emitir_estado()

    def _emitir_estado(self):
        botoes = {nome: str(botao.cget("state")) != "disabled" for nome, botao in self._botoes_por_nome.items()}
        enviar("estado", status=self._rotulo_status.cget("text"), cor=self._rotulo_status.cget("fg"),
               projeto=self._rotulo_projeto.cget("text"), git=self._rotulo_git.cget("text"), botoes=botoes)


def main():
    motor = Motor()
    motor.withdraw()
    fila = queue.Queue()
    respostas = queue.Queue()
    mensagens_originais = {nome: getattr(base.messagebox, nome) for nome in ("askyesno", "showerror", "showwarning", "showinfo")}

    def dialogo(nome, titulo, mensagem, **opcoes):
        # Diálogos de validação pertencentes à janela de configurações continuam
        # vinculados a ela. Os demais pertencem à janela principal WPF.
        parent = opcoes.get("parent")
        if parent is not None and parent is not motor:
            return mensagens_originais[nome](titulo, mensagem, **opcoes)
        enviar("dialogo", modalidade=nome, titulo=titulo, mensagem=mensagem)
        try:
            resposta = respostas.get(timeout=300)
        except queue.Empty:
            resposta = False
        return resposta if nome == "askyesno" else "ok"

    for nome in mensagens_originais:
        setattr(base.messagebox, nome, lambda titulo, mensagem, _nome=nome, **kwargs: dialogo(_nome, titulo, mensagem, **kwargs))

    def preparar_configuracoes(janela):
        # O handle de Tk é filho de um wrapper nativo; o wrapper deve ser
        # associado à janela WPF para não ficar escondido atrás dela.
        def associar():
            hwnd_wpf = int(os.environ.get("CRM_GERENCIADOR_HWND", "0"))
            if not hwnd_wpf or not janela.winfo_exists():
                return
            user32 = ctypes.windll.user32
            user32.GetParent.argtypes = [ctypes.c_void_p]
            user32.GetParent.restype = ctypes.c_void_p
            user32.SetWindowLongPtrW.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_ssize_t]
            user32.SetWindowLongPtrW.restype = ctypes.c_ssize_t
            hwnd_tk = user32.GetParent(janela.winfo_id()) or janela.winfo_id()
            user32.SetWindowLongPtrW(hwnd_tk, -8, hwnd_wpf)
            janela.lift()
            janela.focus_force()
        janela.after_idle(associar)

    motor._preparar_janela_configuracoes = preparar_configuracoes
    comandos = {"abrir": motor.abrir_crm, "iniciar": motor.iniciar_crm, "reiniciar": motor.reiniciar_crm,
                "fechar": motor.fechar_crm, "pull": motor.git_pull, "log": motor.ver_log_crm,
                "pasta": motor.abrir_pasta, "configuracoes": motor.abrir_configuracoes,
                "limpar": motor.limpar_historico, "sair": motor._ao_fechar}

    def ler():
        for linha in sys.stdin:
            comando = linha.strip()
            if comando.startswith("resposta:"):
                respostas.put(comando == "resposta:sim")
            else:
                fila.put(comando)
        respostas.put(False)
        fila.put("sair")

    def drenar():
        try:
            while True:
                comando = fila.get_nowait()
                if comando in comandos:
                    comandos[comando]()
                    if comando == "limpar":
                        enviar("limpar")
        except queue.Empty:
            pass
        motor._emitir_estado()
        motor.after(1000, drenar)

    threading.Thread(target=ler, daemon=True).start()
    motor.after(100, drenar)
    motor.mainloop()


if __name__ == "__main__":
    main()
