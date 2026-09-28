using Microsoft.UI.Xaml;
using Microsoft.UI;
using Microsoft.UI.Windowing;
using Microsoft.UI.Xaml.Media;
using Windows.Graphics;
using WinRT.Interop;

namespace Jarvis.ControlHub.WinUI;

public sealed partial class MainWindow : Window
{
    private const int MinimumWindowWidth = 760;
    private const int MinimumWindowHeight = 560;
    private const int PreferredWindowWidth = 1600;
    private const int PreferredWindowHeight = 980;

    public MainWindow()
    {
        InitializeComponent();
        Title = "J.A.R.V.I.S Control Hub";
        var windowId = Win32Interop.GetWindowIdFromWindow(WindowNative.GetWindowHandle(this));
        var appWindow = AppWindow.GetFromWindowId(windowId);
        appWindow.Title = Title;
        // Startgröße an die reale Work Area klemmen (ohne Taskbar) und zentrieren: keine feste Bildschirmhöhe.
        var workArea = DisplayArea.GetFromWindowId(windowId, DisplayAreaFallback.Primary).WorkArea;
        var width = Math.Min(PreferredWindowWidth, workArea.Width);
        var height = Math.Min(PreferredWindowHeight, workArea.Height);
        appWindow.MoveAndResize(new RectInt32(
            workArea.X + (workArea.Width - width) / 2,
            workArea.Y + (workArea.Height - height) / 2,
            width,
            height));
        if (appWindow.Presenter is OverlappedPresenter presenter)
        {
            presenter.PreferredMinimumWidth = MinimumWindowWidth;
            presenter.PreferredMinimumHeight = MinimumWindowHeight;
        }
        SystemBackdrop = new MicaBackdrop();
        ExtendsContentIntoTitleBar = true;
        if (AppWindowTitleBar.IsCustomizationSupported())
        {
            var titleBar = appWindow.TitleBar;
            titleBar.PreferredHeightOption = TitleBarHeightOption.Tall;
            titleBar.ButtonBackgroundColor = Windows.UI.Color.FromArgb(0, 2, 14, 26);
            titleBar.ButtonInactiveBackgroundColor = Windows.UI.Color.FromArgb(0, 2, 14, 26);
            titleBar.ButtonForegroundColor = Windows.UI.Color.FromArgb(255, 172, 189, 202);
            titleBar.ButtonHoverBackgroundColor = Windows.UI.Color.FromArgb(255, 5, 23, 35);
            titleBar.ButtonHoverForegroundColor = Windows.UI.Color.FromArgb(255, 229, 236, 243);
            titleBar.ButtonPressedBackgroundColor = Windows.UI.Color.FromArgb(255, 18, 55, 75);
            titleBar.ButtonPressedForegroundColor = Windows.UI.Color.FromArgb(255, 229, 236, 243);
        }
        RootFrame.Navigate(typeof(Views.ShellPage));
        if (RootFrame.Content is Views.ShellPage shell)
        {
            SetTitleBar(shell.TitleBarDragRegion);
        }
    }
}
