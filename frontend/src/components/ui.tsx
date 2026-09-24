import {
  useEffect,
  useId,
  useRef,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type TextareaHTMLAttributes,
} from "react";
import { Link } from "react-router";
import { AlertTriangle, CheckCircle2, Info, Loader2, X, XCircle } from "lucide-react";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

type Variant = "primary" | "secondary" | "danger" | "ghost" | "soft";
type Size = "sm" | "md";

const variants: Record<Variant, string> = {
  primary: "bg-brand-600 text-white hover:bg-brand-700 shadow-sm",
  secondary: "bg-white text-slate-700 border border-slate-300 hover:bg-slate-50 shadow-sm",
  danger: "bg-red-600 text-white hover:bg-red-700 shadow-sm",
  ghost: "text-slate-600 hover:bg-slate-100",
  soft: "bg-brand-50 text-brand-700 hover:bg-brand-100",
};
const sizes: Record<Size, string> = {
  sm: "h-8 px-3 text-sm gap-1.5",
  md: "h-10 px-4 text-sm gap-2",
};

export function buttonClass(variant: Variant = "primary", size: Size = "md", extra?: string) {
  return cx(
    "inline-flex items-center justify-center rounded-lg font-medium transition-colors whitespace-nowrap",
    "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500",
    "disabled:opacity-50 disabled:pointer-events-none",
    variants[variant],
    sizes[size],
    extra,
  );
}

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: Variant;
  size?: Size;
  loading?: boolean;
  icon?: ReactNode;
};

export function Button({ variant, size, loading, icon, className, children, disabled, type = "button", ...rest }: ButtonProps) {
  return (
    <button type={type} className={buttonClass(variant, size, className)} disabled={disabled || loading} {...rest}>
      {loading ? <Loader2 className="size-4 animate-spin" /> : icon}
      {children}
    </button>
  );
}

type LinkButtonProps = { to: string; variant?: Variant; size?: Size; icon?: ReactNode; children: ReactNode; className?: string };

export function LinkButton({ to, variant, size, icon, children, className }: LinkButtonProps) {
  return (
    <Link to={to} className={buttonClass(variant, size, className)}>
      {icon}
      {children}
    </Link>
  );
}

/** External link styled as a button; opens in a new tab. */
export function ExternalButton({ href, variant, size, icon, children, className }: Omit<LinkButtonProps, "to"> & { href: string }) {
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className={buttonClass(variant, size, className)}>
      {icon}
      {children}
    </a>
  );
}

export function Card({ className, children }: { className?: string; children: ReactNode }) {
  return <div className={cx("rounded-xl border border-slate-200 bg-white shadow-sm", className)}>{children}</div>;
}

export function CardHeader({ title, action, subtitle }: { title: ReactNode; action?: ReactNode; subtitle?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
      <div className="min-w-0">
        <h2 className="font-semibold text-slate-900">{title}</h2>
        {subtitle && <p className="mt-0.5 text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action}
    </div>
  );
}

export function PageHeader({ title, subtitle, action }: { title: ReactNode; subtitle?: ReactNode; action?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="text-xl font-bold text-slate-900 sm:text-2xl">{title}</h1>
        {subtitle && <p className="mt-1 max-w-2xl text-sm text-slate-500">{subtitle}</p>}
      </div>
      {action && <div className="flex flex-wrap gap-2">{action}</div>}
    </div>
  );
}

type Tone = "neutral" | "brand" | "red" | "amber" | "green";
const badgeTones: Record<Tone, string> = {
  neutral: "bg-slate-100 text-slate-700",
  brand: "bg-brand-50 text-brand-700",
  red: "bg-red-50 text-red-700 ring-1 ring-red-200",
  amber: "bg-amber-50 text-amber-800 ring-1 ring-amber-200",
  green: "bg-emerald-50 text-emerald-700 ring-1 ring-emerald-200",
};

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return (
    <span className={cx("inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium whitespace-nowrap", badgeTones[tone], className)}>
      {children}
    </span>
  );
}

