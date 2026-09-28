using Jarvis.ControlHub.WinUI.Icons;
using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;

namespace Jarvis.ControlHub.WinUI.Views;

/// <summary>Shell-Rahmen: Runtime/Privacy/Cloud in der Titelleiste, Status-Chips und Viewport-Höhe (Lovable desktop-shell).</summary>
public sealed partial class ShellPage
{
    // .jx-sys Beschriftungen entfallen unter 90rem, die Chips bleiben (styles.css, @media width < 90rem).
    private const double SystemLabelMinWidth = 1440;

    // Innenabstand des Canvas: oben und unten je 0.85rem (.jx-canvas).
    private const double CanvasVerticalPadding = 27.2;

    private StatusChipView? _runtimeChip;
    private StackPanel? _runtimeGroup;
    private readonly List<TextBlock> _systemLabels = [];
    private Grid? _homeGrid;

    private void BuildSystemGroups()
    {
        _runtimeChip = StatusChipView.Create("UNAVAILABLE");
        _runtimeGroup = SystemGroup("Runtime", "Link2Off", _runtimeChip, "Runtime Supervisor");
        SystemGroups.Children.Add(_runtimeGroup);
        SystemGroups.Children.Add(SystemGroup("Privacy", "ShieldAlert", StatusChipView.Create("UNAVAILABLE"), "Keine autoritative Privacy-Quelle"));
        SystemGroups.Children.Add(SystemGroup("Cloud", "CloudOff", StatusChipView.Create("UNAVAILABLE"), "Keine autoritative Cloud-Quelle"));
    }

    private StackPanel SystemGroup(string label, string icon, StatusChipView chip, string tooltip)
    {
        var group = new StackPanel { Orientation = Orientation.Horizontal, Spacing = 6.4, VerticalAlignment = VerticalAlignment.Center };
        group.Children.Add(Lucide(icon, 14, "JarvisMutedTextBrush"));
        var text = new TextBlock { Text = label, FontSize = 11.52, Foreground = Brush("JarvisMutedTextBrush"), VerticalAlignment = VerticalAlignment.Center };
        _systemLabels.Add(text);
        group.Children.Add(text);
        group.Children.Add(chip.Root);
        ToolTipService.SetToolTip(group, tooltip);
        AutomationProperties.SetName(group, label);
        return group;
    }

    private void UpdateSystemLabels(double width)
    {
        var visibility = width >= SystemLabelMinWidth ? Visibility.Visible : Visibility.Collapsed;
        foreach (var label in _systemLabels) label.Visibility = visibility;
    }

    /// <summary>Home füllt die reale Client Area (kein fester Höhenwert) und scrollt erst, wenn der Inhalt höher ist.</summary>
    private void ApplyHomeMinHeight()
    {
        if (_homeGrid is null) return;
        _homeGrid.MinHeight = Math.Max(0, PageScroll.ViewportHeight - CanvasVerticalPadding);
    }

    /// <summary>
    /// .jx-tab[data-active] svg: Das Icon des aktiven Tabs ist Signalblau, das Label bleibt Vordergrund. Hover und
    /// Normalzustand folgen dem Label (currentColor). Beim System-Tab zeigt das Icon das gewählte Untermodul, sonst LayoutGrid.
    /// </summary>
    private void UpdateNavIcons()
    {
        var selected = Navigation.SelectedItem as NavigationViewItem;
        foreach (var entry in Navigation.MenuItems)
        {
            if (entry is not NavigationViewItem { Content: StackPanel { Children: [LucideIcon icon, ..] } } item) continue;
            var active = ReferenceEquals(item, selected) || item.MenuItems.Any(child => ReferenceEquals(child, selected));
            if (ReferenceEquals(item, SystemNavItem))
            {
                icon.Kind = selected is { Content: StackPanel { Children: [LucideIcon childIcon, ..] } } && active ? childIcon.Kind : "LayoutGrid";
            }

            if (active) icon.Foreground = Brush("JarvisSignalBrush");
            else icon.ClearValue(Control.ForegroundProperty);
        }
    }

    /// <summary>
    /// Die Referenz setzt den Chevron des System-Tabs inline hinter das Label. Der eingebaute Chevron der NavigationView
    /// sitzt außerhalb des Tabs und wird deshalb aus dem Template herausgenommen (Opacity und Breite 0, Logik bleibt).
    /// </summary>
    private void HideBuiltInChevron(DependencyObject root)
    {
        var count = VisualTreeHelper.GetChildrenCount(root);
        for (var i = 0; i < count; i++)
        {
            var child = VisualTreeHelper.GetChild(root, i);
            if (child is FrameworkElement { Name: "ExpandCollapseChevron" } chevron)
            {
                chevron.Opacity = 0;
                chevron.Width = 0;
                chevron.MinWidth = 0;
                chevron.Margin = new Thickness(0);
                return;
            }

            HideBuiltInChevron(child);
        }
    }

