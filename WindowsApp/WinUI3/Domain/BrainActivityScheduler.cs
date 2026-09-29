namespace Jarvis.ControlHub.WinUI.Domain;

/// <summary>
/// Reine Zulassungslogik für gleichzeitig sichtbare Brain-Impulse, ohne Kenntnis von Zeit oder Rendering.
/// Verhindert, dass ein Event-Burst beliebig viele parallele Animationen erzeugt: bei Überschreiten der
/// Obergrenze werden neue Schritte gebündelt (nur der zulässige Rest wird admittiert), nicht verworfen oder
/// verzögert nachgeholt.
/// </summary>
public static class BrainActivityScheduler
{
    /// <summary>Obergrenze gleichzeitig sichtbarer Aktivitäts-Impulse (Kanten- und Knoten-Flashes zusammen).</summary>
    public const int MaxConcurrentPulses = 8;

    /// <summary>
    /// Liefert, wie viele der angeforderten <paramref name="requested"/> neuen Impulse noch admittiert werden
    /// dürfen, gegeben die Anzahl <paramref name="currentlyActive"/> bereits laufender Impulse und die Obergrenze
    /// <paramref name="max"/>. Nie negativ, nie größer als <paramref name="requested"/>.
    /// </summary>
    public static int Admit(int currentlyActive, int requested, int max = MaxConcurrentPulses)
    {
        var free = max - currentlyActive;
        if (free <= 0) return 0;
        return Math.Min(free, requested);
    }
}