/** Small count bubble for the menu. */
export function CountBadge({ count, tone = "red" }: { count: string; tone?: "red" | "neutral" }) {
  return (
    <span
      className={cx(
        "num inline-flex min-w-5 items-center justify-center rounded-full px-1.5 text-xs font-semibold leading-5",
        tone === "red" ? "bg-red-600 text-white" : "bg-slate-200 text-slate-700",
      )}
    >
      {count}
    </span>
  );
}

type AlertKind = "warning" | "error" | "info" | "success";
const alertStyles: Record<AlertKind, { box: string; icon: ReactNode }> = {
  warning: { box: "border-amber-200 bg-amber-50 text-amber-900", icon: <AlertTriangle className="size-5 shrink-0 text-amber-500" /> },
  error: { box: "border-red-200 bg-red-50 text-red-800", icon: <XCircle className="size-5 shrink-0 text-red-500" /> },
  info: { box: "border-sky-200 bg-sky-50 text-sky-900", icon: <Info className="size-5 shrink-0 text-sky-500" /> },
  success: { box: "border-emerald-200 bg-emerald-50 text-emerald-900", icon: <CheckCircle2 className="size-5 shrink-0 text-emerald-500" /> },
};

export function Alert({ kind = "info", children, action, className }: { kind?: AlertKind; children: ReactNode; action?: ReactNode; className?: string }) {
  const s = alertStyles[kind];
  return (
    <div role={kind === "error" ? "alert" : "status"} className={cx("flex flex-wrap items-start gap-3 rounded-lg border px-4 py-3 text-sm", s.box, className)}>
      {s.icon}
      <div className="min-w-0 flex-1 user-text">{children}</div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}

export function Spinner({ className }: { className?: string }) {
  return <Loader2 className={cx("size-5 animate-spin text-slate-400", className)} />;
}

export function PageLoading() {
  return (
    <div className="flex min-h-48 items-center justify-center">
      <Spinner className="size-7" />
    </div>
  );
}

export function EmptyState({ icon, title, children }: { icon?: ReactNode; title: ReactNode; children?: ReactNode }) {
  return (
    <div className="flex flex-col items-center justify-center gap-2 px-6 py-14 text-center">
      {icon && <div className="mb-1 text-slate-300">{icon}</div>}
      <p className="font-medium text-slate-600">{title}</p>
      {children}
    </div>
  );
}

type FieldProps = { label: ReactNode; hint?: ReactNode; error?: string; children: (id: string) => ReactNode; className?: string };

export function Field({ label, hint, error, children, className }: FieldProps) {
  const id = useId();
  return (
    <div className={className}>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children(id)}
      {error ? (
        <p className="mt-1 text-xs text-red-600">{error}</p>
      ) : (
        hint && <p className="mt-1 text-xs text-slate-500">{hint}</p>
      )}
    </div>
  );
}

const inputBase =
  "block w-full rounded-lg border bg-white px-3 text-sm text-slate-900 placeholder:text-slate-400 shadow-sm transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/30 disabled:bg-slate-50";

