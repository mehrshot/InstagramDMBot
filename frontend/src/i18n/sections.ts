import type { Section } from "../api/types";
import type { Lang } from ".";

// Section labels come from the API in Persian (docs/FRONTEND.md §4.3). For the English
// panel (Meta's reviewers) we swap in translations; unknown keys fall back to the API text.
const en: Record<string, Pick<Section, "label" | "hint" | "placeholder">> = {
  about: {
    label: "About the shop",
    hint: "What does your shop sell, and what should customers know about it?",
    placeholder: "e.g. Mahsa Boutique, making women's coats and blouses since 2019. Everything is sewn in-house.",
  },
  shipping: {
    label: "Shipping",
    hint: "Shipping methods, cost, delivery time, other cities and abroad",
    placeholder: "e.g. Express post, 3–5 business days, 85,000 Toman. Free over 2 million.",
  },
  payment: {
    label: "Payment",
    hint: "Payment methods and how to place an order",
    placeholder: "e.g. Card transfer or website checkout. Cash on delivery in Tehran only.",
  },
  returns: {
    label: "Returns & exchanges",
    hint: "Return or exchange conditions and deadline",
    placeholder: "e.g. Size exchanges within 7 days of delivery if unworn with tags.",
  },
  contact: {
    label: "Contact & opening hours",
    hint: "Website, phone, address, support hours",
    placeholder: "e.g. mahsa.shop, support 10am–8pm, closed Fridays.",
  },
  faq: {
    label: "Frequently asked questions",
    hint: "Questions customers often ask, with the answers",
    placeholder: "Question: What's the fabric? / Answer: Premium Turkish linen",
  },
  free_text: {
    label: "Other information",
    hint: "Anything else the bot should know",
    placeholder: "e.g. 15% off your first order with code FIRST15",
  },
  file: {
    label: "Uploaded files",
    hint: "Text extracted from your files. You can edit it.",
    placeholder: "",
  },
};

export function localizeSection(section: Section, lang: Lang): Section {
  const tr = lang === "en" ? en[section.key] : undefined;
  return tr ? { ...section, ...tr } : section;
}
