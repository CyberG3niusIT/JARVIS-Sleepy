import wordmarkAsset from "@/assets/jarvis-wordmark.png.asset.json";
import symbolAsset from "@/assets/jarvis-symbol.png.asset.json";
import { cn } from "@/lib/utils";

/**
 * Official J.A.R.V.I.S brand assets, taken from the approved identity artwork.
 * Never typeset the wordmark with a UI font, never drop the node periods.
 */

export function JarvisWordmark({
  className,
  height = 14,
}: {
  className?: string;
  height?: number;
}) {
  return (
    <img
      src={wordmarkAsset.url}
      alt="J.A.R.V.I.S"
      style={{ height }}
      className={cn("w-auto select-none", className)}
      draggable={false}
    />
  );
}

export function JarvisSymbol({
  className,
  size = 20,
}: {
  className?: string;
  size?: number;
}) {
  return (
    <img
      src={symbolAsset.url}
      alt=""
      aria-hidden
      style={{ height: size }}
      className={cn("w-auto select-none", className)}
      draggable={false}
    />
  );
}

/** Compact header identity: symbol + wordmark + fixed subtitle. */
export function JarvisLockup({
  subtitle = true,
  className,
}: {
  subtitle?: boolean;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center", className)}>
      <JarvisWordmark height={13} />
      {subtitle ? (
        <span className="mt-0.5 text-[10px] leading-none tracking-[0.18em] text-muted-foreground">
          Local AI Assistant
        </span>
      ) : null}
    </div>
  );
}
