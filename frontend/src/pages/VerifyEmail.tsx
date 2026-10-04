import { useEffect, useRef } from "react";
import { Link, useSearchParams } from "react-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { keys } from "../api/queries";
import { useAuth } from "../auth/AuthContext";
import AuthShell from "../components/AuthShell";
import { Alert, LinkButton, Spinner } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

/** The page behind the emailed link: /verify-email?token=… (works logged in or out). */
export default function VerifyEmail() {
  const { t } = useI18n();
  const V = t.launch.verify;
  const { loggedIn } = useAuth();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const sent = useRef(false);

  const verify = useMutation({
    mutationFn: () => api("/auth/email/verify", { method: "POST", json: { token }, auth: false }),
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.me }),
  });

  useEffect(() => {
    // Once, even under StrictMode's double effects.
    if (token && !sent.current) {
      sent.current = true;
      verify.mutate();
    }
  }, [token, verify]);

  const next = loggedIn ? (
    <LinkButton to="/" className="mt-4 w-full">
      {V.toPanel}
    </LinkButton>
  ) : (
    <LinkButton to="/login" className="mt-4 w-full">
      {t.auth.login}
    </LinkButton>
  );
  const footer = (
    <Link to="/" className="font-medium text-brand-700 hover:underline">
      {V.toPanel}
    </Link>
  );

  return (
    <AuthShell title={V.pageTitle} subtitle="" footer={verify.isSuccess ? null : footer}>
      {!token ? (
        <Alert kind="error">{V.noToken}</Alert>
      ) : verify.isSuccess ? (
        <>
          <Alert kind="success">{V.done}</Alert>
          {next}
        </>
      ) : verify.isError ? (
        <Alert kind="error">{errorMessage(verify.error, t)}</Alert>
      ) : (
        <div className="flex items-center gap-3 text-sm text-slate-500">
          <Spinner className="size-5" />
          {V.checking}
        </div>
      )}
    </AuthShell>
  );
}
