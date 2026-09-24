import { useEffect } from "react";
import { useSearchParams } from "react-router";
import { useQueryClient } from "@tanstack/react-query";
import { CheckCircle2, XCircle } from "lucide-react";
import { keys } from "../api/queries";
import { Button, Card, LinkButton } from "../components/ui";
import { useI18n } from "../i18n";
import { useConnectInstagram } from "./Instagram";

// The backend redirects here after Instagram's permission screen:
// ?status=connected | denied | error (&reason=account_in_use | invalid_state | instagram | missing_code)

export default function InstagramCallback() {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const connect = useConnectInstagram();
  const status = params.get("status");
  const reason = params.get("reason");

  useEffect(() => {
    qc.invalidateQueries({ queryKey: keys.instagram });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  }, [qc]);

  const ok = status === "connected";
  let title: string;
  let hint: string | null = null;
  if (ok) {
    title = t.callback.connected;
    hint = t.callback.connectedHint;
  } else if (status === "denied") {
    title = t.callback.denied;
    hint = t.callback.deniedHint;
  } else if (reason === "account_in_use") {
    title = t.callback.accountInUse;
  } else if (reason === "invalid_state") {
    title = t.callback.invalidState;
  } else {
    title = t.callback.instagramError;
  }

  return (
    <div className="mx-auto max-w-md pt-10">
      <Card className="flex flex-col items-center p-8 text-center">
        {ok ? <CheckCircle2 className="mb-4 size-14 text-emerald-500" /> : <XCircle className="mb-4 size-14 text-red-500" />}
        <h1 className="text-xl font-bold text-slate-900">{title}</h1>
        {hint && <p className="mt-2 text-sm leading-7 text-slate-500">{hint}</p>}
        <div className="mt-6 flex flex-wrap justify-center gap-2">
          {ok ? (
            <LinkButton to="/knowledge">{t.callback.nextStep}</LinkButton>
          ) : (
            <>
              {reason !== "account_in_use" && (
                <Button onClick={() => connect.mutate()} loading={connect.isPending || connect.isSuccess}>
                  {t.callback.tryAgain}
                </Button>
              )}
              <LinkButton to="/instagram" variant="secondary">
                {t.callback.backToInstagram}
              </LinkButton>
            </>
          )}
        </div>
      </Card>
    </div>
  );
}