    /// <summary>Lucide-Icon aus der zentralen Registry, Linienfarbe aus dem Token (currentColor der Referenz).</summary>
    private static LucideIcon Lucide(string kind, double size, string brushKey) => LucideIcon.Create(kind, size, Brush(brushKey));

    /// <summary>.jx-tag: neutrale Marke ohne Zustandssemantik (zum Beispiel NO LIVE DATA, KEINE QUELLE).</summary>
    private static Border JxTag(string text) => new()
    {
        Background = Brush("JarvisBackgroundBrush"),
        BorderBrush = Brush("JarvisLineBrush"),
        BorderThickness = new Thickness(1),
        CornerRadius = new CornerRadius(3),
        Padding = new Thickness(7.2, 2.4, 7.2, 2.4),
        VerticalAlignment = VerticalAlignment.Center,
        Child = new TextBlock
        {
            Text = text,
            FontSize = 11,
            FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"],
            Foreground = Brush("JarvisSecondaryTextBrush"),
        },
    };
}

/// <summary>
/// .jx-status: Cascadia Mono 11 px, Rand je Zustand (durchgezogen, gestrichelt für OFFLINE und NOT_IMPLEMENTED,
/// gepunktet für UNAVAILABLE), bei ERROR ein 2-px-Balken links.
/// </summary>
internal sealed class StatusChipView
{
    private enum Pattern { Solid, Dashed, Dotted }

    private readonly Rectangle _frame = new() { RadiusX = 2, RadiusY = 2, StrokeThickness = 1, StrokeDashCap = PenLineCap.Round };
    private readonly Rectangle _bar = new() { Width = 2, HorizontalAlignment = HorizontalAlignment.Left, Visibility = Visibility.Collapsed };
    private readonly TextBlock _text = new()
    {
        FontSize = 11,
        LineHeight = 16.5,
        Margin = new Thickness(7, 3, 7, 3),
        VerticalAlignment = VerticalAlignment.Center,
        TextWrapping = TextWrapping.NoWrap,
    };

    private StatusChipView()
    {
        Root = new Grid { HorizontalAlignment = HorizontalAlignment.Left, VerticalAlignment = VerticalAlignment.Center };
        _text.FontFamily = (Microsoft.UI.Xaml.Media.FontFamily)Application.Current.Resources["JarvisMonoFontFamily"];
        Root.Children.Add(_frame);
        Root.Children.Add(_bar);
        Root.Children.Add(_text);
    }

    public Grid Root { get; }

    public static StatusChipView Create(string state)
    {
        var chip = new StatusChipView();
        chip.Set(state);
        return chip;
    }

    public void Set(string state)
    {
        var (foreground, border, background, pattern, bar) = Describe(state);
        _text.Text = state;
        _text.Foreground = foreground;
        _frame.Stroke = border;
        _frame.Fill = background;
        _frame.StrokeDashArray = pattern switch
        {
            Pattern.Dashed => [3, 2],
            Pattern.Dotted => [1, 2],
            _ => [],
        };
        _bar.Fill = foreground;
        _bar.Visibility = bar ? Visibility.Visible : Visibility.Collapsed;
        AutomationProperties.SetName(Root, "Status: " + state);
    }

    private static Brush Res(string key) => (Brush)Application.Current.Resources[key];

    private static (Brush Foreground, Brush Border, Brush Background, Pattern Pattern, bool Bar) Describe(string state) => state switch
    {
        "READY" => (Res("JarvisReadyBrush"), Res("JarvisChipBorderReadyBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Solid, false),
        "STARTING" => (Res("JarvisInfoBrush"), Res("JarvisChipBorderStartingBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Solid, false),
        "DEGRADED" => (Res("JarvisDegradedBrush"), Res("JarvisChipBorderDegradedBrush"), Res("JarvisChipBackgroundDegradedBrush"), Pattern.Solid, false),
        "ERROR" => (Res("JarvisErrorBrush"), Res("JarvisErrorBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Solid, true),
        "STOPPED" => (Res("JarvisStoppedBrush"), Res("JarvisChipBorderStoppedBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Solid, false),
        "OFFLINE" => (Res("JarvisErrorBrush"), Res("JarvisChipBorderOfflineBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Dashed, false),
        "NOT_IMPLEMENTED" => (Res("JarvisUnavailableBrush"), Res("JarvisChipBorderUnavailableBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Dashed, false),
        _ => (Res("JarvisUnavailableBrush"), Res("JarvisChipBorderUnavailableBrush"), Res("JarvisSurfaceElevatedBrush"), Pattern.Dotted, false),
    };
}
