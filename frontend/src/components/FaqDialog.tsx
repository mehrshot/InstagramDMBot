import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "../api/client";
import { keys } from "../api/queries";
import type { Entry, EntryCreate } from "../api/types";
import { useI18n } from "../i18n";
import { errorMessage } from "../lib/errors";
import { Alert, Button, Field, Modal, Textarea } from "./ui";

/**
 * "Add to bot knowledge": a FAQ form pre-filled with the customer's question.
 * Used from the handoffs and unanswered pages.
 */
export default function FaqDialog({
  question,
  onClose,
  onSaved,
}: {
  /** null = closed */
  question: string | null;
  onClose: () => void;
  onSaved?: (entry: Entry) => Promise<unknown> | void;
}) {
  const { t } = useI18n();
  const qc = useQueryClient();
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");

  const save = useMutation({
    mutationFn: async () => {
      const body: EntryCreate = { section: "faq", title: title.trim(), content: content.trim() };
      const entry = await api<Entry>("/knowledge", { method: "POST", json: body });
      await onSaved?.(entry);
      return entry;
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["knowledge"] });
      qc.invalidateQueries({ queryKey: keys.dashboard });
      onClose();
    },
  });

  const { reset } = save;
  useEffect(() => {
    if (question !== null) {
      setTitle(question.trim().slice(0, 255)); // API limit for titles
      setContent("");
      reset();
    }
  }, [question, reset]);

  return (
    <Modal
      open={question !== null}
      onClose={onClose}
      title={t.knowledge.faqFormTitle}
      size="lg"
      footer={
        <>
          <Button variant="secondary" onClick={onClose}>
            {t.common.cancel}
          </Button>
          <Button onClick={() => save.mutate()} loading={save.isPending} disabled={!content.trim()}>
            {t.common.save}
          </Button>
        </>
      }
    >
      <div className="space-y-4">
        <p className="text-sm text-slate-500">{t.knowledge.faqFormHint}</p>
        {save.error && <Alert kind="error">{errorMessage(save.error, t)}</Alert>}
        <Field label={t.knowledge.faqQuestion}>{(id) => <Textarea id={id} rows={2} maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
        <Field label={t.knowledge.faqAnswer}>
          {(id) => <Textarea id={id} rows={5} data-autofocus value={content} onChange={(e) => setContent(e.target.value)} />}
        </Field>
      </div>
    </Modal>
  );
}
