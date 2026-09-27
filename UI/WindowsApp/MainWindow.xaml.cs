using System;
using System.Collections.Generic;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Controls;
using System.Windows.Media;

namespace Jarvis.ControlHub;

public partial class MainWindow : Window
{
    private static readonly Brush ActiveNavigationBrush = new SolidColorBrush(Color.FromRgb(24, 59, 58));
    private static readonly Brush ActiveNavigationForeground = new SolidColorBrush(Color.FromRgb(85, 199, 181));
    private static readonly Brush InactiveNavigationBrush = Brushes.Transparent;
    private static readonly Brush InactiveNavigationForeground = new SolidColorBrush(Color.FromRgb(169, 182, 196));

    private readonly Dictionary<string, FrameworkElement> _pages;

    public MainWindow()
    {
        InitializeComponent();
        DataContext = new MainWindowViewModel();
        _pages = new Dictionary<string, FrameworkElement>(StringComparer.Ordinal)
        {
            ["Dashboard"] = DashboardPage,
            ["Live"] = LivePage,
            ["Systemhistorie"] = HealthPage,
            ["Runtime Supervisor"] = RuntimePage,
            ["AI Engines"] = AiPage,
            ["Voice"] = VoicePage,
            ["Memory"] = MemoryPage,
            ["Skills / Tools"] = SkillsPage,
            ["Logs"] = LogsPage,
            ["Agents"] = AgentsPage,
            ["Automations"] = AutomationsPage,
            ["Settings"] = SettingsPage,
        };

        SelectPage("Dashboard");
        Loaded += MainWindow_Loaded;
        Closed += (_, _) => (DataContext as MainWindowViewModel)?.Dispose();
    }

    private async void MainWindow_Loaded(object sender, RoutedEventArgs e)
    {
        await RunViewModelActionAsync(viewModel => viewModel.RefreshAsync());
    }

    private void Navigation_Click(object sender, RoutedEventArgs e)
    {
        if (sender is not Button { Tag: string pageName })
        {
            return;
        }

        SelectPage(pageName);
    }

    private void SelectPage(string pageName)
    {
        if (!_pages.TryGetValue(pageName, out var selectedPage))
        {
            return;
        }

        foreach (var page in _pages.Values)
        {
            page.Visibility = ReferenceEquals(page, selectedPage) ? Visibility.Visible : Visibility.Collapsed;
        }

        foreach (var button in FindVisualChildren<Button>(this))
        {
            if (button.Tag is not string tag || !_pages.ContainsKey(tag))
            {
                continue;
            }

            var isSelected = string.Equals(tag, pageName, StringComparison.Ordinal);
            button.Background = isSelected ? ActiveNavigationBrush : InactiveNavigationBrush;
            button.Foreground = isSelected ? ActiveNavigationForeground : InactiveNavigationForeground;
            button.FontWeight = isSelected ? FontWeights.SemiBold : FontWeights.Normal;
        }
    }

    private async void ChooseRepository_Click(object sender, RoutedEventArgs e)
    {
        await RunViewModelActionAsync(viewModel => viewModel.ChooseRepositoryAsync());
    }

    private async void StartRuntime_Click(object sender, RoutedEventArgs e)
    {
        await RunViewModelActionAsync(viewModel => viewModel.StartRuntimeAsync());
    }

    private async void StopRuntime_Click(object sender, RoutedEventArgs e)
    {
        await RunViewModelActionAsync(viewModel => viewModel.StopRuntimeAsync());
    }

    private async void RestartRuntime_Click(object sender, RoutedEventArgs e)
    {
        await RunViewModelActionAsync(viewModel => viewModel.RestartRuntimeAsync());
    }

    private async Task RunViewModelActionAsync(Func<MainWindowViewModel, Task> action)
    {
        if (DataContext is not MainWindowViewModel viewModel)
        {
            return;
        }

        try
        {
            await action(viewModel);
        }
        catch (Exception exception)
        {
            MessageBox.Show(
                this,
                exception.Message,
                "J.A.R.V.I.S Control Hub",
                MessageBoxButton.OK,
                MessageBoxImage.Warning);
        }
    }

    private static IEnumerable<T> FindVisualChildren<T>(DependencyObject parent) where T : DependencyObject
    {
        var childCount = VisualTreeHelper.GetChildrenCount(parent);
        for (var index = 0; index < childCount; index++)
        {
            var child = VisualTreeHelper.GetChild(parent, index);
            if (child is T match)
            {
                yield return match;
            }

            foreach (var descendant in FindVisualChildren<T>(child))
            {
                yield return descendant;
            }
        }
    }
}
