import React, { useState } from "react";

export interface Column<T> {
  key: string;
  header: string;
  render?: (item: T) => React.ReactNode;
  width?: string;
  className?: string;
}

interface DataTableProps<T> {
  columns: Column<T>[];
  data: T[];
  keyExtractor: (item: T) => string;
  searchableKey?: keyof T;
  searchPlaceholder?: string;
  emptyMessage?: string;
  onRowClick?: (item: T) => void;
}

export function DataTable<T>({
  columns,
  data,
  keyExtractor,
  searchableKey,
  searchPlaceholder = "Filter entries...",
  emptyMessage = "No records found.",
  onRowClick,
}: DataTableProps<T>) {
  const [searchTerm, setSearchTerm] = useState("");

  const filteredData = searchableKey
    ? data.filter((item) => {
        const val = item[searchableKey];
        if (typeof val === "string") {
          return val.toLowerCase().includes(searchTerm.toLowerCase());
        }
        return true;
      })
    : data;

  return (
    <div className="space-y-3 font-mono text-xs">
      {searchableKey && (
        <div className="flex items-center justify-between gap-4">
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="px-3 py-1.5 rounded-lg bg-slate-900/90 border border-white/10 text-slate-200 placeholder-slate-500 outline-none focus:border-cyan-500 w-64 text-xs transition-colors"
          />
          <span className="text-slate-500 text-[11px]">
            Showing {filteredData.length} of {data.length}
          </span>
        </div>
      )}

      <div className="rounded-xl border border-white/10 bg-slate-950/60 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-white/10 bg-slate-900/80 text-slate-400 font-semibold uppercase text-[11px]">
                {columns.map((col) => (
                  <th
                    key={col.key}
                    style={{ width: col.width }}
                    className={`px-4 py-2.5 ${col.className || ""}`}
                  >
                    {col.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-white/5">
              {filteredData.length === 0 ? (
                <tr>
                  <td
                    colSpan={columns.length}
                    className="px-4 py-8 text-center text-slate-500 italic"
                  >
                    {emptyMessage}
                  </td>
                </tr>
              ) : (
                filteredData.map((item) => (
                  <tr
                    key={keyExtractor(item)}
                    onClick={() => onRowClick && onRowClick(item)}
                    className={`transition-colors hover:bg-white/5 ${
                      onRowClick ? "cursor-pointer" : ""
                    }`}
                  >
                    {columns.map((col) => (
                      <td
                        key={col.key}
                        className={`px-4 py-3 text-slate-300 ${col.className || ""}`}
                      >
                        {col.render
                          ? col.render(item)
                          : String((item as Record<string, unknown>)[col.key] ?? "-")}
                      </td>
                    ))}
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
