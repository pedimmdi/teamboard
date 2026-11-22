import type { Locale } from "@/lib/locale";

const persianMessages: Readonly<Record<string, string>> = {
  "A user with this email already exists.": "این نشانی ایمیل قبلاً ثبت شده است.",
  "No active account found with the given credentials.": "ایمیل یا گذرواژه درست نیست.",
  "Email address is not verified.": "ابتدا نشانی ایمیل‌تان را تأیید کنید.",
  "Email address is already verified.": "این نشانی ایمیل قبلاً تأیید شده است.",
  "Invalid verification link.": "پیوند تأیید نامعتبر است.",
  "Invalid or expired verification link.": "پیوند تأیید نامعتبر یا منقضی است.",
  "Invalid password reset link.": "پیوند بازنشانی گذرواژه نامعتبر است.",
  "Invalid or expired password reset link.": "پیوند بازنشانی گذرواژه نامعتبر یا منقضی است.",
  "Password has been reset successfully.": "گذرواژه‌تان بازنشانی شد.",
  "If an account exists for this email, a password reset link has been sent.": "اگر حسابی با این ایمیل وجود داشته باشد، پیوند بازنشانی گذرواژه ارسال شده است.",
  "Passwords do not match.": "گذرواژه‌ها یکسان نیستند.",
  "Current password is incorrect.": "گذرواژه فعلی درست نیست.",
  "Choose a different password.": "گذرواژه دیگری انتخاب کنید.",
  "This password is too common.": "این گذرواژه بسیار رایج است.",
  "This password is entirely numeric.": "گذرواژه نمی‌تواند فقط از اعداد تشکیل شود.",
  "This field is required.": "این فیلد الزامی است.",
  "This field may not be blank.": "این فیلد نباید خالی باشد.",
  "Enter a valid email address.": "نشانی ایمیل معتبر وارد کنید.",
  "Invalid or expired invitation token.": "پیوند دعوت نامعتبر یا منقضی است.",
  "This invitation has expired.": "این دعوت منقضی شده است.",
  "This invitation is not for your email address.": "این دعوت برای نشانی ایمیل شما نیست.",
  "Profile images must be 5 MB or smaller.": "حجم عکس نمایه باید حداکثر ۵ مگابایت باشد.",
  "Upload a JPEG, PNG, or WebP image with the correct extension.": "یک تصویر JPEG، PNG یا WebP با پسوند درست بارگذاری کنید.",
  "Upload a valid JPEG, PNG, or WebP image.": "یک تصویر معتبر JPEG، PNG یا WebP بارگذاری کنید.",
  "Profile images must be 4096 × 4096 pixels or smaller.": "ابعاد عکس نمایه باید حداکثر ۴۰۹۶ × ۴۰۹۶ پیکسل باشد.",
  "Could not create an workspace. Please try again.": "فضای کاری ایجاد نشد. دوباره تلاش کنید.",
  "Session not found.": "نشست پیدا نشد.",
};

export function localizeAccountMessage(locale: Locale, message: string, fallback = "عملیات انجام نشد. دوباره تلاش کنید.") {
  if (locale === "en" || !message || /[\u0600-\u06ff]/.test(message)) return message;
  const shortPassword = message.match(/^This password is too short\. It must contain at least (\d+) characters\.$/);
  if (shortPassword) {
    return `گذرواژه باید دست‌کم ${new Intl.NumberFormat("fa-IR").format(Number(shortPassword[1]))} نویسه داشته باشد.`;
  }
  return Object.hasOwn(persianMessages, message) ? persianMessages[message] : fallback;
}
