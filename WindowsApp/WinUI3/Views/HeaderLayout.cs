namespace Jarvis.ControlHub.WinUI.Views;

internal enum TabDensity
{
    Wide,
    Compact,
}

internal readonly record struct HeaderFit(TabDensity Tabs, bool SystemLabels);

/// <summary>
/// Passregel der Titelleiste. Die Stufen stammen aus Lovable styles.css (.jx-tabs, .jx-tab, @media width &lt; 90rem);
/// entschieden wird nach tatsächlich verfügbarer Breite statt nach Fensterbreite, weil die nativen Caption-Buttons
/// breiter sind als die Fenstersteuerung der Referenz. Reihenfolge: erst Statuslabels ausblenden, dann Tabs verdichten.
/// </summary>
internal static class HeaderLayout
{
    public const double TabGap = 2.4;
    public const double WideTabMinWidth = 86.4;
    public const double WideTabPadding = 11.2;
    public const double CompactTabMinWidth = 70.4;
    public const double CompactTabPadding = 7.2;

    // Sicherheitsabstand gegen Rundung und Messunterschiede, damit die NavigationView nicht knapp ins Overflow kippt.
    public const double FitReserve = 16;

    public static double MinWidth(TabDensity density) => density == TabDensity.Wide ? WideTabMinWidth : CompactTabMinWidth;

    public static double Padding(TabDensity density) => density == TabDensity.Wide ? WideTabPadding : CompactTabPadding;

    public static double TabsWidth(IReadOnlyList<double> contentWidths, TabDensity density) =>
        contentWidths.Sum(width => Math.Max(MinWidth(density), width + 2 * Padding(density))) + TabGap * contentWidths.Count;

    public static HeaderFit Choose(double available, IReadOnlyList<double> tabContentWidths, double statusWithLabels, double statusWithoutLabels)
    {
        var wide = TabsWidth(tabContentWidths, TabDensity.Wide);
        if (wide + statusWithLabels + FitReserve <= available) return new HeaderFit(TabDensity.Wide, true);
        if (wide + statusWithoutLabels + FitReserve <= available) return new HeaderFit(TabDensity.Wide, false);
        return new HeaderFit(TabDensity.Compact, false);
    }
}
