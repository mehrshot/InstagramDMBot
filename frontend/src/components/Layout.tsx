import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation } from "react-router";
import {
  BellRing,
  BookOpen,
  Camera,
  FlaskConical,
  HelpCircle,
  Inbox,
  Languages,
  LayoutDashboard,
  LogOut,
  Menu,
  Package,
  Settings,
  UserRound,
  X,
} from "lucide-react";
import { useDashboard, useMe } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useI18n } from "../i18n";
import { useHandoffWatcher } from "../lib/notifications";
import { CountBadge, cx } from "./ui";

type Item = { to: string; label: string; icon: ReactNode; badge?: number; badgeTone?: "red" | "neutral"; end?: boolean };

export default function Layout() {
  const { t, f, toggleLang } = useI18n();
  const { logout } = useAuth();
  const { data: me } = useMe();
  const { data: dash } = useDashboard();
  const [open, setOpen] = useState(false);
  const location = useLocation();

  useHandoffWatcher(dash);

  // Close the mobile drawer on navigation
  useEffect(() => setOpen(false), [location.pathname]);

  // "(2) پنل مزون مهسا" in the browser tab
  useEffect(() => {
    const base = me ? t.panelTitle(me.shop.name) : t.appName;
    const n = dash?.open_handoffs ?? 0;
    document.title = n > 0 ? `(${f.num(n)}) ${base}` : base;
  }, [me, dash, t, f]);

  const items: Item[] = [
    { to: "/", label: t.nav.dashboard, icon: <LayoutDashboard />, end: true },
    { to: "/handoffs", label: t.nav.handoffs, icon: <BellRing />, badge: dash?.open_handoffs },
    { to: "/inbox", label: t.nav.inbox, icon: <Inbox /> },
    { to: "/unanswered", label: t.nav.unanswered, icon: <HelpCircle />, badge: dash?.last_7_days.open_unanswered, badgeTone: "neutral" },
    { to: "/knowledge", label: t.nav.knowledge, icon: <BookOpen /> },
    { to: "/products", label: t.nav.products, icon: <Package /> },
    { to: "/playground", label: t.nav.playground, icon: <FlaskConical /> },
    { to: "/settings", label: t.nav.settings, icon: <Settings /> },
    { to: "/instagram", label: t.nav.instagram, icon: <Camera /> },
    { to: "/account", label: t.nav.account, icon: <UserRound /> },
  ];

  const botOn = dash?.setup.bot_enabled;

  const sidebar = (
    <div className="flex h-full flex-col">
      <div className="flex items-center gap-3 px-4 py-5">
        <img src="/favicon.svg" alt="" className="size-9" />
        <div className="min-w-0">
          <div className="truncate font-bold text-slate-900">{me?.shop.name ?? t.appName}</div>
          {dash && (
            <div className="flex items-center gap-1.5 text-xs text-slate-500">
              <span className={cx("size-2 rounded-full", botOn ? "bg-emerald-500" : "bg-slate-300")} />
              {botOn ? t.nav.botOnShort : t.nav.botOffShort}
            </div>
          )}
        </div>
      </div>
      <nav className="flex-1 space-y-0.5 overflow-y-auto px-3">
        {items.map((it) => (
          <NavLink
            key={it.to}
            to={it.to}
            end={it.end}
            className={({ isActive }) =>
              cx(
                "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors [&>svg]:size-[18px] [&>svg]:shrink-0",
                isActive ? "bg-brand-50 text-brand-700" : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
              )
            }
          >
            {it.icon}
            <span className="flex-1 truncate">{it.label}</span>
            {!!it.badge && <CountBadge count={f.num(it.badge)} tone={it.badgeTone} />}
          </NavLink>
        ))}
      </nav>
      <div className="space-y-0.5 border-t border-slate-200 p-3 text-sm">
        <button
          type="button"
          onClick={toggleLang}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100"
        >
          <Languages className="size-[18px]" />
          {t.otherLang}
        </button>
        <button
          type="button"
          onClick={logout}
          className="flex w-full items-center gap-3 rounded-lg px-3 py-2 text-slate-600 hover:bg-slate-100"
        >
          <LogOut className="size-[18px] rtl:-scale-x-100" />
          {t.common.logout}
        </button>
        <Link to="/privacy" className="block px-3 pt-2 text-xs text-slate-400 hover:text-slate-600">
          {t.nav.legal}
        </Link>
      </div>
    </div>
  );

  return (
    <div className="min-h-screen lg:flex">
      {/* desktop sidebar */}
      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 border-e border-slate-200 bg-white lg:block">{sidebar}</aside>

      {/* mobile top bar + drawer */}
      <header className="sticky top-0 z-30 flex items-center justify-between border-b border-slate-200 bg-white px-4 py-3 lg:hidden">
        <button type="button" onClick={() => setOpen(true)} className="relative rounded-md p-1.5 text-slate-600 hover:bg-slate-100" aria-label={t.nav.menu}>
          <Menu className="size-6" />
          {!!dash?.open_handoffs && <span className="absolute -top-0.5 -end-0.5 size-2.5 rounded-full bg-red-600" />}
        </button>
        <span className="truncate font-bold text-slate-900">{me?.shop.name ?? t.appName}</span>
        <img src="/favicon.svg" alt="" className="size-7" />
      </header>
      {open && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-slate-900/40" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 start-0 w-72 max-w-[85%] bg-white shadow-xl">
            <button
              type="button"
              onClick={() => setOpen(false)}
              className="absolute top-4 end-3 rounded-md p-1 text-slate-400 hover:bg-slate-100"
              aria-label={t.common.close}
            >
              <X className="size-5" />
            </button>
            {sidebar}
          </aside>
        </div>
      )}

      <main className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 lg:py-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
