import type { HTMLAttributes, ReactNode } from "react";
import { AlertCircle, Inbox, RotateCcw, X } from "lucide-react";
import { Button, IconButton } from "./Controls";
import type { StatusTone, WorkflowStatus } from "./Status";
import { clampPercent, cx } from "./utils";

export interface ProgressBarProps extends HTMLAttributes<HTMLDivElement> {
  value: number;
  label?: string;
  showValue?: boolean;
  tone?: "green" | "blue" | "amber" | "red";
  size?: "sm" | "md";
}

export function ProgressBar({ value, label, showValue = false, tone = "green", size = "md", className, ...props }: ProgressBarProps) {
  const percent = clampPercent(value);
  return (
    <div className={cx("bd-progress", className)} {...props}>
      {(label || showValue) && <div className="bd-progress__head">{label && <span>{label}</span>}{showValue && <strong>{Math.round(percent)}%</strong>}</div>}
      <div className={cx("bd-progress__track", `bd-progress__track--${size}`)} role="progressbar" aria-label={label ?? "Progress"} aria-valuenow={percent} aria-valuemin={0} aria-valuemax={100}>
        <span className={cx("bd-progress__fill", `bd-progress__fill--${tone}`)} style={{ transform: `scaleX(${percent / 100})` }} />
      </div>
    </div>
  );
}

export interface ConfidenceBarProps extends Omit<ProgressBarProps, "tone" | "showValue"> {
  value: number;
  threshold?: number;
}

export function ConfidenceBar({ value, threshold = 80, label = "Confidence", ...props }: ConfidenceBarProps) {
  const percent = clampPercent(value);
  return <ProgressBar value={percent} label={label} tone={percent >= threshold ? "green" : percent >= 60 ? "amber" : "red"} showValue {...props} />;
}

export interface TimelineStep {
  id: string;
  title: string;
  description?: string;
  meta?: ReactNode;
  icon?: ReactNode;
  status: WorkflowStatus;
}

export interface TimelineProps extends HTMLAttributes<HTMLOListElement> {
  steps: TimelineStep[];
  compact?: boolean;
}

export function Timeline({ steps, compact = false, className, ...props }: TimelineProps) {
  return (
    <ol className={cx("bd-timeline", compact && "bd-timeline--compact", className)} {...props}>
      {steps.map((step) => (
        <li key={step.id} className={cx("bd-timeline__step", `bd-timeline__step--${step.status}`)}>
          <span className="bd-timeline__marker" aria-hidden="true">{step.icon ?? <span />}</span>
          <div className="bd-timeline__content">
            <div className="bd-timeline__heading"><strong>{step.title}</strong>{step.meta && <span className="bd-timeline__meta">{step.meta}</span>}</div>
            {step.description && <p>{step.description}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}

export interface EmptyStateProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  compact?: boolean;
}

export function EmptyState({ title, description, icon = <Inbox size={22} />, action, compact = false, className, ...props }: EmptyStateProps) {
  return (
    <div className={cx("bd-state", compact && "bd-state--compact", className)} {...props}>
      <span className="bd-state__icon" aria-hidden="true">{icon}</span>
      <h3>{title}</h3>
      {description && <p>{description}</p>}
      {action && <div className="bd-state__action">{action}</div>}
    </div>
  );
}

export interface ErrorStateProps extends Omit<EmptyStateProps, "icon" | "action" | "title"> {
  title?: string;
  onRetry?: () => void;
  retryLabel?: string;
}

export function ErrorState({ title = "Something went wrong", description, onRetry, retryLabel = "Try again", className, ...props }: ErrorStateProps) {
  return (
    <EmptyState
      title={title}
      description={description}
      icon={<AlertCircle size={22} />}
      action={onRetry ? <Button variant="secondary" size="sm" leadingIcon={<RotateCcw size={14} />} onClick={onRetry}>{retryLabel}</Button> : undefined}
      className={cx("bd-state--error", className)}
      role="alert"
      {...props}
    />
  );
}

export interface SkeletonProps extends HTMLAttributes<HTMLSpanElement> {
  width?: string | number;
  height?: string | number;
  lines?: number;
  rounded?: boolean;
}

export function Skeleton({ width, height, lines = 1, rounded = false, className, style, ...props }: SkeletonProps) {
  const count = Math.max(1, Math.min(12, Math.floor(lines)));
  return (
    <span className={cx("bd-skeleton-group", className)} aria-hidden="true" {...props}>
      {Array.from({ length: count }, (_, index) => (
        <span
          key={index}
          className={cx("bd-skeleton", rounded && "bd-skeleton--rounded")}
          style={{ width: count > 1 && index === count - 1 ? "68%" : width, height, ...style }}
        />
      ))}
    </span>
  );
}

export interface ToastProps extends HTMLAttributes<HTMLDivElement> {
  title: string;
  description?: string;
  tone?: StatusTone;
  onDismiss?: () => void;
  action?: ReactNode;
}

export function Toast({ title, description, tone = "info", onDismiss, action, className, ...props }: ToastProps) {
  return (
    <div className={cx("bd-toast", `bd-toast--${tone}`, className)} role={tone === "danger" ? "alert" : "status"} {...props}>
      <span className="bd-toast__marker" aria-hidden="true" />
      <div className="bd-toast__body"><strong>{title}</strong>{description && <p>{description}</p>}{action}</div>
      {onDismiss && <IconButton icon={<X size={16} />} label="Dismiss notification" variant="ghost" size="sm" onClick={onDismiss} />}
    </div>
  );
}
