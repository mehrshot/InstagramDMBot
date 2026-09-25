// Short names for the generated API types (regenerate with `npm run gen:api`).
import type { components } from "./schema";

type S = components["schemas"];

export type User = S["UserOut"];
export type Shop = S["ShopOut"];
export type ShopUpdate = S["ShopUpdate"];
export type Dashboard = S["DashboardOut"];
export type SetupStatus = S["SetupStatus"];
export type InstagramStatus = S["InstagramStatusOut"];
export type KnowledgeSection = S["KnowledgeSection"];
export type Section = S["SectionOut"];
export type Sections = S["SectionsOut"];
export type Knowledge = S["KnowledgeOut"];
export type Entry = S["EntryOut"];
export type EntryCreate = S["EntryCreate"];
export type ProductField = S["FieldOut"];
export type Preview = S["PreviewOut"];
export type Source = S["SourceOut"];
export type Product = S["ProductOut"];
export type ProductPage = S["ProductPage"];
export type Conversation = S["ConversationOut"];
export type ConversationDetail = S["ConversationDetail"];
export type ConversationPage = S["ConversationPage"];
export type Message = S["MessageOut"];
export type Handoff = S["HandoffOut"];
export type HandoffItem = S["HandoffItem"];
export type HandoffPage = S["HandoffPage"];
export type Unanswered = S["UnansweredOut"];
export type PlaygroundTurn = S["PlaygroundTurn"];
export type PlaygroundReply = S["PlaygroundOut"];
export type Posts = S["PostsOut"];

export type ConversationFilter = "all" | "needs_owner" | "unanswered" | "paused";
