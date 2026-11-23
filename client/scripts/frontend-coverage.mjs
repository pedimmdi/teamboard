import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";

const report = "coverage/lcov.info";
mkdirSync("coverage", { recursive: true });
rmSync(report, { force: true });

const result = spawnSync(process.execPath, [
  "--enable-source-maps",
  "--experimental-test-coverage",
  "--test-coverage-include=src/**",
  "--test-reporter=spec",
  "--test-reporter-destination=stdout",
  "--test-reporter=lcov",
  `--test-reporter-destination=${report}`,
  "--test",
  "tests/*.test.mjs",
], { stdio: "inherit" });
if (result.error) throw result.error;

if (existsSync(report)) {
  // Node's LCOV reporter can emit branch positions for generated JavaScript
  // that have no corresponding TypeScript line. Keep the mapped data valid.
  const coverage = readFileSync(report, "utf8").split("end_of_record");
  const mapped = coverage.map((record) => {
    const validBranches = record.match(/^BRDA:\d+,.*$/gm) ?? [];
    const coveredBranches = validBranches.filter((branch) => Number(branch.trimEnd().split(",").at(-1)) > 0);
    return record
      .replace(/^BRDA:(?!\d+,).*\r?\n/gm, "")
      .replace(/^BRF:\d+/m, `BRF:${validBranches.length}`)
      .replace(/^BRH:\d+/m, `BRH:${coveredBranches.length}`);
  });
  writeFileSync(report, mapped.join("end_of_record"));
}

process.exitCode = result.status ?? 1;
