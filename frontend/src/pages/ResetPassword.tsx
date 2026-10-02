import { useState, type FormEvent } from "react";
import { Link, useSearchParams } from "react-router";
import { api } from "../api/client";
import AuthShell from "../components/AuthShell";
import { Alert, Button, Field, Input, LinkButton } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage, fieldError } from "../lib/errors";

/** The page behind the emailed link: /reset-password?token=… */
export default function ResetPassword() {
  const { t } = useI18n();
  const P = t.launch.password;
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [password, setPassword] = useState("");
  const [repeat, setRepeat] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [done, setDone] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (password !== repeat) return;
    setBusy(true);
    setError(null);
    try {
      await api("/auth/password/reset", { method: "POST", json: { token, new_password: password }, auth: false });
      setDone(true);
    } catch (err) {
      setError(err);
    } finally {
      setBusy(false);
    }
  }

  const footer = (
    <Link to="/login" className="font-medium text-brand-700 hover:underline">
      {P.backToLogin}
    </Link>
  );

  if (!token)
    return (
      <AuthShell title={P.resetTitle} subtitle="" footer={footer}>
        <Alert kind="error">{P.noToken}</Alert>
      </AuthShell>
    );

  if (done)
    return (
      <AuthShell title={P.resetTitle} subtitle="" footer={null}>
        <Alert kind="success">{P.done}</Alert>
        <LinkButton to="/login" className="mt-4 w-full">
          {t.auth.login}
        </LinkButton>
      </AuthShell>
    );

  const mismatch = repeat.length > 0 && password !== repeat;
  return (
    <AuthShell title={P.resetTitle} subtitle={P.resetSubtitle} footer={footer}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error != null && !fieldError(error, "new_password", t) && <Alert kind="error">{errorMessage(error, t)}</Alert>}
        <Field label={P.newPassword} hint={t.auth.passwordHint} error={fieldError(error, "new_password", t)}>
          {(id) => <Input id={id} type="password" dir="ltr" autoComplete="new-password" value={password} onChange={(e) => setPassword(e.target.value)} />}
        </Field>
        <Field label={P.repeat} error={mismatch ? P.mismatch : undefined}>
          {(id) => <Input id={id} type="password" dir="ltr" autoComplete="new-password" value={repeat} invalid={mismatch} onChange={(e) => setRepeat(e.target.value)} />}
        </Field>
        <Button type="submit" loading={busy} className="w-full" disabled={password.length < 8 || password !== repeat}>
          {P.save}
        </Button>
      </form>
    </AuthShell>
  );
}
