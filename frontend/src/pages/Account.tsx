import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import { useMe } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import { useToast } from "../components/toast";
import { Alert, Button, Card, CardHeader, ConfirmDialog, Field, Input, Modal, PageHeader, PageLoading } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage, fieldError } from "../lib/errors";

export default function Account() {
  const { t, lang, setLang } = useI18n();
  const { data: me, isPending, error } = useMe();

  if (isPending) return <PageLoading />;
  if (error) return <Alert kind="error">{errorMessage(error, t)}</Alert>;

  return (
    <div className="max-w-2xl space-y-6">
      <PageHeader title={t.account.title} />

      <Card>
        <CardHeader title={t.account.info} />
        <dl className="grid gap-4 p-5 text-sm sm:grid-cols-3">
          <div>
            <dt className="text-slate-500">{t.account.email}</dt>
            <dd className="ltr mt-0.5 font-medium text-slate-900">{me.email}</dd>
          </div>
          {me.full_name && (
            <div>
              <dt className="text-slate-500">{t.account.name}</dt>
              <dd className="mt-0.5 font-medium text-slate-900">{me.full_name}</dd>
            </div>
          )}
          <div>
            <dt className="text-slate-500">{t.account.shop}</dt>
            <dd className="mt-0.5 font-medium text-slate-900">{me.shop.name}</dd>
          </div>
        </dl>
        <div className="flex items-center justify-between gap-3 border-t border-slate-100 px-5 py-4 text-sm">
          <span className="font-medium text-slate-700">{t.account.language}</span>
          <div className="flex gap-1 rounded-lg bg-slate-100 p-1">
            {(["fa", "en"] as const).map((l) => (
              <button
                key={l}
                type="button"
                onClick={() => setLang(l)}
                className={`rounded-md px-3 py-1 ${lang === l ? "bg-white shadow-sm" : "text-slate-600"}`}
              >
                {l === "fa" ? "فارسی" : "English"}
              </button>
            ))}
          </div>
        </div>
      </Card>

      <ChangePassword />
      <DeleteAccount />
    </div>
  );
}

function ChangePassword() {
  const { t } = useI18n();
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [repeat, setRepeat] = useState("");

  const change = useMutation({
    mutationFn: () => api("/me/password", { method: "POST", json: { current_password: current, new_password: next } }),
    onSuccess: () => {
      toast.success(t.account.passwordChanged);
      setCurrent("");
      setNext("");
      setRepeat("");
    },
  });

  const short = next.length > 0 && next.length < 8;
  const mismatch = repeat.length > 0 && repeat !== next;

  function submit(e: FormEvent) {
    e.preventDefault();
    if (!short && !mismatch && current && next === repeat) change.mutate();
  }

  const hasFieldErrors = change.error && fieldError(change.error, "new_password", t);

  return (
    <Card>
      <CardHeader title={t.account.changePassword} />
      <form onSubmit={submit} className="space-y-4 p-5" noValidate>
        {change.error && !hasFieldErrors && <Alert kind="error">{errorMessage(change.error, t)}</Alert>}
        <Field label={t.account.currentPassword}>
          {(id) => <Input id={id} type="password" dir="ltr" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label={t.account.newPassword} hint={t.auth.passwordHint} error={short ? t.errors.field.new_password : fieldError(change.error, "new_password", t)}>
            {(id) => (
              <Input id={id} type="password" dir="ltr" autoComplete="new-password" maxLength={128} invalid={short} value={next} onChange={(e) => setNext(e.target.value)} />
            )}
          </Field>
          <Field label={t.account.repeatPassword} error={mismatch ? t.account.passwordMismatch : undefined}>
            {(id) => (
              <Input id={id} type="password" dir="ltr" autoComplete="new-password" invalid={mismatch} value={repeat} onChange={(e) => setRepeat(e.target.value)} />
            )}
          </Field>
        </div>
        <div className="flex justify-end">
          <Button type="submit" loading={change.isPending} disabled={!current || next.length < 8 || next !== repeat}>
            {t.account.changePassword}
          </Button>
        </div>
      </form>
    </Card>
  );
}

/** Two-step confirmation: "are you sure?" then password + typed confirmation word. */
function DeleteAccount() {
  const { t } = useI18n();
  const { logout } = useAuth();
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [password, setPassword] = useState("");
  const [word, setWord] = useState("");

  const remove = useMutation({
    // DELETE with a JSON body (fine with fetch)
    mutationFn: () => api("/me", { method: "DELETE", json: { password } }),
    onSuccess: () => logout(),
  });

  const close = () => {
    setStep(0);
    setPassword("");
    setWord("");
    remove.reset();
  };

  const wordOk = word.trim().toLowerCase() === t.account.deleteWord.toLowerCase();

  return (
    <Card className="border-red-200">
      <CardHeader title={<span className="text-red-700">{t.account.deleteTitle}</span>} />
      <div className="space-y-4 p-5">
        <p className="text-sm leading-7 text-slate-600">{t.account.deleteDesc}</p>
        <Button variant="danger" onClick={() => setStep(1)}>
          {t.account.deleteButton}
        </Button>
      </div>

      <ConfirmDialog
        open={step === 1}
        onClose={close}
        onConfirm={() => setStep(2)}
        danger
        title={t.account.deleteStep1Title}
        body={t.account.deleteStep1Body}
        confirmLabel={t.account.deleteStep1Continue}
        cancelLabel={t.common.cancel}
      />

      <Modal
        open={step === 2}
        onClose={close}
        title={t.account.deleteStep2Title}
        footer={
          <>
            <Button variant="secondary" onClick={close}>
              {t.common.cancel}
            </Button>
            <Button variant="danger" loading={remove.isPending} disabled={!password || !wordOk} onClick={() => remove.mutate()}>
              {t.account.deleteFinal}
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-slate-600">{t.account.deleteStep2Body(t.account.deleteWord)}</p>
          {remove.error && <Alert kind="error">{errorMessage(remove.error, t)}</Alert>}
          <Field label={t.auth.password}>
            {(id) => <Input id={id} type="password" dir="ltr" autoComplete="current-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
          </Field>
          <Field label={t.account.deleteWordLabel}>{(id) => <Input id={id} value={word} onChange={(e) => setWord(e.target.value)} />}</Field>
        </div>
      </Modal>
    </Card>
  );
}
