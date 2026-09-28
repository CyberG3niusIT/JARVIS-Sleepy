namespace Jarvis.ControlHub;

public sealed record MetricBucket(string Period, long Interactions, long Tokens, double AverageLatencyMs)
{
    public double RelativeActivity { get; init; }
    public string Detail { get; init; } = string.Empty;
}
