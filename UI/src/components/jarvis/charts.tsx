import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { ChartPoint } from "@/lib/jarvis/types";

export function PerformanceChart({
  data,
  secondary = false,
  unit = "%",
}: {
  data: ChartPoint[];
  secondary?: boolean;
  unit?: string;
}) {
  if (data.length === 0)
    return (
      <div className="flex h-36 w-full items-center justify-center text-[11px] text-muted-foreground">
        Keine Live-Daten
      </div>
    );
  return (
    <div className="h-36 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={data} margin={{ top: 12, right: 8, left: -26, bottom: 0 }}>
          <defs>
            <linearGradient id="lineFill" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="var(--primary)" stopOpacity={0.18} />
              <stop offset="100%" stopColor="var(--primary)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <CartesianGrid stroke="var(--border)" strokeDasharray="2 4" vertical={false} />
          <XAxis
            dataKey="time"
            tick={{ fill: "var(--muted-foreground)", fontSize: 9 }}
            interval={5}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            domain={[0, unit === "%" ? 100 : "auto"]}
            tickFormatter={(value: number) => `${value}${unit}`}
            tick={{ fill: "var(--muted-foreground)", fontSize: 9 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip
            contentStyle={{
              background: "var(--popover)",
              border: "1px solid var(--border)",
              borderRadius: 4,
              fontSize: 11,
            }}
            formatter={(value) => [`${value}${unit}`, "Wert"]}
          />
          {secondary && (
            <Area
              type="monotone"
              dataKey="secondary"
              stroke="var(--chart-2)"
              fill="none"
              strokeWidth={1}
            />
          )}
          <Area
            type="monotone"
            dataKey="primary"
            stroke="var(--primary)"
            fill="url(#lineFill)"
            strokeWidth={1.5}
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
