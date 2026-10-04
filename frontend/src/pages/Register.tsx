import { useState, type ChangeEvent, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import AuthShell from "../components/AuthShell";
import { Alert, Button, Field, Input } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage, fieldError } from "../lib/errors";

export default function Register() {
  const { t } = useI18n();
  const { register } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "", full_name: "", shop_name: "" });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const set = (k: keyof typeof form) => (e: ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value });
  const tooShort = form.password.length > 0 && form.password.length < 8;

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (tooShort) return;
    setBusy(true);
    setError(null);
    try {
      await register({
        email: form.email.trim(),
        password: form.password,
        shop_name: form.shop_name.trim(),
        ...(form.full_name.trim() ? { full_name: form.full_name.trim() } : {}),
      });
      navigate("/", { replace: true });
    } catch (err) {
      setError(err);
      setBusy(false);
    }
  }

  const hasFieldErrors = error instanceof ApiError && Object.keys(error.fields).length > 0;

  return (
    <AuthShell
      title={t.auth.registerTitle}
      subtitle={t.auth.registerSubtitle}
      footer={
        <>
          {t.auth.haveAccount}{" "}
          <Link to="/login" className="font-medium text-brand-700 hover:underline">
            {t.auth.goLogin}
          </Link>
        </>
      }
    >
      <form onSubmit={submit} className="space-y-4" noValidate>
        {error != null && !hasFieldErrors && <Alert kind="error">{errorMessage(error, t)}</Alert>}
        <Field label={t.auth.shopName} hint={t.auth.shopNameHint} error={fieldError(error, "shop_name", t)}>
          {(id) => <Input id={id} required maxLength={120} value={form.shop_name} onChange={set("shop_name")} />}
        </Field>
        <Field
          label={
            <>
              {t.auth.fullName} <span className="font-normal text-slate-400">({t.common.optional})</span>
            </>
          }
        >
          {(id) => <Input id={id} autoComplete="name" maxLength={120} value={form.full_name} onChange={set("full_name")} />}
        </Field>
        <Field label={t.auth.email} error={fieldError(error, "email", t)}>
          {(id) => <Input id={id} type="email" dir="ltr" autoComplete="email" required value={form.email} onChange={set("email")} />}
        </Field>
        <Field label={t.auth.password} hint={t.auth.passwordHint} error={tooShort ? t.errors.field.password : fieldError(error, "password", t)}>
          {(id) => (
            <Input
              id={id}
              type="password"
              dir="ltr"
              autoComplete="new-password"
              required
              maxLength={128}
              invalid={tooShort}
              value={form.password}
              onChange={set("password")}
            />
          )}
        </Field>
        <Button type="submit" loading={busy} className="w-full" disabled={!form.email || !form.shop_name.trim() || form.password.length < 8}>
          {t.auth.register}
        </Button>
        <p className="text-center text-xs leading-6 text-slate-500">
          {t.launch.signupTerms.before}
          <Link to="/terms" className="font-medium text-brand-700 hover:underline">
            {t.launch.signupTerms.terms}
          </Link>
          {t.launch.signupTerms.and}
          <Link to="/privacy" className="font-medium text-brand-700 hover:underline">
            {t.launch.signupTerms.privacy}
          </Link>
          {t.launch.signupTerms.after}
        </p>
      </form>
    </AuthShell>
  );
}
