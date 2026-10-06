import { useEffect, useId, useRef } from "react";
import type { ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion, useReducedMotion } from "framer-motion";
import { X } from "lucide-react";
import { IconButton } from "./Controls";
import { cx } from "./utils";

interface OverlayProps {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg";
  side?: "left" | "right";
  className?: string;
}

function Overlay({ open, onClose, title, description, children, footer, size = "md", side, className }: OverlayProps) {
  const dialogRef = useRef<HTMLElement>(null);
  const triggerRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  const titleId = useId();
  const descriptionId = useId();
  const reducedMotion = useReducedMotion();

  useEffect(() => { closeRef.current = onClose; }, [onClose]);

  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement as HTMLElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusFrame = requestAnimationFrame(() => dialogRef.current?.querySelector<HTMLElement>("button, [href], input, select, textarea, [tabindex]:not([tabindex='-1'])")?.focus());
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); closeRef.current(); return; }
      if (event.key !== "Tab") return;
      const focusable = Array.from(dialogRef.current?.querySelectorAll<HTMLElement>("button:not(:disabled), [href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex='-1'])") ?? []);
      if (focusable.length === 0) { event.preventDefault(); dialogRef.current?.focus(); return; }
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
      triggerRef.current?.focus();
    };
  }, [open]);

  if (typeof document === "undefined") return null;
  const isDrawer = Boolean(side);
  const duration = reducedMotion ? 0 : 0.24;
  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          className={cx("bd-overlay", isDrawer && "bd-overlay--drawer")}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: reducedMotion ? 0 : 0.18 }}
          onMouseDown={(event) => { if (event.target === event.currentTarget) onClose(); }}
        >
          <motion.section
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={description ? descriptionId : undefined}
            tabIndex={-1}
            className={cx("bd-dialog", isDrawer ? `bd-dialog--drawer-${side}` : `bd-dialog--${size}`, className)}
            initial={reducedMotion ? { opacity: 1 } : { opacity: 0, y: isDrawer ? 0 : 12, x: side === "right" ? 24 : side === "left" ? -24 : 0 }}
            animate={{ opacity: 1, x: 0, y: 0 }}
            exit={reducedMotion ? { opacity: 0 } : { opacity: 0, y: isDrawer ? 0 : 8, x: side === "right" ? 24 : side === "left" ? -24 : 0 }}
            transition={{ duration, ease: [0.22, 1, 0.36, 1] }}
          >
            <header className="bd-dialog__header">
              <div><h2 id={titleId}>{title}</h2>{description && <p id={descriptionId}>{description}</p>}</div>
              <IconButton icon={<X size={18} />} label={`Close ${isDrawer ? "panel" : "dialog"}`} variant="ghost" onClick={onClose} />
            </header>
            <div className="bd-dialog__body">{children}</div>
            {footer && <footer className="bd-dialog__footer">{footer}</footer>}
          </motion.section>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}

export interface ModalProps extends Omit<OverlayProps, "side"> {}
export function Modal(props: ModalProps) { return <Overlay {...props} />; }

export interface DrawerProps extends Omit<OverlayProps, "size"> {
  side?: "left" | "right";
}
export function Drawer({ side = "right", ...props }: DrawerProps) { return <Overlay side={side} {...props} />; }
