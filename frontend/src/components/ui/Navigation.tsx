import { Fragment, cloneElement, isValidElement, useEffect, useId, useRef, useState } from "react";
import type { FormEvent, HTMLAttributes, KeyboardEvent, ReactNode } from "react";
import { ChevronDown, ChevronRight, Search } from "lucide-react";
import { cx } from "./utils";

export interface TabItem {
  id: string;
  label: string;
  icon?: ReactNode;
  count?: number;
  disabled?: boolean;
  /** ID of the tabpanel controlled by this tab. Its aria-labelledby should reference tabId or `${panelId}-tab`. */
  panelId?: string;
  tabId?: string;
}

export interface TabsProps extends Omit<HTMLAttributes<HTMLDivElement>, "onChange"> {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
  label?: string;
  variant?: "line" | "segmented";
}

export function Tabs({ items, value, onChange, label = "Sections", variant = "line", className, ...props }: TabsProps) {
  function onTabKeyDown(event: KeyboardEvent<HTMLButtonElement>, currentIndex: number) {
    const enabled = items.map((item, index) => ({ item, index })).filter(({ item }) => !item.disabled);
    if (!enabled.length) return;
    const position = enabled.findIndex(({ index }) => index === currentIndex);
    let next = position;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") next = (position + 1) % enabled.length;
    else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = (position - 1 + enabled.length) % enabled.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = enabled.length - 1;
    else return;
    event.preventDefault();
    const target = enabled[next];
    onChange(target.item.id);
    event.currentTarget.parentElement?.querySelectorAll<HTMLButtonElement>("[role='tab']")[target.index]?.focus();
  }

  return (
    <div className={cx("bd-tabs", `bd-tabs--${variant}`, className)} role="tablist" aria-label={label} {...props}>
      {items.map((item, index) => (
        <button key={item.id} id={item.tabId ?? (item.panelId ? `${item.panelId}-tab` : undefined)} type="button" role="tab" className="bd-tabs__tab" aria-selected={value === item.id} aria-controls={item.panelId} tabIndex={value === item.id ? 0 : -1} disabled={item.disabled} onClick={() => onChange(item.id)} onKeyDown={(event) => onTabKeyDown(event, index)}>
          {item.icon && <span aria-hidden="true">{item.icon}</span>}
          {item.label}
          {item.count !== undefined && <span className="bd-tabs__count">{item.count}</span>}
        </button>
      ))}
    </div>
  );
}

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  side?: "top" | "bottom";
  className?: string;
}

export function Tooltip({ content, children, side = "top", className }: TooltipProps) {
  const id = useId();
  const canDescribeChild = isValidElement<HTMLAttributes<HTMLElement>>(children) && children.type !== Fragment;
  const trigger = canDescribeChild
    ? cloneElement(children, {
        "aria-describedby": [children.props["aria-describedby"], id].filter(Boolean).join(" "),
        tabIndex: children.props.tabIndex ?? 0,
      })
    : children;
  return <span className={cx("bd-tooltip", `bd-tooltip--${side}`, className)} tabIndex={canDescribeChild ? undefined : 0} aria-describedby={canDescribeChild ? undefined : id}>{trigger}<span id={id} className="bd-tooltip__content" role="tooltip">{content}</span></span>;
}

export interface DropdownItem {
  id: string;
  label: string;
  icon?: ReactNode;
  onSelect: () => void;
  disabled?: boolean;
  danger?: boolean;
}

export interface DropdownProps {
  label: string;
  items: DropdownItem[];
  icon?: ReactNode;
  align?: "start" | "end";
  className?: string;
}

