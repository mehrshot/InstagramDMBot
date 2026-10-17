import type { Dict } from "./fa";

const landing: Dict["landing"] = {
  meta: {
    title: "Javab — AI agent for your business",
    description: "Javab is an AI agent for your business: it talks to your customers using your own info and products, helps with sales and support, and works on your messaging channels.",
  },

  nav: {
    roles: "Capabilities",
    channels: "Channels",
    how: "Setup",
    ask: "Ask",
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
    eyebrow: "AI agent for businesses",
    titleBefore: "An AI ",
    titleMark: "teammate",
    titleAfter: " for your business",
    lead: "Javab talks to your customers using your own info and products: it answers questions, guides purchases and keeps requests on track. When it should, it hands the conversation to you.",
    primary: "Create account",
    secondary: "See what it does",
    rolesLabel: "Javab's roles",
    roles: ["Sales", "Support", "Advisor", "Assistant", "Follow-up"],
    channelsLabel: "On your channels",
  },

  chat: {
    label: "An example sales conversation",
    example: "Example",
    shop: "Customer conversation",
    customer: "neda_k",
    botOn: "Javab is on",
    auto: "Auto-reply by Javab",
    typing: "Javab is typing",
    m1: "Hi, do you have the black linen coat in size 44?",
    m2: "Hi! Yes, it's in stock. There are 2 left in black, size 44, and it's 1,250,000 toman.",
    lookup: "Stock checked in your product list",
    postTitle: "Product card",
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

  roles: {
    eyebrow: "Capabilities",
    title: "One teammate, several roles",
    lead: "Javab works the way your business needs it to — from sales and support to guidance and follow-up.",
    items: [
      { title: "Sales", body: "Answers buyers' questions about products, prices and stock, and stays with them until they decide." },
      { title: "Support", body: "Handles customers' everyday questions and requests around the clock, using your own information." },
      { title: "Advisor", body: "Knows your products and terms, and guides each customer toward the right choice." },
      { title: "Assistant", body: "Takes care of the repetitive parts of conversations and only brings you what needs you." },
      { title: "Follow-up", body: "Keeps each conversation on track until it's resolved, so no customer request gets lost." },
    ],
  },

  channels: {
    eyebrow: "Channels",
    title: "Works where your customers already are",
    lead: "Connect your business's messaging channels; Javab works across all of them with the same knowledge and the same voice.",
    names: { instagram: "Instagram", whatsapp: "WhatsApp", telegram: "Telegram", bale: "Bale" },
    connect: (name) => `Connect ${name}`,
    live: "Live",
    soon: "Coming soon",
  },

  problem: {
    eyebrow: "Why Javab",
    title: "Most customer messages are the same few questions",
    lead: "Price, size, stock, shipping cost, payment. Customers want the answer now, even at 2 a.m. — and a message left unanswered is usually a sale that doesn't happen.",
    inboxTitle: "Last night's messages",
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
      { title: "Only from your own information", body: "Javab doesn't make things up. Answers come from your business info and your product list." },
      { title: "When it doesn't know, it doesn't guess", body: "A question your info doesn't cover is handed to you instead of getting a wrong answer." },
    ],
  },

  features: {
    eyebrow: "How it works",
    title: "A teammate that knows your business",
    lead: "Javab works from your own information, products and rules — like a well-trained colleague.",
    knowledge: {
      title: "Works from your business info",
      body: "Write down shipping, payment, returns and FAQs once, or upload a PDF, Word file or photo of them. Javab answers only from this information.",
      bullets: [
        "Text in files and photos is extracted automatically, and you can edit it",
        "Questions your info didn't cover are collected so you can add the answer in one click",
      ],
    },
    products: {
      title: "Prices and stock, always current",
      body: "Connect your product list from Google Sheets or an Excel file. Before every answer, Javab checks price and stock in that list.",
      bullets: [
        "Google Sheets syncs automatically every 5 minutes",
        "If a colour or size is sold out, it suggests the variants still in stock",
        "Learns product photos and details from your Telegram channel posts",
      ],
    },
    handoff: {
      title: "Hands the conversation to you when it should",
      body: "A question your info doesn't cover gets a polite holding reply and is handed to you, shown above everything else in your panel.",
      bullets: [
        "You hear about it right away in your own Telegram or Bale, and reply from there",
        "Browser notification and a count in the tab title",
        "Replying to the customer yourself closes the handoff automatically",
        "While you're in the conversation, Javab stays quiet for that customer",
      ],
    },
    control: {
      title: "Your tone, your rules",
      body: "Friendly or formal, with or without emoji. Write rules Javab must never break, and pause it for any single customer whenever you like.",
      bullets: ["Before you start, ask questions as a customer on the test page", "Turn Javab on or off for everyone with one switch"],
    },
    comments: {
      title: "Answers comments, publicly or by DM",
      body: "Javab reads the comments under your posts and reels, and the post's caption tells it which product \"how much?\" is about. It answers by private message with a short public note, or however you choose.",
      bullets: [
        "What it doesn't know, it doesn't reply to: it waits for you, sorted by price, stock, ordering, complaint…",
        "Thanks people for compliments, ignores friends tagging friends, and can hide spam",
        "Try any comment in the panel and see the reply before you switch it on",
      ],
    },
    stories: {
      title: "Your stories, published on time",
      body: "Upload story photos and videos, pick a time for each, and Javab publishes them to your account right on schedule. Add a line about what each story shows.",
      bullets: [
        "When someone replies to a story, the bot knows what it's about and answers",
        "It also thanks people who mention your shop in their story",
        "A clear timeline of today's, tomorrow's and past stories",
      ],
    },
    insights: {
      title: "Your page's numbers, and a content assistant",
      body: "Javab reads your page's reach, engagement, followers and how every post did, and tells you plainly what works: which format, which day, which hour, which hashtags.",
      bullets: [
        "An AI content assistant turns your numbers into ideas, captions and a weekly plan",
        "Ask it \"what should I post this week?\" or \"write a caption for this product\"",
        "Numbers refresh daily, or whenever you press refresh",
      ],
    },
    instagramTag: "With Instagram, coming soon",
  },

  demos: {
    knowledge: {
      title: "Business info",
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
      reasonText: "The customer wants an official invoice, and that isn't in your info yet.",
      reply: "Reply to customer",
      resolve: "Close",
      tabCount: "(1) Your business panel",
    },
    tone: {
      title: "Tone",
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
      rules: "Rules",
      rulesText: "Never offer discounts. Don't talk about competitors.",
    },
    comments: {
      title: "Comments",
      author: "rana.k",
      comment: "How much is this manto?",
      privateLabel: "Private message",
      privateReply: "Hi Rana! The linen manto is 1,250,000 toman, in black and navy 🖤",
      publicLabel: "Public reply",
      publicReply: "Sent you the details in a message 💌",
      waitingTitle: "Waiting for you",
      waiting: [
        { category: "Ordering & delivery", text: "Can I order 20 pieces? Wholesale price?" },
        { category: "Complaint", text: "My order still hasn't arrived!" },
      ],
    },
    stories: {
      title: "Scheduled stories",
      items: [
        { when: "Today 18:00", note: "Weekend sale on silk blouses", status: "Scheduled" },
        { when: "Tomorrow 19:00", note: "Cream linen shirt back in stock", status: "Scheduled" },
        { when: "Yesterday 20:00", note: "New linen manto, 1,250,000 toman", status: "Published" },
      ],
      reply: "Replied to your story: \"Is it available in 40?\"",
      answer: "Yes, 40 is available in black 🖤",
    },
    insights: {
      title: "Insights",
      reach: "Reach (7 days)",
      reachValue: "11.8K",
      change: "+21.8%",
      formats: [
        { label: "Reel", value: 92 },
        { label: "Carousel", value: 38 },
        { label: "Photo", value: 22 },
      ],
      best: "Best time to post",
      bestValue: "Wednesday & Thursday, 18:00",
      idea: "An idea from the content assistant",
      ideaText: "Reel: \"3 ways to style the linen manto\" on Thursday at 18:00",
    },
  },

  how: {
    eyebrow: "Setup",
    title: "From sign-up to first conversation in four steps",
    lead: "Nothing to install and no technical knowledge needed — it all happens in the panel.",
    steps: [
      { title: "Connect a channel", body: "Your shop's own link on Telegram and Bale is ready; put it in your bio and channel. No passwords needed. Instagram is coming soon." },
      { title: "Info and products", body: "Enter shipping, payment, returns and FAQs, and connect your product list." },
      { title: "Test Javab", body: "Ask questions as a customer on the test page and see the replies. Nothing is sent to anyone." },
      { title: "Go live", body: "Flip one switch. From then on, Javab talks to your customers and you only see what's handed to you." },
    ],
  },

  trust: {
    eyebrow: "Security & control",
    title: "Your accounts, your rules, your data",
    lead: "Javab is built so the business owner always stays in control.",
    items: [
      { title: "Official channel connections", body: "Each channel connects through that platform's official flow. We never ask for your account passwords." },
      { title: "Encrypted access", body: "Channel access tokens are stored encrypted, and your password only as a hash." },
      { title: "Your data isn't sold", body: "We don't use your data for advertising or to train models, and we don't sell it to anyone." },
      { title: "Full deletion, any time", body: "Deleting your account permanently removes conversations, info, products and channel connections." },
    ],
    privacyLink: "Privacy policy",
  },

  faq: {
    eyebrow: "FAQ",
    title: "Before you start, you might ask",
    items: [
      {
        q: "Which channels does Javab work on?",
        a: "Today, Telegram and Bale. Every shop gets its own link that takes customers straight to that shop's assistant; you can also have your own bot with your shop's name, or let it answer from your personal Telegram account. Instagram is coming soon.",
      },
      {
        q: "Do you need my account passwords to connect?",
        a: "No. Telegram and Bale connect with a one-time link from the panel, and we never ask for any password. You can disconnect any time from the panel.",
      },
      {
        q: "What happens when Javab doesn't know an answer?",
        a: "It doesn't guess. It tells the customer their question is being followed up, hands the conversation to you, and lets you know in the panel and with a browser notification.",
      },
      {
        q: "Can I still talk to customers myself?",
        a: "Yes. Whenever you reply yourself, Javab stays quiet for that customer for a while — you choose how long. You can also pause it completely for any customer.",
      },
      {
        q: "How do I add my products?",
        a: "Any way you like: describe them to the bot in your own words, send a PDF, Word or Excel file, connect a Google Sheet, or forward your Telegram channel posts. Before saving, it shows you a summary of what it understood for your OK.",
      },
      {
        q: "Does it reply to comments too?",
        a: "Yes, with Instagram. You choose: under the comment, by private message, or both. What it doesn't know, it doesn't reply to: it waits for you in the panel, sorted by topic. Scheduled stories and page insights come with Instagram too.",
      },
    ],
  },

  cta: {
    title: "Add Javab to your team",
    lead: "Create an account, add your business info, and try it yourself before you go live.",
    primary: "Create account",
    secondary: "Log in to the panel",
  },

  footer: {
    about: "AI agent for businesses — for sales, support and customer follow-up.",
    product: "Product",
    account: "Account",
    legal: "Legal",
    support: "Support",
    rights: (year) => `© ${year} Javab`,
  },
};

export default landing;
