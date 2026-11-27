import type { WebsiteLocale } from "./website";

export function getMcpPublicUrl(configured: string | undefined): string | null {
  if (!configured?.trim()) return null;
  try {
    const url = new URL(configured.trim());
    const domain = /^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z][a-z0-9-]{0,62}$/;
    const privateName = /(?:^|\.)(?:localhost|local|internal|test|example|invalid|onion)$/;
    if (
      url.protocol !== "https:" || !domain.test(url.hostname) || privateName.test(url.hostname) ||
      url.port || url.href !== `${url.origin}/mcp`
    ) return null;
    return url.href;
  } catch {
    return null;
  }
}

export const mcpProviders = [
  { id: "chatgpt", name: "ChatGPT", docs: "https://help.openai.com/en/articles/12584461-connecting-custom-mcp-servers-in-chatgpt" },
  { id: "claude", name: "Claude", docs: "https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp" },
  { id: "gemini", name: "Gemini Apps", docs: "https://support.google.com/gemini/answer/17209137" },
] as const;

type ProviderId = typeof mcpProviders[number]["id"];
type ProviderGuide = { availability: string; steps: readonly string[] };
type Prompt = { question: string; caption: string; icon: "board" | "chat" | "inbox" };
type McpPageCopy = {
  title: string;
  description: string;
  lead: string;
  seeSetup: string;
  developerGuide: string;
  serverUrl: string;
  preview: string;
  previewDescription: string;
  endpointDescription: string;
  unverified: string;
  copy: { action: string; success: string; failure: string };
  promptsTitle: string;
  promptsDescription: string;
  prompts: readonly Prompt[];
  setupTitle: string;
  setupDescription: string;
  providerGuide: (name: string) => string;
  providers: Record<ProviderId, ProviderGuide>;
  securityTitle: string;
  security: string;
  disconnectTitle: string;
  disconnect: string;
  privacy: string;
  faqTitle: string;
  faq: readonly { question: string; answer: string }[];
  sdkGuide: string;
  cliGuide: string;
  contact: string;
};

