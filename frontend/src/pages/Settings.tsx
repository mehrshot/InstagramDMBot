import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { Shop, ShopUpdate } from "../api/types";
import { useToast } from "../components/toast";
import { Alert, Button, Card, Field, Input, LinkButton, PageHeader, PageLoading, Textarea, Toggle, cx } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage, fieldError } from "../lib/errors";

type Form = Omit<Shop, "id" | "tone"> & { tone: "friendly" | "formal" };

function toForm(s: Shop): Form {
  return {
    name: s.name,
    bot_enabled: s.bot_enabled,
    tone: s.tone === "formal" ? "formal" : "friendly",
    use_emoji: s.use_emoji,
    fallback_message: s.fallback_message,
    forbidden_rules: s.forbidden_rules,
    handoff_pause_minutes: s.handoff_pause_minutes,
  };
}

export default function Settings() {
  const { t } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const shop = useQuery({ queryKey: keys.shop, queryFn: () => api<Shop>("/shop") });
  const [form, setForm] = useState<Form | null>(null);
  const [toneChanged, setToneChanged] = useState(false);

  useEffect(() => {
    if (shop.data && !form) setForm(toForm(shop.data));
  }, [shop.data, form]);

  const original = shop.data ? toForm(shop.data) : null;
  // PATCH only what changed
  const changes: ShopUpdate = {};
  if (form && original) {
    for (const k of Object.keys(form) as (keyof Form)[]) {
      if (form[k] !== original[k]) (changes as Record<string, unknown>)[k] = typeof form[k] === "string" ? (form[k] as string).trim() : form[k];
    }
  }
  const dirty = Object.keys(changes).length > 0;

  const save = useMutation({
    mutationFn: (body: ShopUpdate) => api<Shop>("/shop", { method: "PATCH", json: body }),
    onSuccess: (s, body) => {
      qc.setQueryData(keys.shop, s);
      qc.invalidateQueries({ queryKey: keys.me });
      qc.invalidateQueries({ queryKey: keys.dashboard });
      setForm(toForm(s));
      if (body.tone !== undefined || body.use_emoji !== undefined) setToneChanged(true);
      toast.success(t.common.saved);
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (shop.isPending || !form) return shop.error ? <Alert kind="error">{errorMessage(shop.error, t)}</Alert> : <PageLoading />;

  const set = <K extends keyof Form>(k: K, v: Form[K]) => setForm({ ...form, [k]: v });
  const err = (name: string) => fieldError(save.error, name, t);
  const pauseInvalid = !Number.isInteger(form.handoff_pause_minutes) || form.handoff_pause_minutes < 0 || form.handoff_pause_minutes > 10080;
  const invalid = !form.name.trim() || !form.fallback_message.trim() || pauseInvalid;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (dirty && !invalid) save.mutate(changes);
  }

  return (
    <form onSubmit={submit} className="max-w-2xl space-y-6">
      <PageHeader title={t.settings.title} />

      {toneChanged && (
        <Alert kind="success" action={<LinkButton to="/playground" size="sm" variant="secondary" icon={<FlaskConical className="size-4" />}>{t.nav.playground}</LinkButton>}>
          {t.settings.tryInPlayground}
        </Alert>
      )}

      <Card className="divide-y divide-slate-100">
        <div className="flex items-center justify-between gap-4 p-5">
          <div>
            <div className="font-medium text-slate-900">{t.settings.botEnabled}</div>
            <div className="text-sm text-slate-500">{t.settings.botEnabledHint}</div>
          </div>
          <Toggle checked={form.bot_enabled} onChange={(v) => set("bot_enabled", v)} label={t.settings.botEnabled} />
        </div>

        <div className="p-5">
          <Field label={t.settings.name} hint={t.settings.nameHint} error={err("name") ?? (!form.name.trim() ? t.errors.field.name : undefined)}>
            {(id) => <Input id={id} maxLength={120} value={form.name} onChange={(e) => set("name", e.target.value)} />}
          </Field>
        </div>

        <div className="space-y-4 p-5">
          <div className="text-sm font-medium text-slate-700">{t.settings.tone}</div>
          <div className="grid gap-3 sm:grid-cols-2">
            {(["friendly", "formal"] as const).map((tone) => (
              <button
                key={tone}
                type="button"
                onClick={() => set("tone", tone)}
                aria-pressed={form.tone === tone}
                className={cx(
                  "rounded-xl border-2 p-4 text-start transition",
                  form.tone === tone ? "border-brand-500 bg-brand-50/50" : "border-slate-200 hover:border-slate-300",
                )}
              >
                <div className="font-semibold text-slate-900">{tone === "friendly" ? t.settings.toneFriendly : t.settings.toneFormal}</div>
                <div className="mt-1 text-sm text-slate-500">{tone === "friendly" ? t.settings.toneFriendlyHint : t.settings.toneFormalHint}</div>
              </button>
            ))}
          </div>
          <label className="flex items-center justify-between gap-4">
            <span className="text-sm font-medium text-slate-700">{t.settings.useEmoji}</span>
            <Toggle checked={form.use_emoji} onChange={(v) => set("use_emoji", v)} label={t.settings.useEmoji} />
          </label>
        </div>

        <div className="space-y-5 p-5">
          <Field
            label={t.settings.fallback}
            hint={t.settings.fallbackHint}
            error={err("fallback_message") ?? (!form.fallback_message.trim() ? t.errors.field.fallback_message : undefined)}
          >
            {(id) => <Textarea id={id} rows={3} maxLength={1000} value={form.fallback_message} onChange={(e) => set("fallback_message", e.target.value)} />}
          </Field>
          <Field label={t.settings.rules} hint={t.settings.rulesHint} error={err("forbidden_rules")}>
            {(id) => (
              <Textarea
                id={id}
                rows={4}
                maxLength={4000}
                placeholder={t.settings.rulesPlaceholder}
                value={form.forbidden_rules}
                onChange={(e) => set("forbidden_rules", e.target.value)}
              />
            )}
          </Field>
          <Field
            label={t.settings.pauseMinutes}
            hint={t.settings.pauseMinutesHint}
            error={err("handoff_pause_minutes") ?? (pauseInvalid ? t.errors.field.handoff_pause_minutes : undefined)}
          >
            {(id) => (
              <div className="flex items-center gap-2">
                <Input
                  id={id}
                  type="number"
                  min={0}
                  max={10080}
                  step={1}
                  dir="ltr"
                  className="num w-32"
                  invalid={pauseInvalid}
                  value={Number.isNaN(form.handoff_pause_minutes) ? "" : form.handoff_pause_minutes}
                  onChange={(e) => set("handoff_pause_minutes", e.target.value === "" ? NaN : Number(e.target.value))}
                />
                <span className="text-sm text-slate-500">{t.settings.minutes}</span>
              </div>
            )}
          </Field>
        </div>
      </Card>

      <div className="sticky bottom-4 flex items-center justify-end gap-3">
        {dirty && <span className="rounded-md bg-white/90 px-2 py-1 text-sm text-amber-600">{t.common.unsavedChanges}</span>}
        <Button type="submit" loading={save.isPending} disabled={!dirty || invalid}>
          {t.common.save}
        </Button>
      </div>
    </form>
  );
}
