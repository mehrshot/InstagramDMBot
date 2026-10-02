import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api } from "../api/client";
import AuthShell from "../components/AuthShell";
import { Alert, Button, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage, fieldError } from "../lib/errors";

export default function ForgotPassword() {
  const { t } = useI18n();
  const P = t.launch.password;
  const [email, setEmail] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [sent, setSent] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const res = await api<{ message: string }>("/auth/password/forgot", { method: "POST", json: { email: email.trim() }, auth: false });
      setSent(res.message);
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

  if (sent)
    return (
      <AuthShell title={P.sentTitle} subtitle="" footer={footer}>
        <Alert kind="success">{sent}</Alert>
      </AuthShell>
    );

  return (
    <AuthShell title={P.forgotTitle} subtitle={P.forgotSubtitle} footer={footer}>
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error != null && !fieldError(error, "email", t) && <Alert kind="error">{errorMessage(error, t)}</Alert>}
        <Field label={t.auth.email} error={fieldError(error, "email", t)}>
          {(id) => <Input id={id} type="email" dir="ltr" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />}
        </Field>
        <Button type="submit" loading={busy} className="w-full" disabled={!email.includes("@")}>
          {P.send}
        </Button>
      </form>
    </AuthShell>
  );
}
