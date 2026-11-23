"use client";

import { BoundaryError } from "@/components/route-feedback";

export default function AppError(props: { retry?: () => void; reset?: () => void }) {
  return <main><BoundaryError {...props} /></main>;
}
