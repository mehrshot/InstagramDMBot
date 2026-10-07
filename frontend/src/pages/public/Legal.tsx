import { useEffect, type ReactNode } from "react";
import { Link, useLocation } from "react-router";
import { useAuth } from "../../auth/AuthContext";
import SiteFooter from "../../components/site/SiteFooter";
import SiteHeader from "../../components/site/SiteHeader";
import { cx } from "../../components/ui";
import { useI18n, type Lang } from "../../i18n";

// Public legal pages (no login): for owners and their customers, for the payment gateway's
// review, and later for Meta's app review, whose reviewers read English, so every page has a
// full English version; `?lang=en` opens it directly. Every statement here must match what the
// product actually does: change the page when the product changes.

const SUPPORT_EMAIL = import.meta.env.VITE_SUPPORT_EMAIL || "support@javab.app";
const UPDATED = "2026-10-04";

type Page = { title: Record<Lang, string>; body: Record<Lang, ReactNode> };

function LegalShell({ page }: { page: Page }) {
  const { t, lang, f } = useI18n();
  const { loggedIn } = useAuth();
  const { pathname, hash } = useLocation();
  useEffect(() => {
    document.title = `${page.title[lang]} · ${t.appName}`;
  }, [page, lang, t]);
  // /terms#wallet (from the top-up form): the page loads lazily, so scroll once it's there.
  useEffect(() => {
    if (!hash) return;
    // after the app's own scroll-to-top on navigation
    const timer = setTimeout(() => document.getElementById(hash.slice(1))?.scrollIntoView(), 100);
    return () => clearTimeout(timer);
  }, [hash]);
  const links = [
    ["/privacy", t.legal.privacy],
    ["/terms", t.legal.terms],
    ["/data-deletion", t.legal.dataDeletion],
  ] as const;

  return (
    <div className="flex min-h-dvh flex-col bg-surface">
      <SiteHeader />
      <main className="container-site flex-1 py-12 lg:py-16">
        <div className="mx-auto max-w-3xl">
          <nav aria-label={t.landing.footer.legal} className="flex flex-wrap gap-2">
            {links.map(([to, label]) => (
              <Link
                key={to}
                to={to}
                aria-current={pathname === to ? "page" : undefined}
                className={cx(
                  "rounded-full px-3.5 py-1.5 text-sm font-medium transition-colors",
                  pathname === to ? "bg-brand-50 text-brand-700" : "text-slate-500 hover:bg-slate-100 hover:text-ink-950",
                )}
              >
                {label}
              </Link>
            ))}
          </nav>
          <h1 className="mt-10 text-3xl font-extrabold text-ink-950 sm:text-4xl">{page.title[lang]}</h1>
          <p className="mt-3 text-sm text-slate-400">
            {t.legal.lastUpdated}: {f.date(UPDATED)}
          </p>
          <article className="legal mt-10 space-y-4 text-[15px] leading-8 text-slate-700 [&_a]:font-medium [&_a]:text-brand-700 [&_a]:underline [&_a]:underline-offset-2 [&_h2]:mt-10 [&_h2]:scroll-mt-24 [&_h2]:text-lg [&_h2]:font-bold [&_h2]:text-ink-950 [&_h3]:mt-6 [&_h3]:font-bold [&_h3]:text-ink-900 [&_li]:ms-5 [&_ol]:list-decimal [&_ol]:space-y-1 [&_ul]:list-disc [&_ul]:space-y-1">
            {page.body[lang]}
          </article>
          {loggedIn && (
            <Link to="/" className="mt-12 inline-block text-sm font-semibold text-brand-700 hover:underline">
              {t.legal.backToPanel}
            </Link>
          )}
        </div>
      </main>
      <SiteFooter />
    </div>
  );
}

const mail = <a href={`mailto:${SUPPORT_EMAIL}`} dir="ltr">{SUPPORT_EMAIL}</a>;

// ---------------------------------------------------------------------------- privacy

