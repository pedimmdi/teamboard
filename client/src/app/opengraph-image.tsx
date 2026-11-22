import { ImageResponse } from "next/og";

export const alt = "TeamBoard — Plan work. Ship together.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", width: "100%", height: "100%", padding: 82, color: "#effbf6", background: "#153631" }}>
        <div style={{ display: "flex", alignItems: "center", fontSize: 30, marginBottom: 44 }}>
          <div style={{ display: "flex", alignItems: "flex-end", gap: 4, padding: 10, marginRight: 15, borderRadius: 11, background: "#9ee5c8" }}>
            <div style={{ width: 6, height: 15, borderRadius: 2, background: "#153631" }} />
            <div style={{ width: 6, height: 23, borderRadius: 2, background: "#153631" }} />
            <div style={{ width: 6, height: 18, borderRadius: 2, background: "#153631" }} />
          </div>
          TeamBoard
        </div>
        <div style={{ fontSize: 98, fontWeight: 700, lineHeight: 1.05, letterSpacing: -6 }}>Plan work.</div>
        <div style={{ fontSize: 98, fontWeight: 700, lineHeight: 1.05, letterSpacing: -6, color: "#9ee5c8" }}>Ship together.</div>
        <div style={{ fontSize: 30, color: "#c9e0d7", marginTop: 36 }}>Projects, tasks and conversations in one workspace.</div>
        <div style={{ position: "absolute", bottom: 0, right: 0, width: 260, height: 14, background: "#ffce8c" }} />
      </div>
    ),
    size,
  );
}
