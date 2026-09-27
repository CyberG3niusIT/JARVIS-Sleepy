import { access, readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("../../", import.meta.url));
const frontendDist = path.join(projectRoot, ".output", "public");
const entryPath = path.join(frontendDist, "index.html");

try {
  const html = await readFile(entryPath, "utf8");
  const referencedFiles = [
    ...html.matchAll(/(?:src|href)="(\/(?:assets\/[^\"]+|favicon\.ico))"/g),
  ].map((match) => match[1]);

  if (!referencedFiles.some((file) => file.startsWith("/assets/"))) {
    throw new Error("index.html enthält keine gebündelten Assets.");
  }

  await Promise.all(referencedFiles.map((file) => access(path.join(frontendDist, file.slice(1)))));
  process.stdout.write(
    `Desktop-Frontend geprüft: index.html und ${referencedFiles.length} referenzierte Dateien vorhanden.\n`,
  );
} catch (error) {
  process.stderr.write(
    `Desktop-Frontend unvollständig (${entryPath}): ${error instanceof Error ? error.message : String(error)}\n`,
  );
  process.exitCode = 1;
}