export function Input({ invalid, className, ...rest }: InputHTMLAttributes<HTMLInputElement> & { invalid?: boolean }) {
  return (
    <input
      className={cx(inputBase, "h-10", invalid ? "border-red-400" : "border-slate-300 focus:border-brand-500", className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
}

export function Textarea({ invalid, className, ...rest }: TextareaHTMLAttributes<HTMLTextAreaElement> & { invalid?: boolean }) {
  return (
    <textarea
      className={cx(inputBase, "py-2 leading-7", invalid ? "border-red-400" : "border-slate-300 focus:border-brand-500", className)}
      aria-invalid={invalid || undefined}
      {...rest}
    />
  );
}

export function Select({ className, children, ...rest }: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select className={cx(inputBase, "h-10 border-slate-300 focus:border-brand-500", className)} {...rest}>
      {children}
    </select>
  );
}

export function Toggle({
  checked,
  onChange,
  disabled,
  label,
}: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
  label: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      onClick={() => onChange(!checked)}
      className={cx(
        "inline-flex h-6 w-11 shrink-0 items-center rounded-full px-0.5 transition-colors",
        "focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand-500 disabled:opacity-50",
        // knob sits at the start edge when off and the end edge when on (works for RTL and LTR)
        checked ? "justify-end bg-emerald-500" : "justify-start bg-slate-300",
      )}
    >
      <span className="inline-block size-5 rounded-full bg-white shadow" />
    </button>
  );
}

export function Tabs<T extends string>({
  value,
  onChange,
  items,
}: {
  value: T;
  onChange: (v: T) => void;
  items: { value: T; label: ReactNode; count?: string }[];
}) {
  return (
    <div role="tablist" className="inline-flex max-w-full gap-1 overflow-x-auto rounded-lg bg-slate-100 p-1">
      {items.map((it) => (
        <button
          key={it.value}
          role="tab"
          type="button"
          aria-selected={value === it.value}
          onClick={() => onChange(it.value)}
          className={cx(
            "flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
            value === it.value ? "bg-white text-slate-900 shadow-sm" : "text-slate-600 hover:text-slate-900",
          )}
        >
          {it.label}
          {it.count && <span className="num text-xs text-slate-500">{it.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Modal({
  open,
  onClose,
  title,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: ReactNode;
  children: ReactNode;
  footer?: ReactNode;
  size?: "md" | "lg";
}) {
  const ref = useRef<HTMLDialogElement>(null);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (open && !d.open) {
      d.showModal();
      // React's autoFocus runs before showModal, which then moves focus; mark fields with data-autofocus instead
      d.querySelector<HTMLElement>("[data-autofocus]")?.focus();
    }
    if (!open && d.open) d.close();
  }, [open]);

  return (
    <dialog
      ref={ref}
      onCancel={(e) => {
        e.preventDefault();
        onClose();
      }}
      onClick={(e) => {
        if (e.target === ref.current) onClose();
      }}
      className={cx(
        "m-auto w-[calc(100%-2rem)] rounded-xl bg-white p-0 shadow-xl backdrop:bg-slate-900/40",
        size === "lg" ? "max-w-2xl" : "max-w-md",
      )}
    >
      {open && (
        <div className="flex max-h-[85vh] flex-col">
          <div className="flex items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
            <h2 className="font-semibold text-slate-900">{title}</h2>
            <button type="button" onClick={onClose} className="rounded-md p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-600">
              <X className="size-5" />
            </button>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-slate-100 px-5 py-3">{footer}</div>}
        </div>
      )}
    </dialog>
  );
}

export function ConfirmDialog({
  open,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel,
  cancelLabel,
  danger,
  loading,
}: {
  open: boolean;
  onClose: () => void;
  onConfirm: () => void;
  title: ReactNode;
  body: ReactNode;
  confirmLabel: string;
  cancelLabel: string;
  danger?: boolean;
  loading?: boolean;
}) {
  return (
    <Modal
      open={open}
      onClose={onClose}
      title={title}
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {cancelLabel}
          </Button>
          <Button variant={danger ? "danger" : "primary"} onClick={onConfirm} loading={loading}>
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-sm leading-7 text-slate-600">{body}</div>
    </Modal>
  );
}

export function ProgressBar({ value, max, tone }: { value: number; max: number; tone?: "brand" | "amber" | "red" }) {
  const pct = max > 0 ? Math.min(100, (value / max) * 100) : 0;
  const auto = pct >= 100 ? "red" : pct >= 85 ? "amber" : "brand";
  const color = { brand: "bg-brand-500", amber: "bg-amber-500", red: "bg-red-500" }[tone ?? auto];
  return (
    <div className="h-2 w-full overflow-hidden rounded-full bg-slate-100" role="progressbar" aria-valuenow={value} aria-valuemax={max}>
      <div className={cx("h-full rounded-full transition-all", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}
