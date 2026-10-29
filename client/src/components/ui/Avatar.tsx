"use client";

import Image from "next/image";
import { useState } from "react";

export default function Avatar({
  src,
  fallback,
  className,
  size = 36,
}: {
  src?: string | null;
  fallback: string;
  className?: string;
  size?: number;
}) {
  const [failedSrc, setFailedSrc] = useState<string | null>(null);

  return (
    <span className={className} style={{ overflow: "hidden", flexShrink: 0 }}>
      {src && failedSrc !== src ? (
        <Image
          src={src}
          alt="Profile picture"
          width={size}
          height={size}
          unoptimized
          style={{ width: "100%", height: "100%", objectFit: "cover" }}
          onError={() => setFailedSrc(src)}
        />
      ) : (
        fallback
      )}
    </span>
  );
}
