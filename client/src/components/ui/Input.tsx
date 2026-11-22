"use client";

import type { InputHTMLAttributes } from "react";

type InputProps = InputHTMLAttributes<HTMLInputElement> & {
  label: string;
  error?: string;
};

export default function Input({
  label,
  error,
  id,
  ...props
}: InputProps) {
  return (
    <div className="input-field">
      <label htmlFor={id}>{label}</label>

      <input
        id={id}
        dir={props.type === "email" ? "ltr" : undefined}
        aria-invalid={Boolean(error)}
        aria-describedby={id && error ? `${id}-error` : undefined}
        {...props}
      />

      {error && <p id={id ? `${id}-error` : undefined} className="input-error">{error}</p>}
    </div>
  );
}