export const mcpPageCopy = {
  en: {
    title: "AI integrations with MCP",
    description: "Explore TeamBoard’s AI integration, available tools, account permissions and connection guides for ChatGPT, Claude and Gemini Apps.",
    lead: "Bring your TeamBoard tasks, project context and conversations into the AI tools you use. Model Context Protocol (MCP) gives those tools a standard way to request the information your account can access.",
    seeSetup: "View connection guides",
    developerGuide: "Developer documentation",
    serverUrl: "MCP server URL",
    preview: "Local preview",
    previewDescription: "TeamBoard’s public MCP address has yet to be published. Developers can test the integration on their own computer using the local guide.",
    endpointDescription: "Use this address in your AI app’s custom connection settings. TeamBoard uses OAuth for authorization.",
    unverified: "The integration is tested locally. Live compatibility with the hosted AI apps is still unverified.",
    copy: { action: "Copy URL", success: "Server URL copied.", failure: "Select and copy the URL manually." },
    promptsTitle: "What you can ask",
    promptsDescription: "Read accessible workspaces, projects, chats, calendars and reports. A separate write permission enables actions such as creating tasks and reminders.",
    prompts: [
      { question: "Show my overdue tasks in the Website workspace.", caption: "Tasks and deadlines", icon: "board" },
      { question: "Summarize the recent messages in the Backend project chat.", caption: "Project conversations", icon: "chat" },
      { question: "What are my five most recent unread notifications?", caption: "Your inbox", icon: "inbox" },
    ],
    setupTitle: "Connect your AI app",
    setupDescription: "These steps describe the providers’ custom MCP settings. Setup requires a published TeamBoard endpoint and an eligible account.",
    providerGuide: (name: string) => `Official ${name} guide`,
    providers: {
      chatgpt: {
        availability: "Full custom MCP is documented for Business and Enterprise/Edu on the web, subject to workspace permissions. Pro supports read and fetch tools.",
        steps: [
          "In ChatGPT on the web, go to Plugins and choose Add custom MCP server.",
          "Enter TeamBoard as the name, add the published server URL and select OAuth.",
          "Review ChatGPT’s warning, sign in on TeamBoard and review the requested access. Review the discovered tools before using the connection.",
        ],
      },
      claude: {
        availability: "Claude supports custom remote connectors on Free and paid plans. Free accounts have one custom connector. Organization permissions and supported regions apply.",
        steps: [
          "In Customize → Connectors, add a custom connector. For Team or Enterprise, your organization may need to add it first.",
          "Name the connector TeamBoard and paste the published server URL. Review the detected OAuth settings.",
          "Connect, sign in on TeamBoard and review the requested access. Enable the connector in the conversation where you want to use it.",
        ],
      },
      gemini: {
        availability: "Google currently documents custom apps for US adults with personal Google accounts, enabled History and English. Setup starts on the web.",
        steps: [
          "In Gemini on the web, open Settings → Connected Apps and find Custom apps.",
          "Paste the published server URL and follow the connection setup. Use OAuth configuration provided by TeamBoard if the setup requests it.",
          "Sign in on TeamBoard and review the requested access. In Gemini, select the linked app with @ when you want to use it.",
        ],
      },
    },
    securityTitle: "You control access",
    security: "Sign in and approve access on TeamBoard. Each call uses an MCP credential and checks your current permissions. Your chosen AI provider receives the results of the calls it makes, so review its data settings before sharing workspace information.",
    disconnectTitle: "Disconnect and revoke",
    disconnect: "In TeamBoard, open Security → AI connections to revoke one client or all clients. Then remove TeamBoard from the AI app’s plugin or connector settings. Review the provider’s settings to manage data already sent there.",
    privacy: "TeamBoard privacy policy",
    faqTitle: "Questions and troubleshooting",
    faq: [
      { question: "Why can’t I find the connection option?", answer: "Check your AI provider’s account, region and workspace requirements. If your account is managed by an organization, ask its administrator to check your permissions." },
      { question: "Why does the connection fail or show no tools?", answer: "Use the official HTTPS server address, including its path. Check if the integration is available, finish TeamBoard sign-in and verify the connection is enabled in your AI app." },
      { question: "Can AI create tasks or download files?", answer: "A write connection can create a task within your existing permissions. Attachment metadata is available to authorized connections. Open attachments in TeamBoard." },
      { question: "How do Gemini Apps, API and CLI differ?", answer: "Gemini Apps is the consumer connection described above. Gemini API and Gemini CLI each have their own developer configuration and compatibility checks." },
    ],
    sdkGuide: "Gemini API documentation",
    cliGuide: "Gemini CLI documentation",
    contact: "Contact TeamBoard support",
  },
  fa: {
    title: "اتصال به هوش مصنوعی با MCP",
    description: "راهنمای اتصال تیم‌برد به هوش مصنوعی، ابزارهای موجود، دسترسی‌های حساب و مراحل تنظیم در ChatGPT، Claude و Gemini Apps.",
    lead: "کارها، اطلاعات پروژه‌ها و گفتگوهای تیم‌برد را در ابزار هوش مصنوعی‌تان بررسی کنید. پروتکل زمینهٔ مدل (MCP) راهی استاندارد برای درخواست اطلاعاتی است که حساب شما در تیم‌برد به آن‌ها دسترسی دارد.",
    seeSetup: "مشاهدهٔ راهنمای اتصال",
    developerGuide: "مستندات توسعه‌دهندگان",
    serverUrl: "نشانی سرور MCP",
    preview: "پیش‌نمایش محلی",
    previewDescription: "نشانی عمومی MCP تیم‌برد هنوز منتشر نشده است. توسعه‌دهندگان می‌توانند اتصال را با راهنمای اجرای محلی روی رایانهٔ خود آزمایش کنند.",
    endpointDescription: "این نشانی را در تنظیمات اتصال سفارشی ابزار هوش مصنوعی وارد کنید. تیم‌برد دسترسی را با OAuth تأیید می‌کند.",
    unverified: "اتصال در محیط محلی آزمایش شده است. سازگاری عملی با سرویس‌های آنلاین هوش مصنوعی هنوز تأیید نشده است.",
    copy: { action: "کپی نشانی", success: "نشانی سرور کپی شد.", failure: "نشانی را انتخاب کنید و دستی کپی کنید." },
    promptsTitle: "چه سؤال‌هایی می‌توانید بپرسید؟",
    promptsDescription: "فضاهای کاری، پروژه‌ها، گفتگوها، تقویم و گزارش‌های مجاز را بررسی کنید. با مجوز جداگانهٔ نوشتن می‌توانید کار و یادآور بسازید.",
    prompts: [
      { question: "کارهای عقب‌افتادهٔ من در فضای کاری وب‌سایت را نشان بده.", caption: "کارها و مهلت‌ها", icon: "board" },
      { question: "پیام‌های اخیر گفتگوی پروژهٔ بک‌اند را خلاصه کن.", caption: "گفتگوهای پروژه", icon: "chat" },
      { question: "پنج اعلان خوانده‌نشدهٔ آخر من چه هستند؟", caption: "صندوق اعلان‌ها", icon: "inbox" },
    ],
    setupTitle: "راهنمای اتصال به سرویس‌ها",
    setupDescription: "این مراحل تنظیمات اتصال سفارشی هر سرویس را توضیح می‌دهند. برای اتصال، نشانی عمومی تیم‌برد و حسابی با شرایط لازم نیاز است.",
    providerGuide: (name: string) => `راهنمای رسمی ${name}`,
    providers: {
      chatgpt: {
        availability: "اتصال کامل سفارشی در نسخهٔ وب برای طرح‌های Business و Enterprise/Edu تابع مجوزهای فضای کاری است. طرح Pro از ابزارهای خواندن و دریافت پشتیبانی می‌کند.",
        steps: [
          "در نسخهٔ وب ChatGPT به بخش Plugins بروید و Add custom MCP server را بزنید.",
          "نام TeamBoard و نشانی عمومی سرور را وارد کنید و OAuth را انتخاب کنید.",
          "هشدار ChatGPT را بخوانید، در تیم‌برد وارد شوید و دسترسی درخواستی را بررسی کنید. قبل از استفاده، ابزارهای شناسایی‌شده را بررسی کنید.",
        ],
      },
      claude: {
        availability: "Claude در طرح رایگان و پولی از اتصال سفارشی پشتیبانی می‌کند. حساب رایگان می‌تواند یک اتصال سفارشی داشته باشد. مجوزهای سازمانی و مناطق پشتیبانی‌شده نیز اعمال می‌شوند.",
        steps: [
          "در بخش Customize و سپس Connectors، یک اتصال سفارشی اضافه کنید. در طرح سازمانی ممکن است مدیر ابتدا اتصال را اضافه کند.",
          "نام TeamBoard و نشانی عمومی سرور را وارد کنید و تنظیمات شناسایی‌شدهٔ OAuth را بررسی کنید.",
          "در تیم‌برد وارد شوید و دسترسی درخواستی را بررسی کنید. سپس اتصال را در گفتگوی دلخواه فعال کنید.",
        ],
      },
      gemini: {
        availability: "گوگل فعلاً اتصال سفارشی را برای افراد بزرگسال در آمریکا با حساب شخصی، فعال بودن History و زبان انگلیسی ارائه می‌کند. تنظیم اتصال از نسخهٔ وب انجام می‌شود.",
        steps: [
          "در نسخهٔ وب Gemini به Settings و سپس Connected Apps بروید و بخش Custom apps را پیدا کنید.",
          "نشانی عمومی سرور را وارد کنید. اگر تنظیمات OAuth درخواست شد، از اطلاعاتی که تیم‌برد برای اتصال ارائه می‌کند استفاده کنید.",
          "در تیم‌برد وارد شوید و دسترسی درخواستی را بررسی کنید. برای استفاده در Gemini، اتصال را با نشانهٔ @ انتخاب کنید.",
        ],
      },
    },
    securityTitle: "دسترسی در اختیار شماست",
    security: "ورود و تأیید دسترسی در خود تیم‌برد انجام می‌شود. هر درخواست با اعتبارنامهٔ MCP و بر اساس مجوزهای فعلی حساب بررسی می‌شود. سرویس هوش مصنوعی انتخابی شما نتیجهٔ درخواست‌هایش را دریافت می‌کند. پیش از اشتراک اطلاعات فضای کاری، تنظیمات دادهٔ آن سرویس را بررسی کنید.",
    disconnectTitle: "قطع اتصال و لغو دسترسی",
    disconnect: "در تیم‌برد، بخش «امنیت» و سپس «اتصال‌های هوش مصنوعی» را باز کنید و دسترسی یک برنامه یا همهٔ برنامه‌ها را لغو کنید. سپس تیم‌برد را از تنظیمات سرویس هوش مصنوعی بردارید. داده‌های قبلاً ارسال‌شده را در تنظیمات همان سرویس مدیریت کنید.",
    privacy: "سیاست حریم خصوصی تیم‌برد",
    faqTitle: "سؤال‌های متداول و رفع مشکل",
    faq: [
      { question: "چرا گزینهٔ اتصال را پیدا نمی‌کنم؟", answer: "شرایط حساب، منطقه و فضای کاری را در راهنمای سرویس بررسی کنید. اگر حسابتان سازمانی است، از مدیر بخواهید مجوزهای اتصال را بررسی کند." },
      { question: "چرا اتصال برقرار نمی‌شود یا ابزارها نمایش داده نمی‌شوند؟", answer: "نشانی رسمی HTTPS را همراه مسیر کامل وارد کنید، فعال بودن اتصال را بررسی کنید و ورود به تیم‌برد را کامل کنید. سپس اتصال را در سرویس هوش مصنوعی فعال کنید." },
      { question: "هوش مصنوعی می‌تواند کار جدید بسازد یا فایلی دانلود کند؟", answer: "اتصال دارای مجوز نوشتن، در محدودهٔ دسترسی حسابتان می‌تواند کار بسازد. اتصال مجاز می‌تواند مشخصات پیوست را ببیند. برای باز کردن پیوست وارد تیم‌برد شوید." },
      { question: "تفاوت برنامهٔ Gemini با API و CLI چیست؟", answer: "برنامهٔ Gemini همان مسیر اتصال کاربران عادی است که در بالا توضیح داده شده. API و CLI هر کدام تنظیمات توسعه‌دهنده و بررسی سازگاری جداگانه دارند." },
    ],
    sdkGuide: "مستندات Gemini API",
    cliGuide: "مستندات Gemini CLI",
    contact: "تماس با پشتیبانی تیم‌برد",
  },
} satisfies Record<WebsiteLocale, McpPageCopy>;
