// Copy added with the panel redesign (navigation groups, page intros, helper text).

const panel = {
  nav: {
    groupMessages: "گفتگوها",
    groupTrain: "آموزش ربات",
    groupSetup: "تنظیمات",
    home: "خانه",
    handoffs: "ارجاع‌ها",
    inbox: "پیام‌ها",
    test: "تست",
    more: "بیشتر",
    main: "منوی پنل",
    closeMenu: "بستن منو",
  },

  dashboard: {
    greeting: (name: string) => `سلام، ${name}`,
    offHint: "روشنش کنید تا به دایرکت‌های مشتری‌ها جواب بدهد.",
    quickTitle: "میان‌برها",
    quick: {
      playground: { title: "تست ربات", body: "جای مشتری سوال بپرسید و جواب را ببینید." },
      knowledge: { title: "اطلاعات فروشگاه", body: "هرچه کامل‌تر، جواب‌های ربات بهتر." },
      inbox: { title: "صندوق پیام", body: "گفتگوهای اخیر مشتری‌ها." },
      settings: { title: "لحن و قوانین", body: "ربات چطور حرف بزند و چه کاری نکند." },
    },
    usageTitle: "مصرف این ماه",
  },

  knowledge: {
    navTitle: "بخش‌ها",
    filled: "پر شده",
    empty: "خالی",
    drop: "فایل را اینجا رها کنید",
    or: "یا",
    choose: "انتخاب فایل",
  },

  playground: {
    env: "محیط تست",
    botName: (shop: string) => `ربات ${shop}`,
    tipsTitle: "چه چیزی را امتحان کنم؟",
    tips: ["سوال‌هایی که مشتری‌ها زیاد می‌پرسند", "موجودی یا قیمت یک محصول مشخص", "سوالی که جوابش را به ربات نداده‌اید"],
    safe: "هیچ پیامی برای کسی فرستاده یا ذخیره نمی‌شود؛ حتی وقتی ربات خاموش است کار می‌کند.",
    improveTitle: "جواب‌ها را بهتر کنید",
  },

  settings: {
    sections: {
      status: { title: "وضعیت", desc: "خاموش و روشن کردن ربات برای همه‌ی دایرکت‌ها." },
      identity: { title: "معرفی", desc: "اسمی که ربات در گفتگو خودش را با آن معرفی می‌کند." },
      tone: { title: "لحن", desc: "ربات با مشتری‌ها چطور حرف بزند. نمونه‌ی هر لحن را ببینید." },
      fallback: { title: "وقتی جواب را نمی‌داند", desc: "پیامی که همراه ارجاع گفتگو به شما فرستاده می‌شود." },
      rules: { title: "قوانین", desc: "خط قرمزهایی که ربات هرگز رد نمی‌کند." },
      handoff: { title: "وقتی خودتان جواب می‌دهید", desc: "ربات برای همان مشتری مدتی ساکت می‌ماند تا حرفتان قطع نشود." },
    },
    discard: "بازگرداندن",
    sample: "نمونه",
  },

  instagram: {
    stepsTitle: "دو کار قبل از اتصال",
    howItWorks: "اتصال از صفحه‌ی رسمی اینستاگرام انجام می‌شود و رمز پیج لازم نیست.",
  },

  notFound: {
    hint: "این صفحه وجود ندارد یا جابه‌جا شده است.",
  },
};

export default panel;
