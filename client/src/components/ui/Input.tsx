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
        aria-invalid={Boolean(error)}
        {...props}
      />

      {error && <p className="input-error">{error}</p>}
    </div>
  );
}