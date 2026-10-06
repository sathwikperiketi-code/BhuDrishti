import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "./utils";

export type StatusTone = "neutral" | "info" | "success" | "warning" | "danger";
export type WorkflowStatus = "pending" | "running" | "completed" | "warning" | "failed" | "review";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: StatusTone;
  subtle?: boolean;
  icon?: ReactNode;
}

export function Badge({ tone = "neutral", subtle = true, icon, className, children, ...props }: BadgeProps) {
  return (
    <span className={cx("bd-badge", `bd-badge--${tone}`, !subtle && "bd-badge--solid", className)} {...props}>
      {icon}
      {children}
    </span>
  );
}

const STATUS_TONES: Record<WorkflowStatus, StatusTone> = {
  pending: "neutral",
  running: "info",
  completed: "success",
  warning: "warning",
  failed: "danger",
  review: "warning",
};

const STATUS_LABELS: Record<WorkflowStatus, string> = {
  pending: "Pending",
  running: "In progress",
  completed: "Completed",
  warning: "Warning",
  failed: "Failed",
  review: "Review required",
};

export interface StatusBadgeProps extends Omit<BadgeProps, "tone" | "icon"> {
  status: WorkflowStatus;
  label?: string;
  pulse?: boolean;
}

export function StatusBadge({ status, label, pulse = false, className, ...props }: StatusBadgeProps) {
  return (
    <Badge tone={STATUS_TONES[status]} className={cx("bd-status-badge", className)} {...props}>
      <span className={cx("bd-status-badge__dot", pulse && status === "running" && "bd-status-badge__dot--pulse")} aria-hidden="true" />
      {label ?? STATUS_LABELS[status]}
    </Badge>
  );
}
