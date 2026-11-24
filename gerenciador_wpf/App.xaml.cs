using System.Runtime.InteropServices;
using System.Windows;
namespace GerenciadorCRM;
public partial class App : Application
{
    [DllImport("shell32.dll", CharSet = CharSet.Unicode)]
    private static extern int SetCurrentProcessExplicitAppUserModelID(string appId);
    protected override void OnStartup(StartupEventArgs e)
    {
        SetCurrentProcessExplicitAppUserModelID("CRMConsignado.Gerenciador.WPF.v2");
        base.OnStartup(e);
    }
}
