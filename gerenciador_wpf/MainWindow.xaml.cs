using System.Diagnostics;
using System.IO;
using System.Text;
using System.Text.Json;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;
using System.Windows.Interop;
using System.Windows.Threading;

namespace GerenciadorCRM;
public partial class MainWindow : Window
{
    private Process? motor;
    private bool encerrando;
    private bool reiniciando;
    private readonly Dictionary<string, Button> botoes;
    private readonly DispatcherTimer atualizadorLog = new() { Interval = TimeSpan.FromSeconds(1) };
    private DateTime ultimaAlteracaoLog = DateTime.MinValue;
    private long ultimoTamanhoLog = -1;
    public MainWindow()
    {
        InitializeComponent();
        botoes = new() { ["Abrir CRM"] = Abrir, ["Iniciar CRM"] = Iniciar, ["Reiniciar CRM"] = Reiniciar,
            ["Fechar CRM"] = Fechar, ["Fazer Git Pull"] = Pull, ["Ver log do CRM"] = VerLog,
            ["Abrir pasta"] = Pasta, ["Configurações"] = Configuracoes, ["Limpar histórico"] = Limpar };
        Loaded += (_, _) => { IniciarMotor(); atualizadorLog.Tick += (_, _) => AtualizarLog(); atualizadorLog.Start(); };
        Closing += (_, _) => { atualizadorLog.Stop(); encerrando = true; Enviar("sair"); };
    }
    private void IniciarMotor()
    {
        string pasta = AppContext.BaseDirectory;
        string script = Path.Combine(pasta, "gerenciador_wpf", "motor.py");
        string python = Path.Combine(pasta, ".venv", "Scripts", "python.exe");
        if (!File.Exists(python)) python = Path.Combine(pasta, "venv", "Scripts", "python.exe");
        if (!File.Exists(python)) python = "python";
        if (!File.Exists(script)) { Erro("Não encontrei os arquivos do gerenciador. Mantenha o executável na pasta do CRM."); return; }
        try {
            var info = new ProcessStartInfo(python) { UseShellExecute = false, CreateNoWindow = true,
                RedirectStandardInput = true, RedirectStandardOutput = true, RedirectStandardError = true,
                StandardOutputEncoding = Encoding.UTF8, StandardErrorEncoding = Encoding.UTF8, WorkingDirectory = pasta };
            info.ArgumentList.Add("-u"); info.ArgumentList.Add(script);
            info.Environment["PYTHONIOENCODING"] = "utf-8";
            info.Environment["CRM_GERENCIADOR_EXE"] = Environment.ProcessPath ?? Path.Combine(pasta, "GerenciadorCRM.exe");
            info.Environment["CRM_GERENCIADOR_HWND"] = new WindowInteropHelper(this).Handle.ToInt64().ToString();
            motor = new Process { StartInfo = info, EnableRaisingEvents = true };
            motor.OutputDataReceived += (_, e) => { if (e.Data != null) Dispatcher.BeginInvoke(() => Processar(e.Data)); };
            motor.ErrorDataReceived += (_, e) => { if (!string.IsNullOrWhiteSpace(e.Data)) Dispatcher.BeginInvoke(() => Registrar(e.Data)); };
            motor.Exited += (_, _) => Dispatcher.BeginInvoke(() => {
                if (encerrando) return;
                if (reiniciando) { encerrando = true; Close(); }
                else Erro("A conexão com o gerenciador foi encerrada. Feche e abra o programa novamente.");
            });
            motor.Start(); motor.BeginOutputReadLine(); motor.BeginErrorReadLine();
        } catch (Exception ex) { Erro("Não foi possível iniciar o gerenciador: " + ex.Message); }
    }
    private void Processar(string linha)
    {
        try {
            using var json = JsonDocument.Parse(linha); var raiz = json.RootElement;
            string tipo = raiz.GetProperty("tipo").GetString() ?? "";
            if (tipo == "log") Registrar(raiz.GetProperty("texto").GetString() ?? "");
            else if (tipo == "limpar") Historico.Clear();
            else if (tipo == "reiniciar") reiniciando = true;
            else if (tipo == "dialogo") {
                string modalidade = raiz.GetProperty("modalidade").GetString() ?? "showinfo";
                string titulo = raiz.GetProperty("titulo").GetString() ?? "Gerenciador CRM";
                string mensagem = raiz.GetProperty("mensagem").GetString() ?? "";
                var botoesDialogo = modalidade == "askyesno" ? MessageBoxButton.YesNo : MessageBoxButton.OK;
                var icone = modalidade switch { "askyesno" => MessageBoxImage.Question, "showerror" => MessageBoxImage.Error, "showwarning" => MessageBoxImage.Warning, _ => MessageBoxImage.Information };
                var resposta = MessageBox.Show(this, mensagem, titulo, botoesDialogo, icone);
                Enviar(resposta == MessageBoxResult.Yes ? "resposta:sim" : "resposta:nao");
            }
            else if (tipo == "estado") {
                StatusText.Text = raiz.GetProperty("status").GetString();
                ProjectText.Text = raiz.GetProperty("projeto").GetString(); GitText.Text = raiz.GetProperty("git").GetString();
                try { StatusText.Foreground = (Brush)new BrushConverter().ConvertFromString(raiz.GetProperty("cor").GetString() ?? "#137A50")!; } catch { }
                foreach (var par in botoes) if (raiz.GetProperty("botoes").TryGetProperty(par.Key, out var ativo)) par.Value.IsEnabled = ativo.GetBoolean();
            }
        } catch (JsonException) { Registrar(linha); }
    }
    private void MostrarPainel(object sender, RoutedEventArgs e)
    {
        TelaLogs.Visibility = Visibility.Collapsed;
        PainelPrincipal.Visibility = Visibility.Visible;
        MenuPainel.Background = (Brush)new BrushConverter().ConvertFromString("#235B49")!;
        MenuLogs.Background = Brushes.Transparent;
    }
    private void MostrarLogs(object sender, RoutedEventArgs e)
    {
        PainelPrincipal.Visibility = Visibility.Collapsed;
        TelaLogs.Visibility = Visibility.Visible;
        MenuLogs.Background = (Brush)new BrushConverter().ConvertFromString("#235B49")!;
        MenuPainel.Background = Brushes.Transparent;
        AtualizarLog();
    }
    private void AtualizarLog()
    {
        if (TelaLogs.Visibility != Visibility.Visible) return;
        string pasta = Environment.GetEnvironmentVariable("APPDATA") ?? Environment.GetFolderPath(Environment.SpecialFolder.ApplicationData);
        string caminho = Path.Combine(pasta, "GerenciadorCRM", "crm.log");
        try {
            var arquivo = new FileInfo(caminho);
            if (!arquivo.Exists) {
                ultimaAlteracaoLog = DateTime.MinValue; ultimoTamanhoLog = -1;
                EstadoLog.Text = "AGUARDANDO LOG";
                LogTempoReal.Text = "O log aparecerá aqui quando o CRM for iniciado pelo gerenciador.";
                return;
            }
            if (arquivo.Length == ultimoTamanhoLog && arquivo.LastWriteTimeUtc == ultimaAlteracaoLog) return;
            using var fluxo = new FileStream(caminho, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete);
            bool parcial = fluxo.Length > 131072;
            if (parcial) fluxo.Seek(-131072, SeekOrigin.End);
            using var leitor = new StreamReader(fluxo, Encoding.UTF8, true);
            if (parcial) leitor.ReadLine();
            string conteudo = leitor.ReadToEnd();
            LogTempoReal.Text = (parcial ? "Exibindo as mensagens mais recentes.\n\n" : "") + conteudo;
            LogTempoReal.ScrollToEnd();
            ultimaAlteracaoLog = arquivo.LastWriteTimeUtc; ultimoTamanhoLog = arquivo.Length;
            EstadoLog.Text = "ATUALIZAÇÃO AUTOMÁTICA";
        } catch (IOException) { EstadoLog.Text = "AGUARDANDO ACESSO AO LOG"; }
          catch (UnauthorizedAccessException) { EstadoLog.Text = "SEM ACESSO AO LOG"; }
    }
    private void Registrar(string texto) { Historico.AppendText($"{DateTime.Now:HH:mm:ss}  {texto}{Environment.NewLine}"); Historico.ScrollToEnd(); }
    private void Erro(string texto) { StatusText.Text = "Gerenciador indisponível"; Registrar(texto); foreach (var botao in botoes.Values) botao.IsEnabled = false; MessageBox.Show(texto, "Gerenciador CRM", MessageBoxButton.OK, MessageBoxImage.Error); }
    private void Enviar(string acao) { try { if (motor is { HasExited: false }) { motor.StandardInput.WriteLine(acao); motor.StandardInput.Flush(); } } catch (IOException) { } catch (InvalidOperationException) { } }
    private void Acao_Click(object sender, RoutedEventArgs e) { if (sender is Button botao && botao.Tag is string acao) Enviar(acao); }
}
