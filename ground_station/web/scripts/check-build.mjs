// Verifies the committed build (../static/app) matches a fresh `vite build` of the current source.
import { execSync } from "node:child_process";
import { mkdtempSync, readdirSync, readFileSync, rmSync } from "node:fs";
import os from "node:os";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname);
const committed = path.resolve(here, "../../static/app");
const fresh = mkdtempSync(path.join(os.tmpdir(), "gs-build-"));
const list = (d) => readdirSync(d, { recursive: true }).map(String).filter((f) => f.includes(".")).sort();
try {
  execSync(`npx vite build --outDir "${fresh}" --emptyOutDir`, { cwd: path.resolve(here, ".."), stdio: "ignore" });
  const a = list(committed), b = list(fresh);
  const sameFiles = JSON.stringify(a) === JSON.stringify(b);
  const sameIndex = readFileSync(path.join(committed, "index.html"), "utf8") === readFileSync(path.join(fresh, "index.html"), "utf8");
  if (!sameFiles || !sameIndex) {
    console.error("Committed build is stale. Run `npm run build` and commit ground_station/static/app.");
    console.error("only in committed:", a.filter((f) => !b.includes(f)));
    console.error("only in fresh:", b.filter((f) => !a.includes(f)));
    process.exit(1);
  }
  console.log(`build check OK (${a.length} files)`);
} finally {
  rmSync(fresh, { recursive: true, force: true });
}