export function Dropdown({ label, items, icon, align = "end", className }: DropdownProps) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const id = useId();

  useEffect(() => {
    if (!open) return;
    const first = rootRef.current?.querySelector<HTMLButtonElement>("[role='menuitem']:not(:disabled)");
    first?.focus();
    function onPointerDown(event: PointerEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKeyDown(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") { setOpen(false); triggerRef.current?.focus(); }
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => { document.removeEventListener("pointerdown", onPointerDown); document.removeEventListener("keydown", onKeyDown); };
  }, [open]);

  function onMenuKeyDown(event: KeyboardEvent<HTMLDivElement>) {
    if (!["ArrowDown", "ArrowUp", "Home", "End"].includes(event.key)) return;
    const buttons = Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>("[role='menuitem']:not(:disabled)"));
    if (!buttons.length) return;
    event.preventDefault();
    const current = buttons.indexOf(document.activeElement as HTMLButtonElement);
    const next = event.key === "Home" ? 0 : event.key === "End" ? buttons.length - 1 : event.key === "ArrowDown" ? (current + 1) % buttons.length : (current - 1 + buttons.length) % buttons.length;
    buttons[next]?.focus();
  }

  return (
    <div ref={rootRef} className={cx("bd-dropdown", className)}>
      <button ref={triggerRef} type="button" className="bd-dropdown__trigger" aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} onClick={() => setOpen((current) => !current)}>
        {icon && <span aria-hidden="true">{icon}</span>}{label}<ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && <div id={id} className={cx("bd-dropdown__menu", `bd-dropdown__menu--${align}`)} role="menu" aria-label={label} onKeyDown={onMenuKeyDown}>
        {items.map((item) => <button key={item.id} type="button" role="menuitem" className={cx("bd-dropdown__item", item.danger && "bd-dropdown__item--danger")} disabled={item.disabled} onClick={() => { item.onSelect(); setOpen(false); triggerRef.current?.focus(); }}>{item.icon && <span aria-hidden="true">{item.icon}</span>}{item.label}</button>)}
      </div>}
    </div>
  );
}

export interface BreadcrumbItem {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface BreadcrumbProps extends HTMLAttributes<HTMLElement> {
  items: BreadcrumbItem[];
}

export function Breadcrumb({ items, className, ...props }: BreadcrumbProps) {
  return (
    <nav aria-label="Breadcrumb" className={cx("bd-breadcrumb", className)} {...props}>
      <ol>{items.map((item, index) => <li key={`${item.label}-${index}`}>
        {index > 0 && <ChevronRight size={13} aria-hidden="true" />}
        {index === items.length - 1 ? <span aria-current="page">{item.label}</span> : item.href ? <a href={item.href}>{item.label}</a> : item.onClick ? <button type="button" onClick={item.onClick}>{item.label}</button> : <span>{item.label}</span>}
      </li>)}</ol>
    </nav>
  );
}

export interface CommandBarProps extends Omit<HTMLAttributes<HTMLFormElement>, "onSubmit" | "onChange"> {
  value: string;
  onChange: (value: string) => void;
  onSubmit?: (value: string) => void;
  placeholder?: string;
  shortcut?: string;
  actions?: ReactNode;
  label?: string;
}

export function CommandBar({ value, onChange, onSubmit, placeholder = "Search records, documents, or survey numbers", shortcut, actions, label = "Global search", className, ...props }: CommandBarProps) {
  function submit(event: FormEvent<HTMLFormElement>) { event.preventDefault(); onSubmit?.(value.trim()); }
  return (
    <form role="search" className={cx("bd-command-bar", className)} onSubmit={submit} {...props}>
      <Search size={17} aria-hidden="true" />
      <input type="search" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} aria-label={label} />
      {shortcut && <kbd aria-hidden="true">{shortcut}</kbd>}
      {actions}
    </form>
  );
}

export interface PageHeaderProps extends HTMLAttributes<HTMLElement> {
  title: string;
  eyebrow?: string;
  description?: string;
  breadcrumbs?: BreadcrumbItem[];
  actions?: ReactNode;
  meta?: ReactNode;
}

export function PageHeader({ title, eyebrow, description, breadcrumbs, actions, meta, className, ...props }: PageHeaderProps) {
  return (
    <header className={cx("bd-page-header", className)} {...props}>
      {breadcrumbs && <Breadcrumb items={breadcrumbs} />}
      <div className="bd-page-header__main">
        <div>
          {eyebrow && <span className="bd-page-header__eyebrow">{eyebrow}</span>}
          <h1>{title}</h1>
          {description && <p>{description}</p>}
        </div>
        {actions && <div className="bd-page-header__actions">{actions}</div>}
      </div>
      {meta && <div className="bd-page-header__meta">{meta}</div>}
    </header>
  );
}
