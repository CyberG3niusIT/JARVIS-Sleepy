namespace Jarvis.ControlHub;

public sealed record MetricBreakdown(string Name, long Interactions, long Tokens, double AverageLatencyMs)
{
    public string Detail => $"{Interactions} Interaktionen · {Tokens} Tokens · Ø {AverageLatencyMs:0} ms";
}
