import type { HTMLAttributes, ReactNode } from "react";
import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import { Button } from "./Controls";
import { cx } from "./utils";

export interface CardProps extends HTMLAttributes<HTMLElement> {
  as?: "article" | "section" | "div";
  elevated?: boolean;
  interactive?: boolean;
}

export function Card({ as: Element = "div", elevated = false, interactive = false, className, children, ...props }: CardProps) {
  return (
    <Element className={cx("bd-card", elevated && "bd-card--elevated", interactive && "bd-card--interactive", className)} {...props}>
      {children}
    </Element>
  );
}

export interface MetricCardProps extends HTMLAttributes<HTMLElement> {
  label: string;
  value: string | number;
  detail?: string;
  change?: string;
  trend?: "up" | "down" | "flat";
  tone?: "neutral" | "green" | "blue" | "amber";
  icon?: ReactNode;
  sparkline?: number[];
}

function sparklinePoints(values: number[]): string {
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  return values.map((value, index) => `${(index / (values.length - 1)) * 100},${30 - ((value - min) / span) * 24}`).join(" ");
}

export function MetricCard({ label, value, detail, change, trend = "flat", tone = "neutral", icon, sparkline, className, ...props }: MetricCardProps) {
  const TrendIcon = trend === "up" ? ArrowUpRight : trend === "down" ? ArrowDownRight : Minus;
  return (
    <Card as="article" className={cx("bd-metric", `bd-metric--${tone}`, className)} {...props}>
      <div className="bd-metric__top">
        <span className="bd-metric__label">{label}</span>
        {icon && <span className="bd-metric__icon" aria-hidden="true">{icon}</span>}
      </div>
      <div className="bd-metric__middle">
        <strong className="bd-metric__value">{value}</strong>
        {sparkline && sparkline.length > 1 && (
          <svg className="bd-metric__sparkline" viewBox="0 0 100 34" preserveAspectRatio="none" aria-hidden="true">
            <polyline points={sparklinePoints(sparkline)} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" vectorEffect="non-scaling-stroke" />
          </svg>
        )}
      </div>
      {(detail || change) && (
        <div className="bd-metric__foot">
          {change && <span className={cx("bd-metric__change", `bd-metric__change--${trend}`)}><TrendIcon size={13} aria-hidden="true" />{change}</span>}
          {detail && <span>{detail}</span>}
        </div>
      )}
    </Card>
  );
}

export interface DataColumn<T> {
  key: string;
  header: ReactNode;
  render: (row: T) => ReactNode;
  align?: "left" | "center" | "right";
  width?: string;
}

export interface DataTableProps<T> {
  columns: DataColumn<T>[];
  rows: T[];
  rowKey: (row: T) => string | number;
  caption?: string;
  emptyMessage?: string;
  onRowClick?: (row: T) => void;
  rowActionLabel?: (row: T) => string;
  className?: string;
}

export function DataTable<T>({ columns, rows, rowKey, caption, emptyMessage = "No records to display.", onRowClick, rowActionLabel, className }: DataTableProps<T>) {
  return (
    <div className={cx("bd-table-wrap", className)}>
      <table className="bd-table">
        {caption && <caption className="bd-sr-only">{caption}</caption>}
        <thead>
          <tr>{columns.map((column) => <th key={column.key} scope="col" className={cx(column.align && `bd-table__${column.align}`)} style={column.width ? { width: column.width } : undefined}>{column.header}</th>)}{onRowClick && <th scope="col">Action</th>}</tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr><td colSpan={columns.length + (onRowClick ? 1 : 0)} className="bd-table__empty">{emptyMessage}</td></tr>
          ) : rows.map((row, index) => (
            <tr
              key={rowKey(row)}
              className={onRowClick ? "bd-table__interactive" : undefined}
              onClick={onRowClick ? (event) => { if (!(event.target as HTMLElement).closest("a, button, input, select, textarea")) onRowClick(row); } : undefined}
            >
              {columns.map((column) => <td key={column.key} className={cx(column.align && `bd-table__${column.align}`)}>{column.render(row)}</td>)}
              {onRowClick && <td><Button variant="ghost" size="sm" aria-label={rowActionLabel?.(row) ?? `Open row ${index + 1}`} onClick={() => onRowClick(row)}>Open</Button></td>}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
