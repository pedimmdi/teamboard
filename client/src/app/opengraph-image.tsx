import { ImageResponse } from "next/og";
export const alt = "TeamBoard — Plan work. Ship together.";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export default function OpenGraphImage() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "#1e1b4b",
          color: "white",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "center",
          padding: 90,
        }}
      >
        <div style={{ fontSize: 32, color: "#c7d2fe", marginBottom: 35 }}>
          TeamBoard
        </div>
        <div style={{ fontSize: 80, fontWeight: 700 }}>Plan work.</div>
        <div style={{ fontSize: 80, fontWeight: 700 }}>Ship together.</div>
        <div style={{ fontSize: 27, color: "#c7d2fe", marginTop: 35 }}>
          Projects, tasks and conversations in one workspace.
        </div>
      </div>
    ),
    size,
  );
}
