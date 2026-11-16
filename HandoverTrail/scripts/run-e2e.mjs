import { spawnSync } from "node:child_process";
import { mkdtempSync, rmSync } from "node:fs";
import { createServer } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";

const dataDirectory = mkdtempSync(join(tmpdir(), "handovertrail-e2e-"));
const npmCli = process.env.npm_execpath;

async function findFreePort() {
  const server = createServer();
  await new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, "127.0.0.1", resolve);
  });
  const { port } = server.address();
  await new Promise((resolve, reject) => {
    server.close((error) => error ? reject(error) : resolve());
  });
  return port;
}

try {
  if (!npmCli) {
    throw new Error("npm did not provide its CLI path; unable to start Playwright.");
  }
  const port = await findFreePort();
  const result = spawnSync(
    process.execPath,
    [npmCli, "exec", "--", "playwright", "test"],
    {
      stdio: "inherit",
      env: {
        ...process.env,
        HANDOVERTRAIL_E2E_DIR: dataDirectory,
        HANDOVERTRAIL_E2E_PORT: String(port),
      },
    },
  );
  if (result.error) {
    throw result.error;
  }
  process.exitCode = result.status ?? 1;
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exitCode = 1;
} finally {
  rmSync(dataDirectory, { recursive: true, force: true });
}
