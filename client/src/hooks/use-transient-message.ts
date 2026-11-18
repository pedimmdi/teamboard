"use client";

import { useCallback, useEffect, useRef, useState } from "react";

export function useTransientMessage<T extends string | null>(empty: T, duration = 5000) {
  const [message, setMessage] = useState<T>(empty);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const update = useCallback((value: T) => {
    if (timer.current !== null) clearTimeout(timer.current);
    setMessage(value);
    timer.current = value ? setTimeout(() => {
      setMessage(empty);
      timer.current = null;
    }, duration) : null;
  }, [empty, duration]);

  useEffect(() => () => {
    if (timer.current !== null) clearTimeout(timer.current);
  }, []);

  return [message, update] as const;
}
