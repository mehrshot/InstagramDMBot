import { useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FileText, Pencil, Plus, Trash2, Upload } from "lucide-react";
import { api } from "../api/client";
import { keys, useSections } from "../api/queries";
import type { Entry, Knowledge as KnowledgeData, KnowledgeSection, Section } from "../api/types";
import { useToast } from "../components/toast";
import { Alert, Button, Card, ConfirmDialog, EmptyState, Field, Input, PageHeader, PageLoading, ProgressBar, Textarea } from "../components/ui";
import { useI18n } from "../i18n";
import { localizeSection } from "../i18n/sections";
import { errorMessage } from "../lib/errors";
import { formatBytesMB } from "../lib/format";

function useInvalidateKnowledge() {
  const qc = useQueryClient();
  return () => {
    qc.invalidateQueries({ queryKey: keys.knowledge });
    qc.invalidateQueries({ queryKey: keys.dashboard });
  };
}

export default function Knowledge() {
  const { t, f, lang } = useI18n();
  const sections = useSections();
  const knowledge = useQuery({ queryKey: keys.knowledge, queryFn: () => api<KnowledgeData>("/knowledge") });

  if (sections.isPending || knowledge.isPending) return <PageLoading />;
  if (sections.error || knowledge.error) return <Alert kind="error">{errorMessage(sections.error ?? knowledge.error, t)}</Alert>;

  const { chars_used, char_limit } = knowledge.data;
  const full = chars_used >= char_limit;
  const bySection = (key: KnowledgeSection) => knowledge.data.entries.filter((e) => e.section === key);

  return (
    <div className="space-y-6">
      <PageHeader title={t.knowledge.title} subtitle={t.knowledge.subtitle} />

      <Card className="p-5">
        <div className="mb-2 flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">{t.knowledge.usage}</span>
          <span className="num text-slate-500">
            {f.num(chars_used)} / {f.num(char_limit)} {t.knowledge.chars}
          </span>
        </div>
        <ProgressBar value={chars_used} max={char_limit} />
        {full && <p className="mt-2 text-sm text-red-600">{t.knowledge.usageFull}</p>}
      </Card>

      {sections.data.sections.map((raw) => {
        const section = localizeSection(raw, lang);
        const entries = bySection(section.key);
        if (!section.multiple) return <SingleSection key={section.key} section={section} entry={entries[0]} />;
        if (section.key === "file")
          return (
            <FileSection
              key={section.key}
              section={section}
              entries={entries}
              types={sections.data.supported_file_types}
              maxBytes={sections.data.max_file_bytes}
            />
          );
        return <MultiSection key={section.key} section={section} entries={entries} />;
      })}
    </div>
  );
}

function SectionCard({ section, children, action }: { section: Section; children: React.ReactNode; action?: React.ReactNode }) {
  return (
    <Card>
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-100 px-5 py-4">
        <div className="min-w-0">
          <h2 className="font-semibold text-slate-900">{section.label}</h2>
          <p className="mt-0.5 text-sm text-slate-500">{section.hint}</p>
        </div>
        {action}
      </div>
      <div className="p-5">{children}</div>
    </Card>
  );
}

