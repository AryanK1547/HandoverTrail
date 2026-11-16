import { expect, test } from "@playwright/test";

test("upload to acknowledged handover works end to end in one workspace", async ({ page }) => {
  test.setTimeout(180_000);

  // Connect: start from the landing page and upload two public sources.
  await page.goto("/?role=Reviewer");
  await page.getByRole("link", { name: "Upload your own files →" }).click();
  await page.getByRole("tab", { name: "Upload files" }).click();
  await page.locator('input[type="file"]').setInputFiles([
    {
      name: "notes.md",
      mimeType: "text/markdown",
      buffer: Buffer.from(
        "Payment webhook owner is Priya Shah.\nDecision: Use Redis for webhook idempotency.\n",
      ),
    },
    {
      name: "chat.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("Payment webhook owner is Alex Chen.\n"),
    },
  ]);
  await expect(page.getByText("chat.txt")).toBeVisible();
  // The dropdown can close while the upload settles, so reopen it until it stays open.
  const publicOption = page.getByRole("option", { name: "Public" });
  await expect(async () => {
    if (!(await publicOption.isVisible())) {
      await page.getByRole("combobox", { name: /Source sensitivity/ }).click();
    }
    await expect(publicOption).toBeVisible({ timeout: 2_000 });
  }).toPass({ timeout: 30_000 });
  await publicOption.click();
  await expect(page.getByRole("combobox", { name: /Source sensitivity/ })).toHaveValue(
    "Public",
  );
  await page.getByRole("button", { name: "Save and process uploaded files" }).click();
  await expect(page).toHaveURL(/workspace=[0-9a-f]{32}/i);
  await expect(page.getByText(/Saved 2 of 2 file\(s\)/).first()).toBeVisible();
  const workspace = new URL(page.url()).searchParams.get("workspace");

  // Reconstruct and verify: extraction validates evidence links automatically.
  await page
    .getByRole("link", { name: "Continue: extract claims from these sources →" })
    .click();
  await page.getByRole("button", { name: "Extract claims" }).click();
  await expect(page.getByText(/Extraction complete/i)).toBeVisible();
  await expect(page.getByText(/Showing claims 1–3 of 3 matching 3 total/)).toBeVisible();
  await expect(page.getByText("Not validated", { exact: true })).toHaveCount(0);
  await expect(page.getByText(/Conflicts and gaps · 1 unresolved conflict\(s\)/)).toBeVisible();

  // Review: approve every candidate claim.
  for (let remaining = 3; remaining > 0; remaining -= 1) {
    await expect(page.getByRole("button", { name: "Approve claim" })).toHaveCount(remaining);
    await page.getByRole("button", { name: "Approve claim" }).first().click();
  }
  await expect(page.getByText(/The review queue is clear/)).toBeVisible();

  // Interview: turn gaps into questions and send them to Departing.
  await page.getByRole("link", { name: "Prepare exit interview →" }).click();
  await page.getByRole("button", { name: "Generate questions from open gaps" }).click();
  await page.getByRole("button", { name: /Send \d+ draft question\(s\) to Departing/ }).click();
  await expect(page.getByText(/question\(s\) are waiting for an answer/)).toBeVisible();

  await page.goto(`/Exit_Interview?workspace=${workspace}&role=Departing`);
  await page.getByLabel("Your answer").first().fill(
    "Priya Shah owns the payment webhook because she built the integration.",
  );
  await page.getByRole("button", { name: "Submit answer" }).first().click();
  await expect(
    page.getByText("Your answer has been saved for reviewer follow-up."),
  ).toBeVisible();

  // Departing has no handover access and gets guidance instead of an error.
  await page.goto(`/Handover_View?workspace=${workspace}&role=Departing`);
  await expect(page.getByText(/The handover is released by Admin or Reviewer/)).toBeVisible();
  await expect(page.getByText(/PermissionError|Traceback/)).toHaveCount(0);

  // The answer became a pending claim for the reviewer.
  await page.goto(`/Review_Claims?workspace=${workspace}&role=Reviewer`);
  await expect(page.getByRole("button", { name: "Approve claim" })).toHaveCount(1);
  await page.getByRole("button", { name: "Approve claim" }).click();
  await expect(page.getByText(/The review queue is clear/)).toBeVisible();

  // Handover: the restricted interview claim is excluded from the release.
  await page.getByRole("link", { name: "Continue: release the handover →" }).click();
  await expect(page.getByText(/What the next release would contain/)).toBeVisible();
  await page.getByRole("button", { name: "Release current approved handover" }).click();
  await expect(page.getByText(/3 approved claim\(s\) with public evidence/)).toBeVisible();
  await expect(page.getByText(/1 approved claim\(s\) are excluded/)).toBeVisible();
  await page.getByRole("button", { name: "Confirm release" }).click();
  await expect(page.getByText(/Latest release: version 1/)).toBeVisible();

  // Incoming reads and acknowledges the fixed snapshot.
  await page.goto(`/Handover_View?workspace=${workspace}&role=Incoming`);
  await expect(page.getByText("Where to pick up")).toBeVisible();
  await expect(page.getByText(/Showing claims 1–3 of 3\./)).toBeVisible();
  await page.getByRole("button", { name: /Acknowledge receipt of version 1/ }).click();
  await expect(page.getByText(/You acknowledged version 1/)).toBeVisible();

  await page.goto(`/?workspace=${workspace}&role=Reviewer`);
  await expect(
    page.getByText(/Handover version 1 is released and up to date\. Incoming has acknowledged it\./),
  ).toBeVisible();
});
