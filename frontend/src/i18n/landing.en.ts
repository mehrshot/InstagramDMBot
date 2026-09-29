import type { Dict } from "./fa";

const landing: Dict["landing"] = {
  meta: {
    title: "Javab — AI assistant for Instagram DMs",
    description: "Javab answers your shop's Instagram DMs around the clock using your own shop info and products, and hands the conversation to you whenever it should.",
  },

  nav: {
    features: "Features",
    how: "Setup",
    trust: "Security",
    faq: "FAQ",
    login: "Log in",
    start: "Create account",
    openPanel: "Open panel",
    menu: "Open menu",
    closeMenu: "Close menu",
    main: "Main navigation",
    home: "Javab home",
    skip: "Skip to main content",
  },

  hero: {
    eyebrow: "AI assistant for Instagram DMs",
    titleBefore: "No DM goes ",
    titleMark: "unanswered",
    titleAfter: ".",
    lead: "Javab answers your customers' DMs day and night using your own shop info and products: prices, stock, shipping. When it doesn't know the answer, it hands the conversation to you.",
    primary: "Create account",
    secondary: "See how it works",
    points: ["Set up in minutes", "Try it yourself first", "Turn it off any time"],
  },

  chat: {
    label: "An example DM conversation",
    example: "Example",
    shop: "Your shop's DMs",
    customer: "neda_k",
    botOn: "Bot on",
    auto: "Auto-reply by Javab",
    typing: "Javab is typing",
    m1: "Hi, do you have the black linen coat in size 44?",
    m2: "Hi! Yes, it's in stock. There are 2 left in black, size 44, and it's 1,250,000 toman.",
    lookup: "Stock checked in your product list",
    postTitle: "Instagram post",
    postCaption: "Summer linen coat, in 4 colours",
    m3: "How long does shipping to Shiraz take?",
    m4: "Express post takes 3 to 5 working days, and shipping is 85,000 toman.",
    m5: "Can you issue an official invoice for a company?",
    m6: "Let me check that with my colleague — we'll reply right here.",
    handedOff: "Handed to you",
    notifyWaiting: "is waiting for your reply",
    notifyBody: "Can you issue an official invoice for a company?",
    replay: "Replay conversation",
  },

  problem: {
    eyebrow: "Why Javab",
    title: "Most DMs are the same few questions",
    lead: "Price, size, stock, shipping cost, payment. Customers want the answer now, even at 2 a.m. — and a DM left unanswered is usually a sale that doesn't happen.",
    inboxTitle: "Last night's DMs",
    unread: "Unread",
    answered: "Answered",
    questions: [
      { q: "How much is this one?", time: "01:12" },
      { q: "Do you have it in size 46?", time: "01:40" },
      { q: "How many days to Mashhad?", time: "02:05" },
      { q: "Can I pay by card transfer?", time: "02:31" },
      { q: "Can I exchange it if it doesn't fit?", time: "03:18" },
    ],
    points: [
      { title: "Replies in seconds, around the clock", body: "Every customer message is answered right away — at night, on holidays, or in the middle of a rush." },
      { title: "Only from your own information", body: "The bot doesn't make things up. Answers come from your shop info and your product list." },
      { title: "When it doesn't know, it doesn't guess", body: "A question your info doesn't cover is handed to you instead of getting a wrong answer." },
    ],
  },

  features: {
    eyebrow: "Features",
    title: "A careful colleague for your DMs",
    lead: "Javab does what you do in the DMs, with the same information you have.",
    knowledge: {
      title: "Answers with your own shop info",
      body: "Write down shipping, payment, returns and FAQs once, or upload a PDF, Word file or photo of them. The bot answers only from this information.",
      bullets: [
        "Text in files and photos is extracted automatically, and you can edit it",
        "Questions the bot couldn't answer are collected so you can add the answer in one click",
      ],
    },
    products: {
      title: "Prices and stock, always current",
      body: "Connect your product list from Google Sheets or an Excel file. Before every answer, the bot checks price and stock in that list.",
      bullets: [
        "Google Sheets syncs automatically every 5 minutes",
        "If a colour or size is sold out, it suggests the variants still in stock",
        "It also sends the customer that product's Instagram post",
      ],
    },
    handoff: {
      title: "Hands the conversation to you when it should",
      body: "A question your info doesn't cover gets a polite holding reply and is handed to you, shown above everything else in your panel.",
      bullets: [
        "Browser notification and a count in the tab title",
        "Replying in Instagram closes the handoff automatically",
        "When you reply yourself, the bot stays quiet for that customer",
      ],
    },
    control: {
      title: "Your tone, your rules",
      body: "Friendly or formal, with or without emoji. Write rules the bot must never break, and pause it for any single customer whenever you like.",
      bullets: ["Before turning it on, ask questions as a customer on the test page", "Turn the bot on or off for everyone with one switch"],
    },
  },

  demos: {
    knowledge: {
      title: "Shop info",
      sections: [
        { label: "Shipping", text: "Express post, 3–5 working days; same-day courier in Tehran" },
        { label: "Payment", text: "Card transfer or online payment gateway" },
        { label: "Returns", text: "Within 7 days, with the tag intact" },
      ],
      file: "shipping-terms.pdf",
      fileStatus: "Text extracted from file",
      usage: "Info used",
      usageValue: "24%",
    },
    products: {
      title: "Stock check",
      query: "Search",
      chips: ["Linen coat", "Black", "46"],
      name: "Linen coat · Black · 46",
      out: "Sold out",
      others: "Variants of this product in stock",
      variants: [
        { label: "Navy · 46", stock: "× 2" },
        { label: "Black · 44", stock: "× 2" },
      ],
      price: "1,250,000 toman",
      source: "Google Sheets · synced 3 minutes ago",
    },
    handoff: {
      title: "Handed to you",
      waiting: "Waiting for 14 minutes",
      question: "Customer's question",
      questionText: "Can you issue an official invoice for a company?",
      reason: "Why it was handed over",
      reasonText: "The customer wants an official invoice, and that isn't in the bot's info.",
      reply: "Reply in Instagram",
      resolve: "Close",
      tabCount: "(1) Your shop panel",
    },
    tone: {
      title: "Bot tone",
      tryIt: "Try it",
      friendly: "Friendly",
      formal: "Formal",
      emoji: "Emoji",
      question: "Does this bag come in cream?",
      replies: {
        friendly: "Hi there! Yes, we have it in cream too! It's 890,000 toman.",
        friendlyEmoji: "Hi there! Yes, we have it in cream too! 😍 It's 890,000 toman.",
        formal: "Hello. Yes, this bag is also available in cream. The price is 890,000 toman.",
        formalEmoji: "Hello. Yes, this bag is also available in cream 🙂 The price is 890,000 toman.",
      },
      rules: "Bot rules",
      rulesText: "Never offer discounts. Don't talk about competitors.",
    },
  },

  how: {
    eyebrow: "Setup",
    title: "From sign-up to first reply in four steps",
    lead: "Nothing to install and no technical knowledge needed — it all happens in the panel.",
    steps: [
      { title: "Connect Instagram", body: "Connect your professional account (Business or Creator) through Instagram's official flow. No page password needed." },
      { title: "Info and products", body: "Enter shipping, payment, returns and FAQs, and connect your product list." },
      { title: "Test the bot", body: "Ask questions as a customer on the test page and see the replies. Nothing is sent to anyone." },
      { title: "Turn it on", body: "Flip one switch. From then on, DMs get answered and you only see the ones handed to you." },
    ],
  },

  trust: {
    eyebrow: "Security & control",
    title: "Your account, your rules, your data",
    lead: "Javab is built so the shop owner always stays in control.",
    items: [
      { title: "Official Instagram connection", body: "You connect through Meta's official flow. We never ask for your page password." },
      { title: "Encrypted access", body: "Instagram access tokens are stored encrypted, and your password only as a hash." },
      { title: "Your data isn't sold", body: "We don't use your data for advertising or to train models, and we don't sell it to anyone." },
      { title: "Full deletion, any time", body: "Deleting your account permanently removes conversations, info, products and the Instagram connection." },
    ],
    privacyLink: "Privacy policy",
  },

  faq: {
    eyebrow: "FAQ",
    title: "Before you start, you might ask",
    items: [
      {
        q: "Do you need my Instagram password to connect?",
        a: "No. You connect through Instagram's official page and grant message access yourself. You can revoke it any time from the panel or from Instagram's settings.",
      },
      {
        q: "Which accounts can connect?",
        a: "The account must be professional (Business or Creator), with “Allow access to messages” turned on in Instagram's message settings.",
      },
      {
        q: "What happens when the bot doesn't know an answer?",
        a: "It doesn't guess. It tells the customer their question is being followed up, hands the conversation to you, and lets you know in the panel and with a browser notification.",
      },
      {
        q: "Can I still reply in the DMs myself?",
        a: "Yes. Whenever you reply from Instagram, the bot stays quiet for that customer for a while — you choose how long. You can also pause the bot completely for any customer.",
      },
      {
        q: "How do I add my products?",
        a: "Connect a Google Sheets link or an Excel/CSV file and say what each column holds. Google Sheets syncs automatically every 5 minutes. There's a ready-made template in the panel.",
      },
      {
        q: "Does it reply to comments too?",
        a: "Not yet. Javab works on Instagram Direct Messages.",
      },
    ],
  },

  cta: {
    title: "Let Javab take tonight's DMs",
    lead: "Create an account, add your shop info, and try the bot yourself before you turn it on.",
    primary: "Create account",
    secondary: "Log in to the panel",
  },

  footer: {
    about: "AI assistant for the DMs of Instagram shops.",
    product: "Product",
    account: "Account",
    legal: "Legal",
    support: "Support",
    rights: (year) => `© ${year} Javab`,
  },
};

export default landing;
