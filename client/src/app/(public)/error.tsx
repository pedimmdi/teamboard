"use client";
export default function WebsiteError({ reset }: { reset: () => void }) {
  return (
    <section style={{ padding: 40 }} role="alert">
      <h1>This page is temporarily unavailable</h1>
      <p>Please try again in a moment.</p>
      <button onClick={reset}>Try again</button>
    </section>
  );
}
