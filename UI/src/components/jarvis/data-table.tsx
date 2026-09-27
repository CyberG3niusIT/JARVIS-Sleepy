import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface Column<T> {
  key: string;
  label: string;
  className?: string;
  render: (row: T) => ReactNode;
}
export function DataTable<T extends { id: string }>({
  columns,
  rows,
  selectedId,
  onSelect,
  emptyText = "Keine Einträge",
}: {
  columns: Column<T>[];
  rows: T[];
  selectedId?: string | undefined;
  onSelect?: ((row: T) => void) | undefined;
  emptyText?: string | undefined;
}) {
  return (
    <div className="overflow-auto">
      <table className="w-full table-fixed text-left text-[11px]">
        <thead className="sticky top-0 z-10 bg-secondary">
          <tr>
            {columns.map((column) => (
              <th
                key={column.key}
                className={cn(
                  "h-8 border-b border-border px-2 font-medium text-muted-foreground",
                  column.className,
                )}
              >
                {column.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="h-32 text-center text-muted-foreground">
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr
                key={row.id}
                tabIndex={onSelect ? 0 : undefined}
                data-state={selectedId === row.id ? "selected" : undefined}
                aria-selected={selectedId === row.id ? true : undefined}
                onClick={() => onSelect?.(row)}
                onKeyDown={(event) => {
                  if (!onSelect || (event.key !== "Enter" && event.key !== " ")) return;
                  event.preventDefault();
                  onSelect(row);
                }}
                className={cn(
                  "border-b border-border/70 transition-colors",
                  onSelect &&
                    "cursor-pointer hover:bg-accent focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring",
                  selectedId === row.id && "bg-selection",
                )}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={cn("h-9 truncate px-2 text-foreground", column.className)}
                  >
                    {column.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
