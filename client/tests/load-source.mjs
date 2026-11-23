import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Script } from "node:vm";
import ts from "typescript";

const scripts = new Map();

export function loadSource(path, globals = {}) {
  const filename = fileURLToPath(new URL(path, import.meta.url));
  let script = scripts.get(filename);
  if (!script) {
    const { outputText } = ts.transpileModule(readFileSync(filename, "utf8"), {
      fileName: filename,
      compilerOptions: {
        module: ts.ModuleKind.CommonJS,
        target: ts.ScriptTarget.ES2022,
        jsx: ts.JsxEmit.React,
        esModuleInterop: true,
        inlineSourceMap: true,
        inlineSources: true,
      },
    });
    // Give V8 a real source filename so the unit run can report coverage for
    // modules executed in isolated contexts with injected dependencies.
    script = new Script(outputText, { filename });
    scripts.set(filename, script);
  }

  const exports = {};
  script.runInNewContext({ exports, ...globals });
  return exports;
}
