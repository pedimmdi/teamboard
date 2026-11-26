import { existsSync } from "node:fs";
import { join } from "node:path";

const fallback = "/fonts/open/vazirmatn-arabic-wght-normal.woff2";
const licensedRegular = "/fonts/iransansx/IRANSansXFaNum-Regular.woff2";

export function persianFontAssets() {
  if (process.env.IRANSANSX_WEBFONT === "0") {
    return { enabled: false, stylesheet: false, regularHref: fallback };
  }
  const directory = join(process.cwd(), "public", "fonts", "iransansx");
  const stylesheet = existsSync(join(directory, "faces.css"));
  const enabled = stylesheet || process.env.IRANSANSX_WEBFONT === "1";
  return {
    enabled,
    stylesheet,
    // The installer guarantees the regular face. Legacy installations still load it via CSS.
    regularHref: stylesheet ? licensedRegular : enabled ? null : fallback,
  };
}
