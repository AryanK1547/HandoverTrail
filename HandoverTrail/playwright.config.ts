import { defineConfig } from "@playwright/test";
import { join } from "node:path";

const dataDirectory = process.env.HANDOVERTRAIL_E2E_DIR;
if (!dataDirectory) {
  throw new Error("Run browser tests through `npm run test:e2e` to isolate test data.");
}

const python = process.env.PYTHON
  ?? (process.platform === "win32"
    ? join(".venv", "Scripts", "python.exe")
    : join(".venv", "bin", "python"));
const port = Number(process.env.HANDOVERTRAIL_E2E_PORT);
if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error("The browser test launcher must provide a valid free port.");
}
const baseURL = `http://127.0.0.1:${port}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  reporter: [["list"]],
  use: {
    baseURL,
    browserName: "chromium",
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: `"${python}" -m streamlit run app.py --server.headless true --server.port ${port}`,
    url: `${baseURL}/_stcore/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      ...process.env,
      HANDOVERTRAIL_DB: join(dataDirectory, "handovertrail.db"),
      HANDOVERTRAIL_UPLOADS_DIR: join(dataDirectory, "uploads"),
      HANDOVERTRAIL_DISABLE_PROVIDERS: "1",
    },
  },
});