const privacy: Page = {
  title: { fa: "سیاست حریم خصوصی", en: "Privacy Policy" },
  body: {
    fa: (
      <>
        <p>
          «جواب» (در این سند «ما» یا «خدمت») به فروشگاه‌ها و کسب‌وکارهای آنلاین کمک می‌کند تا یک دستیار هوش مصنوعی، با اطلاعات و محصولاتی که خود فروشگاه وارد
          کرده، به پیام‌های مشتری‌هایشان جواب بدهد. امروز «جواب» در پیام‌رسان‌های <b>تلگرام</b> و <b>بله</b> کار می‌کند و <b>اینستاگرام</b> به‌زودی اضافه می‌شود.
          این سند توضیح می‌دهد چه داده‌هایی را، برای چه و چطور پردازش می‌کنیم؛ هم درباره‌ی صاحبان فروشگاه که از «جواب» استفاده می‌کنند و هم درباره‌ی مشتری‌هایی که
          به آن فروشگاه‌ها پیام می‌دهند.
        </p>

        <h2>۱. داده‌های صاحب فروشگاه</h2>
        <ul>
          <li>
            <b>حساب کاربری:</b> ایمیل، نام، اسم فروشگاه و رمز عبور. رمز عبور فقط به صورت هش (غیرقابل بازگشت) ذخیره می‌شود.
          </li>
          <li>
            <b>تأیید هویت:</b> وضعیت تأیید ایمیل، و شماره موبایلی که تأیید می‌کنید (با پیامک یا با فرستادن شماره‌ی اکانت تلگرام یا بله‌تان به ربات). کد
            پیامکی فقط به صورت هش و تا چند دقیقه نگهداری می‌شود.
          </li>
          <li>
            <b>اکانت تلگرام یا بله‌ای که به فروشگاه وصل می‌کنید:</b> شناسه‌ی عددی، نام کاربری و نام نمایشی آن، تا خبر مشتری‌های منتظر را برایتان بفرستیم و
            بتوانید فروشگاه را از داخل پیام‌رسان مدیریت کنید.
          </li>
          <li>
            <b>اطلاعات و محصولات فروشگاه:</b> متن‌ها، فایل‌ها، عکس‌ها و لینک‌هایی که در پنل یا برای ربات می‌فرستید، لیست محصولات (دستی، از فایل یا گوگل شیت)،
            پست‌های کانال تلگرامی که ربات را ادمین آن کرده‌اید، و پیام‌هایی که برای یاد دادن به ربات می‌نویسید.
          </li>
          <li>
            <b>اتصال‌ها:</b> توکن ربات اختصاصی تلگرام یا بله (در صورت اتصال) و شناسه‌ی اتصال Telegram Business. توکن‌ها رمزنگاری‌شده ذخیره می‌شوند.
          </li>
          <li>
            <b>کیف پول و پرداخت:</b> موجودی، پلن، تاریخچه‌ی شارژ و مصرف، و برای هر پرداخت مبلغ، وضعیت و شناسه‌ی فاکتور درگاه. شارژ با درگاه کارت‌به‌کارت
            «آبان گیت‌وی» انجام می‌شود: مبلغ را از اپ بانکی خودتان به کارتی که نشان داده می‌شود واریز می‌کنید و تأییدش خودکار است. ما رمز یا اطلاعات کارت
            بانکی شما را دریافت نمی‌کنیم.
          </li>
          <li>
            <b>مصرف:</b> تعداد و حجم جواب‌های هوش مصنوعی (برای محاسبه‌ی هزینه).
          </li>
        </ul>

        <h2>۲. داده‌های مشتری‌های فروشگاه</h2>
        <p>وقتی کسی در تلگرام یا بله به ربات «جواب» یا ربات اختصاصی یک فروشگاه پیام می‌دهد، این داده‌ها ذخیره می‌شوند:</p>
        <ul>
          <li>متن پیام‌های او و جواب‌هایی که ربات یا فروشگاه برایش فرستاده. از پیوست‌ها (عکس، صدا، فایل و…) فقط نوعشان ثبت می‌شود و خود فایل ذخیره نمی‌شود.</li>
          <li>شناسه‌ی عددی، نام کاربری و نام نمایشی او در همان پیام‌رسان، تا گفتگو به فروشگاه درست برسد و صاحب فروشگاه بداند با چه کسی حرف می‌زند.</li>
          <li>
            اگر فروشگاه حالت «جواب از اکانت شخصی» (Telegram Business) را وصل کرده باشد، پیام‌های خصوصی مشتری‌ها با اکانت تلگرام صاحب فروشگاه، و پیام‌هایی که
            خود صاحب فروشگاه در آن گفتگوها می‌فرستد.
          </li>
        </ul>
        <p>
          این داده‌ها متعلق به همان فروشگاه است و فقط صاحب آن فروشگاه در پنل خودش آن‌ها را می‌بیند. فروشگاه مسئول است که مشتری‌هایش را از استفاده از دستیار
          هوشمند آگاه کند.
        </p>

        <h3>گفتگو با دستیار «جواب» در سایت</h3>
        <p>
          اگر در سایت ما با دستیار «جواب» گفتگو کنید، متن پیام‌ها، یک شناسه‌ی تصادفی که مرورگرتان نگه می‌دارد (و اگر وارد شده باشید، حسابتان) ذخیره می‌شود تا
          گفتگو ادامه پیدا کند و تیم ما بتواند به سوال‌هایی که ربات نمی‌داند جواب بدهد. برای جلوگیری از سوءاستفاده، مقدار مصرف روزانه به‌همراه نشانی IP شما
          شمرده می‌شود و این شمارنده‌ها حداکثر ۷ روز نگه داشته می‌شوند.
        </p>

        <h3>اینستاگرام (پس از فعال شدن)</h3>
        <p>
          وقتی اتصال اینستاگرام فعال شود و فروشگاهی پیج حرفه‌ای خود را از مسیر رسمی متا وصل کند، این‌ها را هم دریافت می‌کنیم: پیام‌های دایرکت آن پیج و جواب‌ها
          (متن و نوع پیوست)، شناسه‌ی اینستاگرامی و نام کاربری مشتری‌ها، شناسه و نام کاربری پیج، پست‌های پیج (برای معرفی محصول) و توکن دسترسی صادرشده توسط متا که
          رمزنگاری‌شده ذخیره می‌شود.
        </p>

        <h2>۳. برای چه استفاده می‌کنیم</h2>
        <ul>
          <li>ساختن و فرستادن جواب به مشتری از طرف فروشگاه، و ارجاع گفتگو به صاحب فروشگاه وقتی ربات جواب را نمی‌داند.</li>
          <li>نمایش گفتگوها، محصولات و گزارش‌ها در پنل، و فرستادن اعلان‌ها به تلگرام یا بله‌ی صاحب فروشگاه.</li>
          <li>محاسبه‌ی هزینه، کم کردن از کیف پول، شارژ آنلاین و تمدید پلن.</li>
          <li>
            تأیید ایمیل و شماره، و جلوگیری از سوءاستفاده؛ از جمله اینکه هدیه‌ی شروع کار به هر نفر فقط یک بار داده شود و تعداد تلاش‌های ورود و درخواست کد محدود
            باشد.
          </li>
          <li>فرستادن ایمیل‌ها و پیام‌های ضروری خدمت (تأیید ایمیل، تغییر رمز، کم شدن موجودی، تغییر پلن). ایمیل یا پیامک تبلیغاتی بدون اجازه‌ی شما نمی‌فرستیم.</li>
          <li>پیدا کردن و رفع خطاهای فنی و حفظ امنیت خدمت.</li>
        </ul>
        <p>
          ما داده‌ها را <b>نمی‌فروشیم</b>، برای <b>تبلیغات</b> استفاده نمی‌کنیم و از آن‌ها برای <b>آموزش مدل‌های هوش مصنوعی</b> استفاده نمی‌کنیم.
        </p>

        <h2>۴. سرویس‌هایی که داده به آن‌ها می‌رسد</h2>
        <p>فقط به اندازه‌ای که برای اجرای خدمت لازم است:</p>
        <ul>
          <li>
            <b>سرویس‌دهنده‌ی هوش مصنوعی:</b> متن پیام مشتری، چند پیام قبلی همان گفتگو و اطلاعات و محصولات مرتبط فروشگاه، فقط برای ساختن جواب.
          </li>
          <li>
            <b>تلگرام و بله:</b> پیام‌ها ذاتاً از طریق همین پیام‌رسان‌ها رد و بدل می‌شوند و تابع قوانین و سیاست حریم خصوصی خود آن‌ها هم هستند.
          </li>
          <li>
            <b>درگاه پرداخت آبان گیت‌وی</b> (برای شارژ کیف پول)، <b>سرویس پیامک</b> (برای کد تأیید شماره)، <b>سرویس ایمیل</b> (برای ایمیل‌های خدمت) و <b>میزبانی سرور</b>.
          </li>
          <li>
            <b>پایش خطا:</b> اطلاعات فنی خطاها (بدون محتوای گفتگوها تا جای ممکن) برای رفع اشکال.
          </li>
          <li>اگر مرجع قانونی صالح طبق قانون درخواست کند.</li>
        </ul>
        <p>سرورهای «جواب» و برخی از این سرویس‌ها ممکن است خارج از ایران باشند.</p>

        <h2>۵. نگهداری و امنیت</h2>
        <ul>
          <li>همه‌ی ارتباط‌ها با پنل و سرور رمزنگاری‌شده (HTTPS) است.</li>
          <li>رمزهای عبور و کدهای تأیید فقط به صورت هش، و توکن‌های ربات و اتصال‌ها رمزنگاری‌شده ذخیره می‌شوند.</li>
          <li>هر فروشگاه فقط به داده‌های خودش دسترسی دارد.</li>
          <li>از پایگاه داده به طور منظم نسخه‌ی پشتیبان رمزنگاری‌شده تهیه می‌شود که حداکثر ۱۴ روز نگهداری و بعد پاک می‌شود.</li>
        </ul>

        <h2>۶. مدت نگهداری و حذف</h2>
        <p>
          داده‌ها تا زمانی که حساب فعال است نگهداری می‌شوند. با حذف حساب، همه‌ی داده‌های آن — گفتگوها و اطلاعات مشتری‌ها، اطلاعات فروشگاه، محصولات، اتصال‌ها،
          کیف پول و تاریخچه‌ی آن — فوراً و برای همیشه پاک می‌شوند و از نسخه‌های پشتیبان هم حداکثر ظرف ۱۴ روز حذف می‌شوند.
        </p>
        <p>
          یک استثنا: برای اینکه هدیه‌ی شروع کار با حذف و ساختن دوباره‌ی حساب دوباره گرفته نشود، یک «اثر انگشت» یک‌طرفه (هش با کلید مخفی) از شناسه‌ی اکانت تلگرام
          یا بله و شماره موبایلی که هدیه را گرفته نگه می‌داریم. از این اثر انگشت نمی‌شود شماره یا شناسه را بازسازی کرد و فقط برای همین مقایسه به کار می‌رود.
        </p>
        <p>
          راهنمای کامل: <Link to="/data-deletion">حذف داده‌ها</Link>.
        </p>

        <h2>۷. حقوق شما</h2>
        <ul>
          <li>اطلاعات حساب و فروشگاه را هر زمان در پنل می‌بینید و ویرایش می‌کنید.</li>
          <li>اتصال اکانت تلگرام یا بله، ربات اختصاصی و کانال را هر زمان از پنل قطع می‌کنید.</li>
          <li>حساب و همه‌ی داده‌هایتان را هر زمان حذف می‌کنید.</li>
          <li>مشتری‌های فروشگاه‌ها می‌توانند حذف گفتگویشان را از ما بخواهند (بخش «حذف داده‌ها»).</li>
        </ul>

        <h2>۸. سن</h2>
        <p>پنل «جواب» برای صاحبان کسب‌وکار است و افراد زیر ۱۸ سال نباید برای آن حساب بسازند.</p>

        <h2>۹. تغییر این سند</h2>
        <p>اگر این سیاست تغییر کند، نسخه‌ی تازه را همین‌جا با تاریخ به‌روزرسانی منتشر می‌کنیم و تغییرهای مهم را در پنل یا با ایمیل اطلاع می‌دهیم.</p>

        <h2>۱۰. تماس</h2>
        <p>پرسش یا درخواست درباره‌ی حریم خصوصی: {mail}</p>
      </>
    ),
    en: (
      <>
        <p>
          Javab (“we”, “the service”) helps online shops and businesses let an AI assistant answer their customers' messages, using the information and products the
          shop provides. Today Javab works on the <b>Telegram</b> and <b>Bale</b> messengers; <b>Instagram</b> is coming soon. This policy explains what data we process,
          why and how — both for shop owners who use Javab and for the customers who message those shops.
        </p>

        <h2>1. Shop owners' data</h2>
        <ul>
          <li>
            <b>Account:</b> email address, name, shop name and password. The password is stored only as a one-way hash.
          </li>
          <li>
            <b>Verification:</b> whether the email is verified, and the mobile number you verify (by SMS, or by sharing your Telegram or Bale account's number with our bot).
            SMS codes are stored only as a hash, for a few minutes.
          </li>
          <li>
            <b>The Telegram or Bale account you link to the shop:</b> its numeric ID, username and display name, so we can tell you about waiting customers and you can manage
            the shop from the messenger.
          </li>
          <li>
            <b>Shop information and products:</b> text, files, photos and links you add in the panel or send the bot, product lists (manual, from files or Google Sheets),
            posts of Telegram channels where you made the bot an admin, and the messages you write to teach the bot.
          </li>
          <li>
            <b>Connections:</b> the token of your own Telegram or Bale bot (if you connect one) and the Telegram Business connection ID. Tokens are stored encrypted.
          </li>
          <li>
            <b>Wallet and payments:</b> balance, plan, top-up and usage history, and for each payment its amount, status and the gateway's invoice ID. Top-ups go through
            the Aban Gateway card-to-card service: you transfer from your own banking app to the card shown and the payment is confirmed automatically. We never receive
            your card details or banking passwords.
          </li>
          <li>
            <b>Usage:</b> the number and size of AI answers (to calculate costs).
          </li>
        </ul>

        <h2>2. Data about the shops' customers</h2>
        <p>When someone messages the Javab bot or a shop's own bot on Telegram or Bale, we store:</p>
        <ul>
          <li>The text of their messages and of the replies sent to them by the bot or the shop. For attachments (photos, audio, files…) only the type is recorded, not the file.</li>
          <li>Their numeric ID, username and display name on that messenger, so the conversation reaches the right shop and the owner knows who they're talking to.</li>
          <li>
            If the shop connected “answer from my personal account” (Telegram Business): the private messages customers send to the owner's Telegram account, and the messages
            the owner sends in those chats.
          </li>
        </ul>
        <p>This data belongs to that shop and only that shop's owner sees it in their panel. The shop is responsible for letting its customers know an AI assistant is used.</p>

        <h3>Chatting with the Javab assistant on our website</h3>
        <p>
          If you chat with the Javab assistant on our website, the messages, a random ID your browser keeps (and your account, if you're logged in) are stored so the
          conversation can continue and our team can answer what the bot doesn't know. To prevent abuse, daily usage is counted together with your IP address; these
          counters are kept for at most 7 days.
        </p>

        <h3>Instagram (once enabled)</h3>
        <p>
          When Instagram is enabled and a shop connects its professional account through Meta's official flow, we also receive: Direct Messages to that account and the replies
          (text and attachment type), customers' Instagram-scoped IDs and usernames, the account's ID and username, its posts (to show products), and an access token issued by
          Meta, which is stored encrypted.
        </p>

        <h2>3. How we use it</h2>
        <ul>
          <li>To generate and send replies to customers on the shop's behalf, and to hand a conversation to the owner when the bot doesn't know the answer.</li>
          <li>To show conversations, products and reports in the panel, and to send notifications to the owner's Telegram or Bale.</li>
          <li>To calculate costs, charge the wallet, process top-ups and renew plans.</li>
          <li>To verify emails and phone numbers and prevent abuse — for example giving the welcome gift only once per person, and limiting login attempts and code requests.</li>
          <li>To send emails and messages the service needs (verification, password reset, low balance, plan changes). We don't send marketing without your permission.</li>
          <li>To find and fix technical errors and keep the service secure.</li>
        </ul>
        <p>
          We do <b>not sell</b> data, use it for <b>advertising</b>, or use it to <b>train AI models</b>.
        </p>

        <h2>4. Who receives data</h2>
        <p>Only what is needed to run the service:</p>
        <ul>
          <li>
            <b>The AI provider:</b> the customer's message, a few earlier messages of the conversation and the shop's relevant information and products, only to produce a reply.
          </li>
          <li>
            <b>Telegram and Bale:</b> messages travel through these messengers by nature and are also subject to their own terms and privacy policies.
          </li>
          <li>
            The <b>Aban Gateway</b> payment service (wallet top-ups), an <b>SMS provider</b> (verification codes), an <b>email provider</b> (service emails) and our <b>hosting provider</b>.
          </li>
          <li>
            <b>Error monitoring:</b> technical details of errors (avoiding conversation content where possible).
          </li>
          <li>A competent authority, when the law requires it.</li>
        </ul>
        <p>Javab's servers and some of these services may be located outside Iran.</p>

        <h2>5. Storage and security</h2>
        <ul>
          <li>All connections to the panel and server are encrypted (HTTPS).</li>
          <li>Passwords and verification codes are stored only as hashes; bot tokens and connection tokens are encrypted.</li>
          <li>Each shop can access only its own data.</li>
          <li>The database is backed up regularly in encrypted form; backups are kept for at most 14 days and then deleted.</li>
        </ul>

        <h2>6. Retention and deletion</h2>
        <p>
          Data is kept while the account is active. When an account is deleted, all of its data — conversations and customer details, shop information, products,
          connections, the wallet and its history — is deleted immediately and permanently, and disappears from backups within 14 days.
        </p>
        <p>
          One exception: so the welcome gift can't be claimed again by deleting and re-creating an account, we keep a one-way fingerprint (a keyed hash) of the Telegram or
          Bale account ID and the mobile number that received it. The number or ID cannot be recovered from it; it is used only for that comparison.
        </p>
        <p>
          Full instructions: <Link to="/data-deletion?lang=en">Data Deletion</Link>.
        </p>

        <h2>7. Your rights</h2>
        <ul>
          <li>You can see and edit your account and shop information in the panel at any time.</li>
          <li>You can disconnect your Telegram or Bale account, your own bot and your channel from the panel at any time.</li>
          <li>You can delete your account and all its data at any time.</li>
          <li>Customers of shops can ask us to delete their conversation (see Data Deletion).</li>
        </ul>

        <h2>8. Age</h2>
        <p>The Javab panel is for business owners; people under 18 should not create an account.</p>

        <h2>9. Changes</h2>
        <p>If this policy changes, we publish the new version here with its date and announce important changes in the panel or by email.</p>

        <h2>10. Contact</h2>
        <p>Privacy questions or requests: {mail}</p>
      </>
    ),
  },
};

// ---------------------------------------------------------------------------- terms

const terms: Page = {
  title: { fa: "شرایط استفاده", en: "Terms of Service" },
  body: {
    fa: (
      <>
        <p>
          با ساختن حساب در «جواب» یا استفاده از آن، این شرایط و <Link to="/privacy">سیاست حریم خصوصی</Link> را می‌پذیرید. اگر با آن‌ها موافق نیستید، از خدمت
          استفاده نکنید.
        </p>

        <h2>۱. خدمت</h2>
        <p>
          «جواب» یک دستیار هوش مصنوعی است که با اطلاعات و محصولاتی که شما وارد می‌کنید، از طرف فروشگاه‌تان به پیام‌های مشتری‌ها جواب می‌دهد، سوال‌هایی را که
          جوابشان را نمی‌داند به شما ارجاع می‌دهد و گفتگوها را در پنل نشان می‌دهد. امروز در <b>تلگرام</b> و <b>بله</b> کار می‌کند؛ از راه لینک اختصاصی فروشگاه روی
          ربات «جواب»، ربات اختصاصی خودتان، یا (در تلگرام) از طرف اکانت شخصی شما. <b>اینستاگرام</b> بعد از تأیید متا اضافه می‌شود.
        </p>
        <p>«جواب» فقط به سوال‌ها جواب می‌دهد؛ سفارش ثبت نمی‌کند، پول دریافت نمی‌کند و طرف معامله‌ی شما با مشتری‌هایتان نیست.</p>

        <h2>۲. حساب کاربری</h2>
        <ul>
          <li>اطلاعات حساب باید درست و متعلق به خودتان باشد. حفظ رمز عبور و امنیت اکانت‌های تلگرام و بله‌ای که وصل می‌کنید با شماست.</li>
          <li>برای تأیید هویت ممکن است از شما بخواهیم ایمیل و شماره موبایلتان را تأیید کنید.</li>
          <li>هر اکانت تلگرام یا بله در هر زمان فقط به یک فروشگاه وصل است و هر شماره موبایل فقط برای یک حساب تأیید می‌شود.</li>
        </ul>

        <h2>۳. مسئولیت‌های شما</h2>
        <ul>
          <li>کانال‌ها، ربات‌ها و اکانت‌هایی که وصل می‌کنید باید متعلق به شما باشند یا اجازه‌ی مدیریتشان را داشته باشید، و باید قوانین تلگرام، بله و (بعدا) اینستاگرام و متا را رعایت کنید.</li>
          <li>درستی اطلاعات فروشگاه، قیمت‌ها، موجودی و شرایط فروش با شماست. قبل از روشن کردن ربات آن را در صفحه‌ی تست امتحان کنید و جواب‌هایش را گاهی مرور کنید.</li>
          <li>فروش کالا یا خدمت غیرقانونی، کلاهبرداری، فرستادن پیام انبوه یا ناخواسته (اسپم) و هر استفاده‌ی خلاف قانون یا آزارنده از «جواب» ممنوع است.</li>
          <li>مشتری‌هایتان را از اینکه یک دستیار هوشمند به آن‌ها جواب می‌دهد آگاه کنید و با داده‌هایشان مطابق قانون رفتار کنید.</li>
        </ul>

        <h2>۴. جواب‌های هوش مصنوعی</h2>
        <p>
          جواب‌ها خودکار ساخته می‌شوند و با وجود همه‌ی تلاش ما ممکن است گاهی ناقص یا اشتباه باشند. «جواب» فقط از اطلاعات شما استفاده می‌کند و وقتی جوابی را نداند،
          پیام انتخابی شما را می‌فرستد و گفتگو را به شما می‌سپارد. هر زمان می‌توانید ربات را برای یک مشتری متوقف یا کاملاً خاموش کنید. مسئولیت تعهدهایی که فروشگاه
          به مشتری‌هایش می‌دهد با خود فروشگاه است.
        </p>

        <h2 id="wallet">۵. کیف پول، هزینه‌ها و پلن‌ها</h2>
        <ul>
          <li>«جواب» پیش‌پرداخت است: کیف پول فروشگاه را به تومان شارژ می‌کنید و هزینه‌ی هر جواب ربات، به اندازه‌ی مصرف و با یک حداقل برای هر جواب، از آن کم می‌شود. تعرفه‌ی روز در پنل، صفحه‌ی «کیف پول و پلن» آمده است.</li>
          <li>پلن‌های بالاتر از «پایه» هزینه‌ی ماهانه دارند که از کیف پول کم می‌شود و هر ۳۰ روز تمدید می‌شود. تغییر به پلن پایین‌تر از پایان ماهِ پرداخت‌شده اعمال می‌شود. اگر موجودی برای تمدید کافی نباشد، پلن به «پایه» برمی‌گردد.</li>
          <li>وقتی موجودی تمام شود، ربات به مشتری‌ها جواب نمی‌دهد و پیام‌ها به خود شما ارجاع می‌شوند تا کیف پول را دوباره شارژ کنید.</li>
          <li>
            <b>اعتبار کیف پول قابل استرداد نیست:</b> مبلغی که شارژ می‌کنید به پول نقد تبدیل یا به حساب بانکی برگردانده نمی‌شود و فقط برای استفاده از خدمات «جواب» در
            همان حساب است. اعتبار قابل انتقال به حساب دیگری هم نیست.
          </li>
          <li>
            شارژ کارت‌به‌کارت فقط وقتی خودکار تأیید می‌شود که <b>دقیقا همان مبلغی</b> که صفحه‌ی پرداخت نشان می‌دهد، پیش از پایان مهلتش واریز شود. اگر مبلغ دیگری
            یا بعد از مهلت واریز کردید، با رسید واریز به پشتیبانی پیام بدهید تا بررسی و دستی ثبت شود.
          </li>
          <li>با حذف حساب، موجودی باقی‌مانده هم از بین می‌رود.</li>
          <li>
            <b>هدیه‌ی شروع کار:</b> اعتبار هدیه به هر نفر فقط یک بار داده می‌شود (پس از وصل کردن اکانت تلگرام یا بله و تأیید شماره موبایل). ارزش نقدی ندارد و اگر با
            ساختن چند حساب یا هر روش فریبکارانه گرفته شود، حذف می‌شود.
          </li>
          <li>ممکن است تعرفه‌ها و هزینه‌ی پلن‌ها را تغییر دهیم؛ تغییر را دست‌کم ۷ روز قبل در پنل اعلام می‌کنیم و تغییر روی مصرف‌های قبلی اثری ندارد.</li>
        </ul>

        <h2>۶. دسترس‌پذیری</h2>
        <p>
          تلاش می‌کنیم خدمت همیشه در دسترس باشد، اما کارکرد بدون وقفه را تضمین نمی‌کنیم. «جواب» به در دسترس بودن تلگرام، بله، اینستاگرام، سرویس‌دهنده‌ی هوش
          مصنوعی، درگاه پرداخت و اینترنت وابسته است؛ از جمله محدودیت‌های دسترسی به تلگرام در ایران خارج از اختیار ماست.
        </p>

        <h2>۷. محدودیت مسئولیت</h2>
        <p>
          «جواب» ابزاری برای کمک به پاسخ‌گویی است. ما مسئول زیان‌های غیرمستقیم، از دست رفتن فروش یا سود، یا پیامدهای جواب‌هایی که بر اساس اطلاعات فروشگاه ساخته
          شده‌اند نیستیم. در هر حال، مسئولیت ما حداکثر به اندازه‌ی مبلغی است که در سه ماه گذشته بابت خدمت پرداخت کرده‌اید.
        </p>

        <h2>۸. تعلیق و پایان استفاده</h2>
        <p>
          هر زمان می‌توانید از «حساب کاربری ← حذف حساب» حسابتان را حذف کنید؛ همه‌ی داده‌هایتان پاک می‌شود. اگر این شرایط نقض شود، حق داریم ربات یا حساب را
          موقتاً یا برای همیشه متوقف کنیم و در صورت امکان دلیلش را به شما اطلاع می‌دهیم.
        </p>

        <h2>۹. تغییر این شرایط</h2>
        <p>ممکن است این شرایط را به‌روز کنیم. نسخه‌ی تازه با تاریخ همین‌جا منتشر می‌شود و تغییرهای مهم را در پنل یا با ایمیل اطلاع می‌دهیم. ادامه‌ی استفاده یعنی پذیرش نسخه‌ی تازه.</p>

        <h2>۱۰. قانون حاکم</h2>
        <p>این شرایط تابع قوانین جمهوری اسلامی ایران است. سعی می‌کنیم هر اختلافی را ابتدا از راه گفتگو با پشتیبانی حل کنیم.</p>

        <h2>۱۱. تماس</h2>
        <p>{mail}</p>
      </>
    ),
    en: (
      <>
        <p>
          By creating a Javab account or using the service you agree to these terms and the <Link to="/privacy?lang=en">Privacy Policy</Link>. If you don't agree, don't use
          the service.
        </p>

        <h2>1. The service</h2>
        <p>
          Javab is an AI assistant that answers your customers' messages on behalf of your shop using the information and products you provide, hands you the questions it
          can't answer, and shows conversations in your panel. Today it works on <b>Telegram</b> and <b>Bale</b>: through your shop's link on the Javab bot, your own bot, or
          (on Telegram) on behalf of your personal account. <b>Instagram</b> will be added after Meta's approval.
        </p>
        <p>Javab only answers questions; it doesn't take orders or payments and is not a party to your sales.</p>

        <h2>2. Your account</h2>
        <ul>
          <li>Your account details must be accurate and your own. You are responsible for your password and for the security of the Telegram and Bale accounts you link.</li>
          <li>We may ask you to verify your email and mobile number.</li>
          <li>Each Telegram or Bale account is linked to one shop at a time, and each mobile number can be verified on one account only.</li>
        </ul>

        <h2>3. Your responsibilities</h2>
        <ul>
          <li>You must own, or be authorized to manage, the channels, bots and accounts you connect, and comply with the terms of Telegram, Bale and (later) Instagram and Meta.</li>
          <li>You are responsible for the accuracy of your shop information, prices, stock and terms of sale. Try the bot on the test page before turning it on, and review its answers from time to time.</li>
          <li>Selling illegal goods or services, fraud, bulk or unsolicited messages (spam) and any unlawful or abusive use of Javab are forbidden.</li>
          <li>Let your customers know an AI assistant answers them, and handle their data lawfully.</li>
        </ul>

        <h2>4. AI-generated replies</h2>
        <p>
          Replies are generated automatically and, despite our efforts, may occasionally be incomplete or wrong. Javab uses only your information; when it doesn't know an
          answer it sends your chosen message and hands the conversation to you. You can pause the bot for any customer or turn it off at any time. Commitments a shop makes to
          its customers are the shop's responsibility.
        </p>

        <h2 id="wallet">5. Wallet, fees and plans</h2>
        <ul>
          <li>Javab is prepaid: you top up your shop's wallet in toman and each bot answer is deducted from it by usage, with a minimum per answer. Current rates are on the panel's “Wallet &amp; plan” page.</li>
          <li>Plans above “Basic” have a monthly fee, deducted from the wallet and renewed every 30 days. Moving to a lower plan takes effect when the paid month ends. If the balance can't cover a renewal, the plan returns to Basic.</li>
          <li>When the balance runs out, the bot stops answering customers and messages are handed to you until you top up.</li>
          <li>
            <b>Wallet credit is non-refundable:</b> top-ups are not converted to cash or returned to a bank account; they can only be used for Javab's services in the same
            account, and can't be transferred to another account.
          </li>
          <li>
            A card-to-card top-up is confirmed automatically only when <b>exactly the amount</b> shown on the payment page is transferred before it expires. If you sent a
            different amount or sent it late, message support with the transfer receipt and we will check and credit it by hand.
          </li>
          <li>Any remaining balance is forfeited when the account is deleted.</li>
          <li>
            <b>Welcome gift:</b> gift credit is given once per person (after linking a Telegram or Bale account and verifying a mobile number). It has no cash value and is
            removed if obtained through multiple accounts or any other deception.
          </li>
          <li>We may change rates and plan fees; we announce changes in the panel at least 7 days in advance, and they don't affect past usage.</li>
        </ul>

        <h2>6. Availability</h2>
        <p>
          We work to keep the service available but don't guarantee uninterrupted operation. Javab depends on Telegram, Bale, Instagram, the AI provider, the payment gateway
          and the internet being available, including access restrictions to Telegram in Iran, which are beyond our control.
        </p>

        <h2>7. Limitation of liability</h2>
        <p>
          Javab is a tool to help answer customers. We are not liable for indirect losses, lost sales or profits, or the consequences of replies generated from a shop's
          information. In any case our liability is limited to the amount you paid for the service in the previous three months.
        </p>

        <h2>8. Suspension and termination</h2>
        <p>
          You can delete your account at any time from Account → Delete account; all your data is then deleted. If these terms are violated, we may suspend the bot or the
          account temporarily or permanently, and tell you why where possible.
        </p>

        <h2>9. Changes to these terms</h2>
        <p>We may update these terms. The new version is published here with its date and important changes are announced in the panel or by email. Continuing to use the service means accepting the new version.</p>

        <h2>10. Governing law</h2>
        <p>These terms are governed by the laws of the Islamic Republic of Iran. We aim to resolve any dispute first through our support.</p>

        <h2>11. Contact</h2>
        <p>{mail}</p>
      </>
    ),
  },
};

// ---------------------------------------------------------------------------- data deletion

const dataDeletion: Page = {
  title: { fa: "راهنمای حذف داده‌ها", en: "Data Deletion Instructions" },
  body: {
    fa: (
      <>
        <h2>صاحبان فروشگاه</h2>
        <p>برای حذف حساب و همه‌ی داده‌های مربوط به آن:</p>
        <ol>
          <li>وارد پنل شوید.</li>
          <li>به صفحه‌ی <b>حساب کاربری</b> بروید.</li>
          <li>روی <b>حذف حساب</b> بزنید، تأیید کنید و رمز عبور را وارد کنید.</li>
        </ol>
        <p>
          حذف فوری و همیشگی است: گفتگوها و اطلاعات مشتری‌ها، اطلاعات فروشگاه، محصولات، اکانت‌های تلگرام و بله‌ی وصل‌شده، ربات‌های اختصاصی، کانال‌ها، کیف پول و
          تاریخچه‌ی آن پاک می‌شوند و از نسخه‌های پشتیبان هم حداکثر ظرف ۱۴ روز حذف می‌شوند. موجودی باقی‌مانده‌ی کیف پول قابل استرداد نیست. همچنین می‌توانید از
          ایمیل حسابتان به {mail} پیام بدهید تا حساب ظرف ۳۰ روز حذف شود.
        </p>
        <p>
          تنها چیزی که می‌ماند یک اثر انگشت یک‌طرفه از شناسه‌ی اکانت تلگرام یا بله و شماره‌ای است که هدیه‌ی شروع کار را گرفته؛ تا هدیه دوباره داده نشود (جزئیات در{" "}
          <Link to="/privacy">سیاست حریم خصوصی</Link>).
        </p>

        <h2>قطع اتصال بدون حذف حساب</h2>
        <ul>
          <li>اکانت تلگرام یا بله‌ی خودتان: در پنل، صفحه‌ی تلگرام یا بله، کنار اکانت روی «حذف» بزنید.</li>
          <li>ربات اختصاصی: در همان صفحه «قطع اتصال» را بزنید.</li>
          <li>جواب از اکانت شخصی (Telegram Business): در تنظیمات تلگرام ربات را از Chatbots حذف کنید یا در پنل «توقف» را بزنید.</li>
          <li>کانال تلگرام: ربات را از ادمین‌های کانال حذف کنید.</li>
        </ul>

        <h2>اینستاگرام (پس از فعال شدن)</h2>
        <p>در اینستاگرام: Settings ← Security ← Apps and websites ← حذف برنامه. با این کار ربات متوقف می‌شود؛ برای پاک شدن داده‌های ذخیره‌شده مراحل بالا را انجام دهید.</p>

        <h2>مشتری‌های فروشگاه‌ها</h2>
        <p>
          اگر در تلگرام یا بله (یا اینستاگرام) به فروشگاهی که از «جواب» استفاده می‌کند پیام داده‌اید و می‌خواهید پیام‌هایتان حذف شود، نام کاربری یا شماره‌ی خود
          در همان پیام‌رسان و اسم فروشگاه را به {mail} بفرستید تا گفتگوی شما با آن فروشگاه ظرف ۳۰ روز حذف شود. برای اینکه دیگر پیامی از ربات نگیرید، کافی است آن را
          در پیام‌رسان بلاک کنید.
        </p>
      </>
    ),
    en: (
      <>
        <h2>Shop owners</h2>
        <p>To delete your account and all data associated with it:</p>
        <ol>
          <li>Log in to the panel.</li>
          <li>Go to <b>Account</b>.</li>
          <li>Click <b>Delete account</b>, confirm, and enter your password.</li>
        </ol>
        <p>
          Deletion is immediate and permanent: conversations and customer details, shop information, products, linked Telegram and Bale accounts, your own bots, channels,
          and the wallet with its history are removed, and disappear from backups within 14 days. Any remaining wallet balance is not refundable. You can also email {mail}{" "}
          from your account's email address and we will delete the account within 30 days.
        </p>
        <p>
          The only thing kept is a one-way fingerprint of the Telegram or Bale account ID and the number that received the welcome gift, so it isn't given again (see the{" "}
          <Link to="/privacy?lang=en">Privacy Policy</Link>).
        </p>

        <h2>Disconnecting without deleting the account</h2>
        <ul>
          <li>Your own Telegram or Bale account: in the panel, on the Telegram or Bale page, click “Remove” next to the account.</li>
          <li>Your own bot: click “Disconnect” on the same page.</li>
          <li>Answering from your personal account (Telegram Business): remove the bot under Chatbots in Telegram's settings, or click “Stop” in the panel.</li>
          <li>A Telegram channel: remove the bot from the channel's admins.</li>
        </ul>

        <h2>Instagram (once enabled)</h2>
        <p>
          You can revoke access from Instagram: Settings → Security → Apps and websites → remove the app. The bot then stops working; to delete stored data follow the steps
          above.
        </p>

        <h2>Customers of a shop</h2>
        <p>
          If you messaged a shop that uses Javab on Telegram or Bale (or Instagram) and want your messages deleted, email {mail} with your username or number on that messenger
          and the shop's name. We will delete your conversation with that shop within 30 days. To stop receiving messages from the bot, simply block it in the messenger.
        </p>
      </>
    ),
  },
};

export const Privacy = () => <LegalShell page={privacy} />;
export const Terms = () => <LegalShell page={terms} />;
export const DataDeletion = () => <LegalShell page={dataDeletion} />;
