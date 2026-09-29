import { useEffect, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ExternalLink, FileSpreadsheet, Package, RefreshCw, Search, Sheet, Upload } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { Product, ProductPage, Source } from "../api/types";
import ProductWizard, { type WizardStart } from "../components/ProductWizard";
import { useToast } from "../components/toast";
import { Alert, Badge, Button, Card, ConfirmDialog, EmptyState, Input, PageHeader, PageLoading, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

export default function Products() {
  const { t } = useI18n();
  const source = useQuery({ queryKey: keys.source, queryFn: () => api<Source>("/products/source") });
  const [wizard, setWizard] = useState<WizardStart | null>(null);

  const header = <PageHeader icon={<Package />} title={t.products.title} subtitle={t.products.subtitle} />;
  if (source.isPending)
    return (
      <>
        {header}
        <PageLoading />
      </>
    );
  if (source.error)
    return (
      <>
        {header}
        <Alert kind="error">{errorMessage(source.error, t)}</Alert>
      </>
    );

  const s = source.data;
  const showWizard = !s.connected || wizard !== null;

  return (
    <>
      {header}
      {showWizard ? (
        <ProductWizard start={wizard ?? {}} onCancel={s.connected ? () => setWizard(null) : undefined} onDone={() => setWizard(null)} />
      ) : (
        <div className="space-y-6">
          <SourceStatus
            source={s}
            onChangeColumns={() => setWizard({ kind: "google_sheet", url: s.url ?? "", mapping: s.column_mapping })}
            onReupload={() => setWizard({ kind: "upload", mapping: s.column_mapping })}
          />
          <ProductTable />
        </div>
      )}
    </>
  );
}

/** Where the products come from, how many there are, and the source's actions. */
function SourceStatus({ source, onChangeColumns, onReupload }: { source: Source; onChangeColumns: () => void; onReupload: () => void }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const isSheet = source.kind === "google_sheet";

  const invalidate = () => {
    qc.invalidateQueries({ queryKey: ["products"] });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  };

  const sync = useMutation({
    mutationFn: () => api<Source>("/products/sync", { method: "POST" }),
    onSuccess: () => {
      toast.success(t.products.synced);
      invalidate();
    },
    onError: (err) => {
      toast.error(errorMessage(err, t));
      invalidate();
    },
  });

  const disconnect = useMutation({
    mutationFn: () => api("/products/source", { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(false);
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <Card className="animate-pop-in">
      <div className="flex flex-wrap items-center gap-x-8 gap-y-5 p-5 sm:p-6">
        {/* real minimum width: on phones the numbers wrap below instead of squeezing this */}
        <div className="flex min-w-56 flex-1 items-center gap-4">
          <span aria-hidden className={cx("flex size-12 shrink-0 items-center justify-center rounded-2xl", isSheet ? "bg-emerald-50 text-emerald-600" : "bg-brand-50 text-brand-700")}>
            {isSheet ? <Sheet className="size-6" /> : <FileSpreadsheet className="size-6" />}
          </span>
          <div className="min-w-0">
            <div className="text-xs font-semibold text-slate-500">{t.products.statusTitle}</div>
            <div className="mt-0.5 font-bold text-ink-950">{isSheet ? t.products.kindSheet : t.products.kindFile}</div>
            {isSheet && source.url && (
              <a href={source.url} target="_blank" rel="noopener noreferrer" className="mt-0.5 inline-flex items-center gap-1 text-sm font-semibold text-brand-700 hover:underline">
                {t.products.openSheet}
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            )}
          </div>
        </div>

        <dl className="flex gap-8">
          <div>
            <dt className="text-xs font-semibold text-slate-500">{t.products.productCount}</dt>
            <dd className="num mt-0.5 text-2xl font-extrabold text-ink-950">{f.num(source.product_count ?? 0)}</dd>
          </div>
          {source.last_synced_at && (
            <div>
              <dt className="text-xs font-semibold text-slate-500">{t.products.lastSync}</dt>
              <dd className="mt-1.5 text-sm font-bold text-ink-900" title={f.dateTime(source.last_synced_at)}>
                {f.ago(source.last_synced_at)}
              </dd>
            </div>
          )}
        </dl>
      </div>

      {source.last_error && (
        <div className="px-5 pb-5 sm:px-6">
          <Alert kind="warning">
            {source.last_error}
            <div className="mt-1 text-xs opacity-80">{t.products.lastErrorNote}</div>
          </Alert>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-5 py-3 sm:px-6">
        {isSheet && (
          <Button variant="secondary" size="sm" icon={<RefreshCw className={cx("size-4", sync.isPending && "animate-spin")} />} disabled={sync.isPending} onClick={() => sync.mutate()}>
            {t.products.syncNow}
          </Button>
        )}
        {isSheet ? (
          <Button variant="secondary" size="sm" onClick={onChangeColumns}>
            {t.products.changeColumns}
          </Button>
        ) : (
          <Button variant="secondary" size="sm" icon={<Upload className="size-4" />} onClick={onReupload}>
            {t.products.reupload}
          </Button>
        )}
        <Button variant="ghost" size="sm" className="sm:ms-auto" onClick={() => setConfirm(true)}>
          <span className="text-red-700">{t.products.disconnect}</span>
        </Button>
      </div>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => disconnect.mutate()}
        loading={disconnect.isPending}
        danger
        title={t.products.disconnectConfirmTitle}
        body={t.products.disconnectConfirmBody}
        confirmLabel={t.products.disconnect}
        cancelLabel={t.common.cancel}
      />
    </Card>
  );
}

const PAGE = 50;

function ProductTable() {
  const { t, f } = useI18n();
  const [q, setQ] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const id = setTimeout(() => {
      setSearch(q.trim());
      setOffset(0);
    }, 300);
    return () => clearTimeout(id);
  }, [q]);

  const { data, isPending, error, isFetching } = useQuery({
    queryKey: keys.products(search, offset),
    queryFn: () => api<ProductPage>("/products", { query: { q: search, offset, limit: PAGE } }),
    placeholderData: keepPreviousData,
  });

  const pages = data ? Math.max(1, Math.ceil(data.total / PAGE)) : 1;
  const page = Math.floor(offset / PAGE) + 1;

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4 sm:px-6">
        <h2 className="flex items-center gap-2 font-bold text-ink-950">
          {t.products.title}
          {data && <Badge tone="brand">{t.products.total(f.num(data.total))}</Badge>}
        </h2>
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute start-3.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden />
          <Input
            className="ps-10"
            placeholder={t.products.searchPlaceholder}
            aria-label={t.products.searchPlaceholder}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            maxLength={100}
          />
        </div>
      </div>

      {isPending ? (
        <PageLoading />
      ) : error ? (
        <div className="p-5">
          <Alert kind="error">{errorMessage(error, t)}</Alert>
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState icon={<Package />} title={t.common.noResults} />
      ) : (
        <div className={cx("transition-opacity", isFetching && "opacity-60")}>
          {/* phones: one card per product */}
          <ul className="divide-y divide-slate-100 md:hidden">
            {data.items.map((p) => (
              <li key={p.id} className="flex items-start justify-between gap-4 px-5 py-4">
                <div className="min-w-0">
                  <div className="font-bold text-ink-950">{p.name}</div>
                  <div className="mt-1 flex flex-wrap gap-1.5 text-xs text-slate-500">
                    {[p.category, p.color, p.size, p.sku].filter(Boolean).map((v) => (
                      <span key={String(v)} className="num rounded-md bg-slate-100 px-1.5 py-0.5">
                        {v}
                      </span>
                    ))}
                  </div>
                </div>
                <div className="shrink-0 text-end">
                  <div className="num text-sm font-bold text-ink-950">{p.price != null ? f.num(p.price) : "—"}</div>
                  <div className="mt-1">
                    <Stock p={p} />
                  </div>
                </div>
              </li>
            ))}
          </ul>

          {/* wider screens: a table */}
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full text-sm">
              <thead className="text-xs text-slate-500">
                <tr className="border-b border-slate-100">
                  <th className="px-6 py-3 text-start font-semibold">{t.products.colName}</th>
                  <th className="px-4 py-3 text-start font-semibold">{t.products.colSku}</th>
                  <th className="px-4 py-3 text-start font-semibold">{t.products.colColor}</th>
                  <th className="px-4 py-3 text-start font-semibold">{t.products.colSize}</th>
                  <th className="px-4 py-3 text-end font-semibold">{t.products.colPrice}</th>
                  <th className="px-6 py-3 text-end font-semibold">{t.products.colStock}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((p) => (
                  <tr key={p.id} className="transition-colors hover:bg-brand-50/40">
                    <td className="px-6 py-3.5">
                      <div className="font-bold text-ink-950">{p.name}</div>
                      {p.category && <div className="text-xs text-slate-400">{p.category}</div>}
                    </td>
                    <td className="num px-4 py-3.5 text-slate-500">{p.sku ?? "—"}</td>
                    <td className="px-4 py-3.5 text-slate-600">{p.color ?? "—"}</td>
                    <td className="num px-4 py-3.5 text-slate-600">{p.size ?? "—"}</td>
                    <td className="num px-4 py-3.5 text-end font-semibold text-ink-950">{p.price != null ? f.num(p.price) : "—"}</td>
                    <td className="px-6 py-3.5 text-end">
                      <Stock p={p} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {pages > 1 && (
            <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-3 text-sm sm:px-6">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                {t.products.prev}
              </Button>
              <span className="num font-medium text-slate-500">{t.products.pageOf(f.num(page), f.num(pages))}</span>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setOffset(offset + PAGE)}>
                {t.products.nextPage}
              </Button>
            </div>
          )}
        </div>
      )}
    </Card>
  );
}

function Stock({ p }: { p: Product }) {
  const { t, f } = useI18n();
  if (p.stock == null) return <span className="text-xs text-slate-400">{t.products.stockUnknown}</span>;
  if (p.stock === 0) return <Badge tone="red">{t.products.outOfStock}</Badge>;
  return <span className="num text-sm font-semibold text-emerald-700">{f.num(p.stock)}</span>;
}
