using Microsoft.UI.Xaml;
using Microsoft.UI.Xaml.Automation;
using Microsoft.UI.Xaml.Controls;
using Microsoft.UI.Xaml.Data;
using Microsoft.UI.Xaml.Markup;
using Microsoft.UI.Xaml.Media;
using Microsoft.UI.Xaml.Shapes;
using Path = Microsoft.UI.Xaml.Shapes.Path;

namespace Jarvis.ControlHub.WinUI.Icons;

/// <summary>
/// Lucide-Icon als native Vektorform (Path in 24x24-Raum, per Viewbox auf <see cref="Size"/> skaliert), damit die
/// Strichstärke wie beim SVG in der Referenz mitskaliert. Die Linienfarbe folgt <see cref="Control.Foreground"/>
/// (entspricht currentColor), im Navigationselement also den Zuständen Normal, Hover und Ausgewählt.
/// Die Formen stehen zentral in <see cref="LucideIcons"/>.
/// </summary>
public sealed class LucideIcon : ContentControl
{
    public static readonly DependencyProperty KindProperty = DependencyProperty.Register(
        nameof(Kind), typeof(string), typeof(LucideIcon), new PropertyMetadata(string.Empty, OnShapeChanged));

    public static readonly DependencyProperty SizeProperty = DependencyProperty.Register(
        nameof(Size), typeof(double), typeof(LucideIcon), new PropertyMetadata(16.0, OnShapeChanged));

    private readonly Path _path = new()
    {
        StrokeThickness = LucideIcons.StrokeWidth,
        StrokeStartLineCap = PenLineCap.Round,
        StrokeEndLineCap = PenLineCap.Round,
        StrokeLineJoin = PenLineJoin.Round,
    };

    private readonly Viewbox _viewbox;

    public LucideIcon()
    {
        IsTabStop = false;
        IsHitTestVisible = false;
        UseSystemFocusVisuals = false;
        HorizontalAlignment = HorizontalAlignment.Center;
        VerticalAlignment = VerticalAlignment.Center;
        AutomationProperties.SetAccessibilityView(this, Microsoft.UI.Xaml.Automation.Peers.AccessibilityView.Raw);

        _path.SetBinding(Shape.StrokeProperty, new Binding { Source = this, Path = new PropertyPath(nameof(Foreground)) });
        var canvas = new Canvas { Width = LucideIcons.ViewBox, Height = LucideIcons.ViewBox };
        canvas.Children.Add(_path);
        _viewbox = new Viewbox { Stretch = Stretch.Uniform, Child = canvas };
        Content = _viewbox;
        Apply();
    }

    /// <summary>Name in <see cref="LucideIcons"/>, gleich dem Lucide-Icon der Referenz (zum Beispiel "Cpu").</summary>
    public string Kind
    {
        get => (string)GetValue(KindProperty);
        set => SetValue(KindProperty, value);
    }

    /// <summary>Kantenlänge in DIP (Lovable: size-4 = 16, size-[18px] = 18, size-5 = 20).</summary>
    public double Size
    {
        get => (double)GetValue(SizeProperty);
        set => SetValue(SizeProperty, value);
    }

    public static LucideIcon Create(string kind, double size, Brush? foreground = null)
    {
        var icon = new LucideIcon { Kind = kind, Size = size };
        if (foreground is not null) icon.Foreground = foreground;
        return icon;
    }

    private static void OnShapeChanged(DependencyObject d, DependencyPropertyChangedEventArgs e) => ((LucideIcon)d).Apply();

    private void Apply()
    {
        Width = Size;
        Height = Size;
        _viewbox.Width = Size;
        _viewbox.Height = Size;
        _path.Data = LucideIcons.TryGet(Kind, out var data)
            ? (Geometry)XamlBindingHelper.ConvertValue(typeof(Geometry), data)
            : null;
    }
}
