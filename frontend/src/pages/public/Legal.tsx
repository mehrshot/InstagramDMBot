import { useEffect, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { Languages } from "lucide-react";
import { useAuth } from "../../auth/AuthContext";
import { cx } from "../../components/ui";
import { useI18n, type Lang } from "../../i18n";

// Public pages Meta's app review requires (no login). Meta reviewers read English, so
// every page has a full English version; `?lang=en` opens it directly.

const SUPPORT_EMAIL = import.meta.env.VITE_SUPPORT_EMAIL || "support@example.com";
const UPDATED = "2026-09-24";

type Page = { title: Record<Lang, string>; body: Record<Lang, ReactNode> };

function LegalShell({ page }: { page: Page }) {
  const { t, lang, f, toggleLang } = useI18n();
  const { loggedIn } = useAuth();
  const { pathname } = useLocation();
  useEffect(() => {
    document.title = `${page.title[lang]} · ${t.appName}`;
  }, [page, lang, t]);
  const links = [
    ["/privacy", t.legal.privacy],
    ["/terms", t.legal.terms],
    ["/data-deletion", t.legal.dataDeletion],
  ] as const;

  return (
    <div className="min-h-screen bg-white">
      <header className="border-b border-slate-200">
        <div className="mx-auto flex max-w-3xl flex-wrap items-center gap-4 px-4 py-4">
          <Link to={loggedIn ? "/" : "/login"} className="flex items-center gap-2 font-bold text-slate-900">
            <img src="/favicon.svg" alt="" className="size-8" />
            {t.appName}
          </Link>
          <nav className="flex flex-1 flex-wrap gap-4 text-sm">
            {links.map(([to, label]) => (
              <Link key={to} to={to} className={cx("text-slate-500 hover:text-slate-900", pathname === to && "font-medium text-slate-900")}>
                {label}
              </Link>
            ))}
          </nav>
          <button type="button" onClick={toggleLang} className="inline-flex items-center gap-1 text-sm text-slate-500 hover:text-slate-900">
            <Languages className="size-4" />
            {t.otherLang}
          </button>
        </div>
      </header>
      <main className="mx-auto max-w-3xl px-4 py-10">
        <h1 className="text-3xl font-bold text-slate-900">{page.title[lang]}</h1>
        <p className="mt-2 text-sm text-slate-400">
          {t.legal.lastUpdated}: {f.date(UPDATED)}
        </p>
        <article className="legal mt-8 space-y-4 text-[15px] leading-8 text-slate-700 [&_h2]:mt-8 [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-slate-900 [&_li]:ms-5 [&_ol]:list-decimal [&_ul]:list-disc [&_ol]:space-y-1 [&_ul]:space-y-1 [&_a]:text-brand-600 [&_a]:underline">
          {page.body[lang]}
        </article>
        {loggedIn && (
          <Link to="/" className="mt-10 inline-block text-sm font-medium text-brand-600 hover:underline">
            {t.legal.backToPanel}
          </Link>
        )}
      </main>
    </div>
  );
}

const mail = <a href={`mailto:${SUPPORT_EMAIL}`} dir="ltr">{SUPPORT_EMAIL}</a>;

const privacy: Page = {
  title: { fa: "سیاست حریم خصوصی", en: "Privacy Policy" },
  body: {
    en: (
      <>
        <p>
          Javab (“we”, “the service”) lets online shops connect their Instagram professional account so an AI assistant can answer customers' Direct
          Messages using information the shop provides. This policy explains what data we process and how.
        </p>
        <h2>Data we receive from Instagram</h2>
        <ul>
          <li>Direct Messages sent to the connected Instagram account, and replies sent from it (text, and the type of any attachment such as “image” or “audio”).</li>
          <li>The Instagram-scoped ID and username of customers who message the shop.</li>
          <li>The connected account's Instagram user ID, username, and an access token issued by Meta.</li>
        </ul>
        <h2>Data shop owners give us</h2>
        <ul>
          <li>Account details: email address, name, shop name, and a hashed password.</li>
          <li>Shop information (shipping, payment, FAQs, uploaded files) and product lists (from Google Sheets or uploaded files).</li>
        </ul>
        <h2>How we use it</h2>
        <ul>
          <li>To generate and send replies to customers on the shop's behalf, and to show conversations to the shop owner in their panel.</li>
          <li>Message text and the shop's information are sent to an AI language-model provider only to produce a reply. They are not used to train models by us.</li>
          <li>We do not sell data, use it for advertising, or share it with anyone except the processors needed to run the service (hosting and the AI provider).</li>
        </ul>
        <h2>Storage and security</h2>
        <p>
          Data is stored on our servers over encrypted (HTTPS) connections. Instagram access tokens are encrypted at rest and passwords are stored only as
          hashes. Access is limited to the shop's own account.
        </p>
        <h2>Retention and deletion</h2>
        <p>
          Data is kept while the shop's account is active. When a shop owner deletes their account, all of its data — conversations, customer usernames,
          shop information, products and the Instagram connection — is permanently deleted. See <Link to="/data-deletion?lang=en">Data Deletion</Link>.
        </p>
        <h2>Contact</h2>
        <p>Questions about privacy: {mail}</p>
      </>
    ),
    fa: (
      <>
        <p>
          «جواب» به فروشگاه‌های آنلاین امکان می‌دهد حساب حرفه‌ای اینستاگرام خود را وصل کنند تا یک دستیار هوشمند با اطلاعاتی که فروشگاه وارد کرده به
          دایرکت مشتری‌ها جواب بدهد. این سند توضیح می‌دهد چه داده‌ای را و چطور پردازش می‌کنیم.
        </p>
        <h2>داده‌هایی که از اینستاگرام دریافت می‌کنیم</h2>
        <ul>
          <li>پیام‌های دایرکتی که به پیج متصل فرستاده می‌شود و جواب‌هایی که از آن ارسال می‌شود (متن، و نوع پیوست مثل «عکس» یا «صدا»).</li>
          <li>شناسه‌ی اینستاگرامی و نام کاربری مشتری‌هایی که به فروشگاه پیام می‌دهند.</li>
          <li>شناسه و نام کاربری پیج متصل، و توکن دسترسی صادرشده توسط متا.</li>
        </ul>
        <h2>داده‌هایی که صاحب فروشگاه وارد می‌کند</h2>
        <ul>
          <li>اطلاعات حساب: ایمیل، نام، اسم فروشگاه و رمز عبور (به صورت هش‌شده).</li>
          <li>اطلاعات فروشگاه (ارسال، پرداخت، سوال‌های پرتکرار، فایل‌ها) و لیست محصولات (از گوگل شیت یا فایل).</li>
        </ul>
        <h2>نحوه‌ی استفاده</h2>
        <ul>
          <li>ساختن و ارسال جواب به مشتری از طرف فروشگاه، و نمایش گفتگوها به صاحب فروشگاه در پنل.</li>
          <li>متن پیام و اطلاعات فروشگاه فقط برای ساختن جواب به سرویس‌دهنده‌ی مدل هوش مصنوعی فرستاده می‌شود؛ ما از آن برای آموزش مدل استفاده نمی‌کنیم.</li>
          <li>داده‌ها را نمی‌فروشیم، برای تبلیغات استفاده نمی‌کنیم و جز با سرویس‌های لازم برای اجرای خدمت (میزبانی و هوش مصنوعی) به اشتراک نمی‌گذاریم.</li>
        </ul>
        <h2>نگهداری و امنیت</h2>
        <p>داده‌ها روی سرورهای ما و از طریق اتصال رمزنگاری‌شده (HTTPS) نگهداری می‌شوند. توکن‌های اینستاگرام رمزنگاری‌شده ذخیره می‌شوند و رمزهای عبور فقط به صورت هش.</p>
        <h2>مدت نگهداری و حذف</h2>
        <p>
          داده‌ها تا زمانی که حساب فروشگاه فعال است نگهداری می‌شوند. با حذف حساب، همه‌ی داده‌ها — گفتگوها، نام کاربری مشتری‌ها، اطلاعات فروشگاه، محصولات و اتصال
          اینستاگرام — برای همیشه پاک می‌شوند. <Link to="/data-deletion">راهنمای حذف داده‌ها</Link> را ببینید.
        </p>
        <h2>تماس</h2>
        <p>پرسش درباره‌ی حریم خصوصی: {mail}</p>
      </>
    ),
  },
};

const terms: Page = {
  title: { fa: "شرایط استفاده", en: "Terms of Service" },
  body: {
    en: (
      <>
        <p>By creating an account or connecting an Instagram account to Javab you agree to these terms.</p>
        <h2>The service</h2>
        <p>Javab replies to Instagram Direct Messages on behalf of your shop using the information and products you provide, and shows the conversations in your panel.</p>
        <h2>Your responsibilities</h2>
        <ul>
          <li>You must own or be authorized to manage the Instagram account you connect, and comply with Instagram's Terms of Use and Meta's Platform Terms.</li>
          <li>You are responsible for the accuracy of your shop information, prices and stock. Review the bot's behaviour using the test page before turning it on.</li>
          <li>Do not use the service for spam, unsolicited messages, or any unlawful purpose.</li>
        </ul>
        <h2>AI-generated replies</h2>
        <p>
          Replies are generated automatically and may occasionally be wrong. When the bot doesn't know an answer it sends your chosen message and hands the conversation to
          you. You can pause the bot for any customer or turn it off at any time.
        </p>
        <h2>Availability</h2>
        <p>We work to keep the service available but do not guarantee uninterrupted operation, and we depend on Instagram's API being available.</p>
        <h2>Termination</h2>
        <p>You can delete your account at any time from Account → Delete account; all your data is then deleted. We may suspend accounts that violate these terms.</p>
        <h2>Contact</h2>
        <p>{mail}</p>
      </>
    ),
    fa: (
      <>
        <p>با ساختن حساب یا اتصال پیج اینستاگرام به «جواب»، این شرایط را می‌پذیرید.</p>
        <h2>خدمت</h2>
        <p>«جواب» با اطلاعات و محصولاتی که وارد می‌کنید، از طرف فروشگاه شما به دایرکت‌های اینستاگرام جواب می‌دهد و گفتگوها را در پنل نشان می‌دهد.</p>
        <h2>مسئولیت‌های شما</h2>
        <ul>
          <li>پیجی که وصل می‌کنید باید متعلق به شما باشد یا اجازه‌ی مدیریتش را داشته باشید، و باید قوانین اینستاگرام و متا را رعایت کنید.</li>
          <li>درستی اطلاعات فروشگاه، قیمت‌ها و موجودی به عهده‌ی شماست. قبل از روشن کردن ربات، آن را در صفحه‌ی تست امتحان کنید.</li>
          <li>استفاده از خدمت برای اسپم، پیام ناخواسته یا هر کار غیرقانونی ممنوع است.</li>
        </ul>
        <h2>جواب‌های هوش مصنوعی</h2>
        <p>جواب‌ها خودکار ساخته می‌شوند و ممکن است گاهی اشتباه باشند. وقتی ربات جوابی را نداند، پیام انتخابی شما را می‌فرستد و گفتگو را به شما می‌سپارد. هر زمان می‌توانید ربات را برای یک مشتری متوقف یا کاملاً خاموش کنید.</p>
        <h2>دسترس‌پذیری</h2>
        <p>تلاش می‌کنیم خدمت همیشه در دسترس باشد، اما کارکرد بدون وقفه را تضمین نمی‌کنیم و به در دسترس بودن API اینستاگرام وابسته‌ایم.</p>
        <h2>پایان استفاده</h2>
        <p>هر زمان می‌توانید از «حساب کاربری ← حذف حساب» حساب خود را حذف کنید؛ همه‌ی داده‌هایتان پاک می‌شود. حساب‌هایی که این شرایط را نقض کنند ممکن است مسدود شوند.</p>
        <h2>تماس</h2>
        <p>{mail}</p>
      </>
    ),
  },
};

const dataDeletion: Page = {
  title: { fa: "راهنمای حذف داده‌ها", en: "Data Deletion Instructions" },
  body: {
    en: (
      <>
        <h2>Shop owners</h2>
        <p>To delete your account and all data associated with it (including all data received from Instagram):</p>
        <ol>
          <li>Log in to the panel.</li>
          <li>Go to <b>Account</b>.</li>
          <li>Click <b>Delete account</b>, confirm, and enter your password.</li>
        </ol>
        <p>
          Deletion is immediate and permanent: conversations, customer usernames and IDs, shop information, products, and the Instagram connection and access token are all
          removed. You can also email {mail} from your account's email address and we will delete it within 30 days.
        </p>
        <h2>Removing the app from Instagram</h2>
        <p>
          You can also revoke access from Instagram: Settings → Security → Apps and websites → remove the app. The bot then stops working; to delete stored data follow the
          steps above.
        </p>
        <h2>Customers of a shop</h2>
        <p>
          If you messaged a shop that uses Javab and want your messages deleted, email {mail} with your Instagram username and the shop's username. We will delete your
          conversation with that shop within 30 days.
        </p>
      </>
    ),
    fa: (
      <>
        <h2>صاحبان فروشگاه</h2>
        <p>برای حذف حساب و همه‌ی داده‌های مربوط به آن (از جمله همه‌ی داده‌های دریافتی از اینستاگرام):</p>
        <ol>
          <li>وارد پنل شوید.</li>
          <li>به صفحه‌ی <b>حساب کاربری</b> بروید.</li>
          <li>روی <b>حذف حساب</b> بزنید، تأیید کنید و رمز عبور را وارد کنید.</li>
        </ol>
        <p>حذف فوری و همیشگی است: گفتگوها، نام کاربری و شناسه‌ی مشتری‌ها، اطلاعات فروشگاه، محصولات و اتصال و توکن اینستاگرام پاک می‌شوند. همچنین می‌توانید از ایمیل حساب خود به {mail} پیام دهید تا ظرف ۳۰ روز حذف شود.</p>
        <h2>حذف دسترسی از خود اینستاگرام</h2>
        <p>در اینستاگرام: Settings ← Security ← Apps and websites ← حذف برنامه. با این کار ربات متوقف می‌شود؛ برای پاک شدن داده‌های ذخیره‌شده مراحل بالا را انجام دهید.</p>
        <h2>مشتری‌های فروشگاه‌ها</h2>
        <p>اگر به فروشگاهی که از «جواب» استفاده می‌کند پیام داده‌اید و می‌خواهید پیام‌هایتان حذف شود، نام کاربری اینستاگرام خود و فروشگاه را به {mail} بفرستید تا ظرف ۳۰ روز حذف شود.</p>
      </>
    ),
  },
};

export const Privacy = () => <LegalShell page={privacy} />;
export const Terms = () => <LegalShell page={terms} />;
export const DataDeletion = () => <LegalShell page={dataDeletion} />;
