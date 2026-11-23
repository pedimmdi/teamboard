import { existsSync } from "node:fs";
import { join } from "node:path";

export function persianFontAssets() {
  if (process.env.IRANSANSX_WEBFONT === "0") return { enabled: false, stylesheet: false };
  const directory = join(process.cwd(), "public", "fonts", "iransansx");
  const stylesheet = existsSync(join(directory, "faces.css"));
  return {
    enabled: stylesheet || process.env.IRANSANSX_WEBFONT === "1",
    stylesheet,
  };
}