/** One text box per section: about, shipping, payment, returns, contact. */
function SingleSection({ section, entry }: { section: Section; entry: Entry | undefined }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const invalidate = useInvalidateKnowledge();
  const saved = entry?.content ?? "";
  const [text, setText] = useState(saved);
  const dirty = text.trim() !== saved.trim();

  // pick up the server value when it changes and the user isn't mid-edit
  const lastSaved = useRef(saved);
  useEffect(() => {
    if (lastSaved.current !== saved) {
      lastSaved.current = saved;
      setText(saved);
    }
  }, [saved]);

  const save = useMutation({
    mutationFn: () => api<Entry | null>(`/knowledge/single/${section.key}`, { method: "PUT", json: { content: text } }),
    onSuccess: () => {
      toast.success(t.common.saved);
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  return (
    <SectionCard section={section}>
      <Textarea rows={4} value={text} placeholder={section.placeholder} onChange={(e) => setText(e.target.value)} aria-label={section.label} />
      <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
        <span className="text-xs text-slate-400">
          <span className="num">{f.num(text.length)}</span> {t.knowledge.chars}
          {dirty && saved && !text.trim() && <span className="ms-2 text-amber-600">· {t.knowledge.singleEmpty}</span>}
        </span>
        <div className="flex items-center gap-2">
          {dirty && <span className="text-xs text-amber-600">{t.common.unsavedChanges}</span>}
          <Button size="sm" onClick={() => save.mutate()} loading={save.isPending} disabled={!dirty}>
            {t.common.save}
          </Button>
        </div>
      </div>
    </SectionCard>
  );
}

/** List of cards: faq (question/answer) and free_text. */
function MultiSection({ section, entries }: { section: Section; entries: Entry[] }) {
  const { t } = useI18n();
  const [adding, setAdding] = useState(false);
  const isFaq = section.key === "faq";

  return (
    <SectionCard
      section={section}
      action={
        !adding && (
          <Button size="sm" variant="soft" icon={<Plus className="size-4" />} onClick={() => setAdding(true)}>
            {isFaq ? t.knowledge.addFaq : t.knowledge.addItem}
          </Button>
        )
      }
    >
      <div className="space-y-3">
        {adding && <EntryEditor section={section} onDone={() => setAdding(false)} />}
        {entries.map((e) => (
          <EntryCard key={e.id} section={section} entry={e} />
        ))}
        {!adding && entries.length === 0 && <p className="text-sm text-slate-400">{t.knowledge.noItems}</p>}
      </div>
    </SectionCard>
  );
}

function FileSection({ section, entries, types, maxBytes }: { section: Section; entries: Entry[]; types: string[]; maxBytes: number }) {
  const { t, f } = useI18n();
  const toast = useToast();
  const invalidate = useInvalidateKnowledge();
  const input = useRef<HTMLInputElement>(null);
  const [fresh, setFresh] = useState<string | null>(null);

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("file", file);
      return api<Entry>("/knowledge/upload", { method: "POST", form });
    },
    onSuccess: (entry) => {
      setFresh(entry.id);
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  function pick(file: File | undefined) {
    if (input.current) input.current.value = "";
    if (!file) return;
    const ext = "." + (file.name.split(".").pop() ?? "").toLowerCase();
    if (!types.includes(ext)) return toast.error(t.errors.fileType);
    if (file.size > maxBytes) return toast.error(t.errors.fileTooBig(f.num(formatBytesMB(maxBytes))));
    upload.mutate(file);
  }

  return (
    <SectionCard
      section={section}
      action={
        <>
          <input ref={input} type="file" className="hidden" accept={types.join(",")} onChange={(e) => pick(e.target.files?.[0])} />
          <Button size="sm" variant="soft" icon={<Upload className="size-4" />} loading={upload.isPending} onClick={() => input.current?.click()}>
            {t.knowledge.upload}
          </Button>
        </>
      }
    >
      <p className="mb-3 text-xs text-slate-400" dir="auto">
        {t.knowledge.uploadHint(types.join(" "), f.num(formatBytesMB(maxBytes)))}
      </p>
      {upload.isPending && <Alert kind="info" className="mb-3">{t.knowledge.uploading}</Alert>}
      <div className="space-y-3">
        {entries.map((e) => (
          <EntryCard key={e.id} section={section} entry={e} startEditing={e.id === fresh} onEditEnd={() => setFresh(null)} />
        ))}
        {entries.length === 0 && !upload.isPending && (
          <EmptyState icon={<FileText className="size-10" />} title={t.knowledge.noItems} />
        )}
      </div>
    </SectionCard>
  );
}

function EntryCard({
  section,
  entry,
  startEditing = false,
  onEditEnd,
}: {
  section: Section;
  entry: Entry;
  startEditing?: boolean;
  onEditEnd?: () => void;
}) {
  const { t } = useI18n();
  const toast = useToast();
  const invalidate = useInvalidateKnowledge();
  const [editing, setEditing] = useState(startEditing);
  const [confirm, setConfirm] = useState(false);

  useEffect(() => {
    if (startEditing) setEditing(true);
  }, [startEditing]);

  const remove = useMutation({
    mutationFn: () => api(`/knowledge/${entry.id}`, { method: "DELETE" }),
    onSuccess: () => {
      setConfirm(false);
      toast.success(t.knowledge.deleted);
      invalidate();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  if (editing)
    return (
      <EntryEditor
        section={section}
        entry={entry}
        review={startEditing}
        onDone={() => {
          setEditing(false);
          onEditEnd?.();
        }}
      />
    );

  return (
    <div className="group rounded-lg border border-slate-200 p-4">
      <div className="flex items-start gap-3">
        <div className="min-w-0 flex-1">
          {entry.source_filename && (
            <div className="mb-1 inline-flex items-center gap-1 text-xs text-slate-400">
              <FileText className="size-3.5" />
              <span dir="auto">{entry.source_filename}</span>
            </div>
          )}
          {entry.title && <div className="user-text mb-1 font-medium text-slate-900">{entry.title}</div>}
          <div className="user-text line-clamp-6 text-sm leading-7 text-slate-600">{entry.content}</div>
        </div>
        <div className="flex shrink-0 gap-1">
          <button type="button" onClick={() => setEditing(true)} className="rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700" title={t.common.edit}>
            <Pencil className="size-4" />
          </button>
          <button type="button" onClick={() => setConfirm(true)} className="rounded-md p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600" title={t.common.delete}>
            <Trash2 className="size-4" />
          </button>
        </div>
      </div>
      <ConfirmDialog
        open={confirm}
        onClose={() => setConfirm(false)}
        onConfirm={() => remove.mutate()}
        loading={remove.isPending}
        danger
        title={t.knowledge.deleteConfirmTitle}
        body={t.knowledge.deleteConfirmBody}
        confirmLabel={t.common.delete}
        cancelLabel={t.common.cancel}
      />
    </div>
  );
}

/** Create (no `entry`) or edit an entry of a multiple section. */
function EntryEditor({ section, entry, review, onDone }: { section: Section; entry?: Entry; review?: boolean; onDone: () => void }) {
  const { t } = useI18n();
  const toast = useToast();
  const invalidate = useInvalidateKnowledge();
  const isFaq = section.key === "faq";
  const [title, setTitle] = useState(entry?.title ?? "");
  const [content, setContent] = useState(entry?.content ?? "");

  const save = useMutation({
    mutationFn: () =>
      entry
        ? api<Entry>(`/knowledge/${entry.id}`, { method: "PATCH", json: { title: title.trim(), content } })
        : api<Entry>("/knowledge", { method: "POST", json: { section: section.key, title: title.trim(), content } }),
    onSuccess: () => {
      toast.success(t.common.saved);
      invalidate();
      onDone();
    },
    onError: (err) => toast.error(errorMessage(err, t)),
  });

  const canSave = content.trim().length > 0 && (!isFaq || title.trim().length > 0);

  return (
    <div className="space-y-3 rounded-lg border border-brand-200 bg-brand-50/40 p-4">
      {review && <Alert kind="info">{t.knowledge.uploadedReview}</Alert>}
      <Field label={isFaq ? t.knowledge.faqQuestion : t.knowledge.itemTitle}>
        {(id) => <Input id={id} maxLength={255} value={title} onChange={(e) => setTitle(e.target.value)} autoFocus={!entry} />}
      </Field>
      <Field label={isFaq ? t.knowledge.faqAnswer : t.knowledge.itemContent}>
        {(id) => (
          <Textarea
            id={id}
            rows={review ? 12 : 4}
            value={content}
            placeholder={entry ? undefined : section.placeholder}
            onChange={(e) => setContent(e.target.value)}
          />
        )}
      </Field>
      <div className="flex justify-end gap-2">
        <Button size="sm" variant="secondary" onClick={onDone}>
          {t.common.cancel}
        </Button>
        <Button size="sm" onClick={() => save.mutate()} loading={save.isPending} disabled={!canSave}>
          {t.common.save}
        </Button>
      </div>
    </div>
  );
}
