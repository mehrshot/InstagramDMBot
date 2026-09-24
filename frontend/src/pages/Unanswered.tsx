import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MessageSquare, Sparkles } from "lucide-react";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { Unanswered as Item } from "../api/types";
import { MessageText } from "../components/conversation";
import FaqDialog from "../components/FaqDialog";
import { useToast } from "../components/toast";
import { Alert, Button, Card, EmptyState, LinkButton, PageHeader, PageLoading } from "../components/ui";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";

export default function Unanswered() {
  const { t, f } = useI18n();
  const toast = useToast();
  const qc = useQueryClient();
  const [adding, setAdding] = useState<Item | null>(null);

  const list = useQuery({ queryKey: keys.unanswered, queryFn: () => api<Item[]>("/unanswered", { query: { limit: 200 } }) });

  const refresh = () => {
    qc.invalidateQueries({ queryKey: keys.unanswered });
    qc.invalidateQueries({ queryKey: keys.dashboard });
    qc.invalidateQueries({ queryKey: keys.conversations });
  };

  const resolveReq = (messageId: string) => api(`/unanswered/${messageId}/resolve`, { method: "POST" });

  const ignore = useMutation({
    mutationFn: resolveReq,
    onSuccess: () => {
      toast.success(t.unanswered.ignored);
      refresh();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (list.isPending) return <PageLoading />;
  if (list.error) return <Alert kind="error">{errorMessage(list.error, t)}</Alert>;

  return (
    <div className="space-y-6">
      <PageHeader title={t.unanswered.title} subtitle={t.unanswered.subtitle} />

      {list.data.length === 0 ? (
        <Card>
          <EmptyState icon={<Sparkles className="size-12" />} title={t.unanswered.empty} />
        </Card>
      ) : (
        <div className="space-y-3">
          {list.data.map((item) => (
            <Card key={item.message_id} className="p-4 sm:p-5">
              <div className="mb-2 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span dir="auto" className="font-medium text-slate-700">{item.customer_username ?? t.common.customer}</span>
                <span>·</span>
                <span title={f.dateTime(item.created_at)}>{f.ago(item.created_at)}</span>
              </div>
              <div className="user-text text-sm leading-7 text-slate-800">
                <MessageText text={item.question} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button size="sm" onClick={() => setAdding(item)}>
                  {t.unanswered.add}
                </Button>
                <LinkButton to={`/inbox/${item.conversation_id}`} size="sm" variant="secondary" icon={<MessageSquare className="size-4" />}>
                  {t.common.viewConversation}
                </LinkButton>
                <Button
                  size="sm"
                  variant="ghost"
                  loading={ignore.isPending && ignore.variables === item.message_id}
                  onClick={() => ignore.mutate(item.message_id)}
                >
                  {t.unanswered.ignore}
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}

      <FaqDialog
        question={adding?.question ?? null}
        onClose={() => setAdding(null)}
        onSaved={async () => {
          // saving the answer also closes the question
          if (adding) await resolveReq(adding.message_id);
          toast.success(t.unanswered.addedResolved);
          refresh();
        }}
      />
    </div>
  );
}
