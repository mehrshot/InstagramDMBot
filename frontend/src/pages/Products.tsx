import { useEffect, useRef, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Download, ExternalLink, FileSpreadsheet, Info, Package, RefreshCw, Search, Sheet, Upload } from "lucide-react";
import { api, apiUrl } from "../api/client";
import { keys } from "../api/queries";
import type { Preview, ProductField, ProductPage, Source } from "../api/types";
import { useToast } from "../components/toast";
import {
  Alert,
  Badge,
  Button,
  Card,
  CardHeader,
  ConfirmDialog,
  EmptyState,
  Field,
  Input,
  PageHeader,
  PageLoading,
  Select,
  cx,
} from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

type Kind = "google_sheet" | "upload";
type Mapping = Record<string, string>;

// Field labels come from the API in Persian; English panel uses these.
const FIELD_LABELS_EN: Record<string, string> = {
  name: "Product name",
  sku: "Product code",
  category: "Category",
  color: "Color",
  size: "Size",
  price: "Price (Toman)",
  stock: "Stock",
  description: "Description",
};

export default function Products() {
  const { t } = useI18n();
  const source = useQuery({ queryKey: keys.source, queryFn: () => api<Source>("/products/source") });
  const [wizard, setWizard] = useState<WizardStart | null>(null);

  if (source.isPending) return <PageLoading />;
  if (source.error) return <Alert kind="error">{errorMessage(source.error, t)}</Alert>;

  const s = source.data;
  const showWizard = !s.connected || wizard !== null;

  return (
    <div className="space-y-6">
      <PageHeader title={t.products.title} subtitle={t.products.subtitle} />
      {showWizard ? (
        <Wizard start={wizard ?? {}} onCancel={s.connected ? () => setWizard(null) : undefined} onDone={() => setWizard(null)} />
      ) : (
        <>
          <SourceStatus
            source={s}
            onChangeColumns={() => setWizard({ kind: "google_sheet", url: s.url ?? "", mapping: s.column_mapping })}
            onReupload={() => setWizard({ kind: "upload", mapping: s.column_mapping })}
          />
          <ProductTable />
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------- status

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
    <Card>
      <CardHeader
        title={t.products.statusTitle}
        action={
          <Badge tone={isSheet ? "green" : "neutral"}>
            {isSheet ? <Sheet className="size-3.5" /> : <FileSpreadsheet className="size-3.5" />}
            {isSheet ? t.products.kindSheet : t.products.kindFile}
          </Badge>
        }
      />
      <div className="space-y-4 p-5">
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">{t.products.productCount}</dt>
            <dd className="num mt-0.5 text-lg font-semibold text-slate-900">{f.num(source.product_count ?? 0)}</dd>
          </div>
          {source.last_synced_at && (
            <div>
              <dt className="text-slate-500">{t.products.lastSync}</dt>
              <dd className="mt-0.5 font-medium text-slate-900" title={f.dateTime(source.last_synced_at)}>
                {f.ago(source.last_synced_at)}
              </dd>
            </div>
          )}
          {isSheet && source.url && (
            <div className="col-span-2 sm:col-span-1">
              <dt className="text-slate-500">{t.products.sheetTitle}</dt>
              <dd className="mt-0.5">
                <a href={source.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline">
                  {t.products.openSheet}
                  <ExternalLink className="size-3.5" />
                </a>
              </dd>
            </div>
          )}
        </dl>

        {source.last_error && (
          <Alert kind="warning">
            {source.last_error}
            <div className="mt-1 text-xs opacity-80">{t.products.lastErrorNote}</div>
          </Alert>
        )}

        <div className="flex flex-wrap gap-2">
          {isSheet && (
            <Button variant="secondary" size="sm" icon={<RefreshCw className="size-4" />} loading={sync.isPending} onClick={() => sync.mutate()}>
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
          <Button variant="ghost" size="sm" className="text-red-600 hover:bg-red-50" onClick={() => setConfirm(true)}>
            {t.products.disconnect}
          </Button>
        </div>
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

// ---------------------------------------------------------------- wizard

type WizardStart = { kind?: Kind; url?: string; mapping?: Mapping };

function Wizard({ start, onCancel, onDone }: { start: WizardStart; onCancel?: () => void; onDone: () => void }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [kind, setKind] = useState<Kind>(start.kind ?? "google_sheet");
  const [url, setUrl] = useState(start.url ?? "");
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Mapping>({});
  const fileInput = useRef<HTMLInputElement>(null);

  const fields = useQuery({ queryKey: keys.fields, queryFn: () => api<ProductField[]>("/products/fields"), staleTime: Infinity });

  const runPreview = useMutation({
    mutationFn: () => {
      if (kind === "google_sheet") return api<Preview>("/products/sheet/preview", { method: "POST", json: { url: url.trim() } });
      const form = new FormData();
      form.append("file", file!);
      return api<Preview>("/products/file/preview", { method: "POST", form });
    },
    onSuccess: (p) => {
      setPreview(p);
      // keep the current mapping where those columns still exist, fill the rest from the suggestion
      const next: Mapping = Object.fromEntries(Object.entries(start.mapping ?? {}).filter(([, col]) => p.headers.includes(col)));
      for (const [field, col] of Object.entries(p.suggested_mapping)) {
        if (!next[field] && !Object.values(next).includes(col)) next[field] = col;
      }
      setMapping(next);
      setStep(2);
    },
  });

  // "Change columns" on a connected sheet jumps straight to the preview
  const autoRan = useRef(false);
  useEffect(() => {
    if (!autoRan.current && start.kind === "google_sheet" && start.url) {
      autoRan.current = true;
      runPreview.mutate();
    }
  }, [start, runPreview]);

  const save = useMutation({
    mutationFn: () => {
      if (kind === "google_sheet") return api<Source>("/products/sheet", { method: "PUT", json: { url: url.trim(), column_mapping: mapping } });
      const form = new FormData();
      form.append("file", file!);
      form.append("column_mapping", JSON.stringify(mapping));
      return api<Source>("/products/file", { method: "POST", form });
    },
    onSuccess: (src) => {
      toast.success(t.products.connectedToast(f.num(src.product_count ?? 0)));
      qc.setQueryData(keys.source, src);
      qc.invalidateQueries({ queryKey: ["products"] });
      qc.invalidateQueries({ queryKey: keys.dashboard });
      onDone();
    },
  });

  const canPreview = kind === "google_sheet" ? url.trim().length > 10 : file !== null;
  const steps = [t.products.step1, t.products.step2, t.products.step3];

  return (
    <Card>
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <ol className="flex flex-wrap items-center gap-2 text-sm">
          {steps.map((label, i) => {
            const n = (i + 1) as 1 | 2 | 3;
            return (
              <li key={label} className="flex items-center gap-2">
                {i > 0 && <span className="h-px w-5 bg-slate-200" />}
                <span
                  className={cx(
                    "num flex size-6 items-center justify-center rounded-full text-xs font-semibold",
                    n < step ? "bg-emerald-500 text-white" : n === step ? "bg-brand-600 text-white" : "bg-slate-100 text-slate-400",
                  )}
                >
                  {n < step ? <Check className="size-3.5" /> : f.num(n)}
                </span>
                <span className={n === step ? "font-medium text-slate-900" : "text-slate-500"}>{label}</span>
              </li>
            );
          })}
        </ol>
        {onCancel && (
          <Button variant="ghost" size="sm" onClick={onCancel}>
            {t.products.cancelWizard}
          </Button>
        )}
      </div>

      <div className="p-5">
        {step === 1 && (
          <div className="space-y-5">
            <div className="grid gap-3 sm:grid-cols-2">
              <SourceOption
                selected={kind === "google_sheet"}
                onSelect={() => setKind("google_sheet")}
                icon={<Sheet className="size-6 text-emerald-600" />}
                title={t.products.sheetTitle}
                badge={t.products.sheetRecommended}
                desc={t.products.sheetDesc}
              />
              <SourceOption
                selected={kind === "upload"}
                onSelect={() => setKind("upload")}
                icon={<FileSpreadsheet className="size-6 text-sky-600" />}
                title={t.products.fileTitle}
                desc={t.products.fileDesc}
              />
            </div>

            {kind === "google_sheet" ? (
              <div className="space-y-3">
                <Field label={t.products.sheetUrl}>
                  {(id) => (
                    <Input
                      id={id}
                      dir="ltr"
                      type="url"
                      placeholder="https://docs.google.com/spreadsheets/d/..."
                      value={url}
                      onChange={(e) => setUrl(e.target.value)}
                    />
                  )}
                </Field>
                <div className="flex gap-2 rounded-lg bg-slate-50 p-3 text-sm text-slate-600">
                  <Info className="mt-0.5 size-4 shrink-0 text-slate-400" />
                  <div>
                    <div className="font-medium text-slate-700">{t.products.sheetGuideTitle}</div>
                    <div className="ltr mt-1 text-xs">
                      Share → General access → <b>Anyone with the link</b> → Viewer → Copy link
                    </div>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <input
                  ref={fileInput}
                  type="file"
                  className="hidden"
                  accept=".xlsx,.xls,.csv"
                  onChange={(e) => {
                    setFile(e.target.files?.[0] ?? null);
                    runPreview.reset();
                  }}
                />
                <Button variant="secondary" icon={<Upload className="size-4" />} onClick={() => fileInput.current?.click()}>
                  {t.products.chooseFile}
                </Button>
                {file && (
                  <span className="text-sm text-slate-600" dir="auto">
                    {t.products.fileChosen(file.name)}
                  </span>
                )}
              </div>
            )}

            <div className="flex items-center gap-2 text-sm text-slate-500">
              <span>{t.products.templateHint}</span>
              {/* no login needed, so a plain link works */}
              <a href={apiUrl("/products/template.csv")} className="inline-flex items-center gap-1 font-medium text-brand-600 hover:underline" download>
                <Download className="size-4" />
                {t.products.template}
              </a>
            </div>

            {runPreview.error && <Alert kind="error">{errorMessage(runPreview.error, t)}</Alert>}

            <div className="flex justify-end">
              <Button onClick={() => runPreview.mutate()} loading={runPreview.isPending} disabled={!canPreview}>
                {runPreview.isPending ? t.products.previewing : t.products.preview}
              </Button>
            </div>
          </div>
        )}

        {step === 2 && preview && (
          <div className="space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm text-slate-500">{t.products.previewHint}</p>
              <Badge tone="brand">{t.products.rowCount(f.num(preview.row_count))}</Badge>
            </div>
            <div className="overflow-x-auto rounded-lg border border-slate-200">
              <table className="w-full text-sm">
                <thead className="bg-slate-50 text-slate-600">
                  <tr>
                    {preview.headers.map((h) => (
                      <th key={h} className="whitespace-nowrap px-3 py-2 text-start font-medium">
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {preview.sample_rows.map((row, i) => (
                    <tr key={i}>
                      {preview.headers.map((h) => (
                        <td key={h} className="num whitespace-nowrap px-3 py-2 text-slate-700">
                          {String((row as Record<string, unknown>)[h] ?? "")}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="flex justify-between">
              <Button variant="secondary" onClick={() => setStep(1)}>
                {t.common.back}
              </Button>
              <Button onClick={() => setStep(3)}>{t.common.next}</Button>
            </div>
          </div>
        )}

        {step === 3 && preview && (
          <div className="space-y-4">
            <p className="text-sm text-slate-600">{t.products.mappingHint}</p>
            {fields.isPending ? (
              <PageLoading />
            ) : fields.error ? (
              <Alert kind="error">{errorMessage(fields.error, t)}</Alert>
            ) : (
              <MappingForm fields={fields.data} headers={preview.headers} mapping={mapping} onChange={setMapping} />
            )}
            <Alert kind="info">{t.products.mappingExtra}</Alert>
            {save.error && <Alert kind="error">{errorMessage(save.error, t)}</Alert>}
            <div className="flex justify-between">
              <Button variant="secondary" onClick={() => setStep(2)}>
                {t.common.back}
              </Button>
              <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!mapping.name}>
                {t.products.saveConnect}
              </Button>
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}

function SourceOption({
  selected,
  onSelect,
  icon,
  title,
  badge,
  desc,
}: {
  selected: boolean;
  onSelect: () => void;
  icon: React.ReactNode;
  title: string;
  badge?: string;
  desc: string;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-pressed={selected}
      className={cx(
        "flex items-start gap-3 rounded-xl border-2 p-4 text-start transition",
        selected ? "border-brand-500 bg-brand-50/50" : "border-slate-200 hover:border-slate-300",
      )}
    >
      {icon}
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-2 font-semibold text-slate-900">
          {title}
          {badge && <Badge tone="green">{badge}</Badge>}
        </div>
        <p className="mt-1 text-sm text-slate-500">{desc}</p>
      </div>
    </button>
  );
}

function MappingForm({ fields, headers, mapping, onChange }: { fields: ProductField[]; headers: string[]; mapping: Mapping; onChange: (m: Mapping) => void }) {
  const { t, lang } = useI18n();
  const used = new Set(Object.values(mapping));

  function set(field: string, column: string) {
    const next = { ...mapping };
    if (column) next[field] = column;
    else delete next[field];
    onChange(next);
  }

  return (
    <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
      {fields.map((fld) => {
        const label = lang === "en" ? (FIELD_LABELS_EN[fld.key] ?? fld.label) : fld.label;
        return (
          <Field
            key={fld.key}
            label={
              <>
                {label}
                {fld.required && <span className="ms-1 text-xs font-normal text-red-500">({t.products.required})</span>}
              </>
            }
          >
            {(id) => (
              <Select id={id} value={mapping[fld.key] ?? ""} onChange={(e) => set(fld.key, e.target.value)}>
                <option value="">{t.products.none}</option>
                {headers.map((h) => (
                  // each column can be used by only one field
                  <option key={h} value={h} disabled={used.has(h) && mapping[fld.key] !== h}>
                    {h}
                  </option>
                ))}
              </Select>
            )}
          </Field>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------- table

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
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <h2 className="font-semibold text-slate-900">
          {t.products.title}
          {data && <span className="num ms-2 text-sm font-normal text-slate-500">({t.products.total(f.num(data.total))})</span>}
        </h2>
        <div className="relative w-full sm:w-72">
          <Search className="pointer-events-none absolute start-3 top-1/2 size-4 -translate-y-1/2 text-slate-400" />
          <Input className="ps-9" placeholder={t.products.searchPlaceholder} value={q} onChange={(e) => setQ(e.target.value)} maxLength={100} />
        </div>
      </div>

      {isPending ? (
        <PageLoading />
      ) : error ? (
        <div className="p-5">
          <Alert kind="error">{errorMessage(error, t)}</Alert>
        </div>
      ) : data.items.length === 0 ? (
        <EmptyState icon={<Package className="size-10" />} title={t.common.noResults} />
      ) : (
        <>
          <div className={cx("overflow-x-auto transition-opacity", isFetching && "opacity-60")}>
            <table className="w-full text-sm">
              <thead className="bg-slate-50 text-slate-600">
                <tr>
                  <th className="px-4 py-2.5 text-start font-medium">{t.products.colName}</th>
                  <th className="px-4 py-2.5 text-start font-medium">{t.products.colSku}</th>
                  <th className="px-4 py-2.5 text-start font-medium">{t.products.colColor}</th>
                  <th className="px-4 py-2.5 text-start font-medium">{t.products.colSize}</th>
                  <th className="px-4 py-2.5 text-end font-medium">{t.products.colPrice}</th>
                  <th className="px-4 py-2.5 text-end font-medium">{t.products.colStock}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {data.items.map((p) => (
                  <tr key={p.id} className="hover:bg-slate-50/60">
                    <td className="px-4 py-2.5">
                      <div className="font-medium text-slate-900">{p.name}</div>
                      {p.category && <div className="text-xs text-slate-400">{p.category}</div>}
                    </td>
                    <td className="num px-4 py-2.5 text-slate-500">
                      {p.sku ?? "—"}
                    </td>
                    <td className="px-4 py-2.5 text-slate-600">{p.color ?? "—"}</td>
                    <td className="num px-4 py-2.5 text-slate-600">{p.size ?? "—"}</td>
                    <td className="num px-4 py-2.5 text-end text-slate-900">{p.price != null ? f.num(p.price) : "—"}</td>
                    <td className="num px-4 py-2.5 text-end">
                      {p.stock == null ? (
                        <span className="text-slate-400">{t.products.stockUnknown}</span>
                      ) : p.stock === 0 ? (
                        <Badge tone="red">{t.products.outOfStock}</Badge>
                      ) : (
                        <span className="text-slate-900">{f.num(p.stock)}</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {pages > 1 && (
            <div className="flex items-center justify-between border-t border-slate-100 px-5 py-3 text-sm">
              <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - PAGE))}>
                {t.products.prev}
              </Button>
              <span className="num text-slate-500">{t.products.pageOf(f.num(page), f.num(pages))}</span>
              <Button size="sm" variant="secondary" disabled={page >= pages} onClick={() => setOffset(offset + PAGE)}>
                {t.products.nextPage}
              </Button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
