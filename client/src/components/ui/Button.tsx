"use client";

import { useLocale } from "@/lib/preferences";
import type { ButtonHTMLAttributes } from "react";

type ButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
};

export default function Button({
  children,
  loading = false,
  disabled,
  ...props
}: ButtonProps) {
  const { t } = useLocale();
  return (
    <button
      disabled={disabled || loading}
      {...props}
    >
      {loading ? t("Loading...", "در حال بارگیری…") : children}
    </button>
  );
}