import { expect, test } from "@playwright/test";

test("uploads stay isolated, are resumable, and do not show demo claims", async ({ page }) => {
  await page.goto("/Upload_Sources?role=Reviewer");
  await page.getByRole("tab", { name: "Upload files" }).click();
  await expect(page.getByText(/Active workspace: Demo project/)).toBeVisible();
  await page.locator('input[type="file"]').setInputFiles({
    name: "custom.md",
    mimeType: "text/markdown",
    buffer: Buffer.from(
      "# Custom workspace brief\n\nThe project confirmed ZebraDB is used.",
    ),
  });
  await page.getByRole("button", { name: "Save and process uploaded files" }).click();
  await expect(page).toHaveURL(/workspace=[0-9a-f]{32}/i);
  await expect(page.getByText(/Active workspace: Upload workspace/)).toBeVisible();
  const originalUploadUrl = page.url();
  const originalWorkspace = new URL(originalUploadUrl).searchParams.get("workspace");

  await page.getByRole("link", { name: "Review", exact: true }).click();
  await expect(page.getByText(/Active workspace: Upload workspace/)).toBeVisible();
  await expect(page.getByText(/Cached synthetic demo claims/)).toHaveCount(0);
  await page.getByRole("button", { name: "Extract claims" }).click();
  await expect(
    page.getByText(/Extraction complete · Universal Keyword Fallback/i),
  ).toBeVisible();
  await expect(page.getByText(/Showing claims 1–1 of 1 matching 1 total/)).toBeVisible();
  await expect(
    page.getByText("The project confirmed ZebraDB is used.", { exact: true }).first(),
  ).toBeVisible();
  await expect(page.getByText(/Project decision identified/)).toHaveCount(0);
  await expect(page.getByText(/Stripe as payment processor/i)).toHaveCount(0);

  const originalReviewUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(originalReviewUrl);
  await expect(page.getByText(/Showing claims 1–1 of 1 matching 1 total/)).toBeVisible();

  const url = new URL("/Upload_Sources", originalUploadUrl);
  await page.goto(url.toString());
  await page.getByRole("tab", { name: "Upload files" }).click();
  await page.getByRole("button", { name: "Start a new upload workspace" }).click();
  await expect(page).toHaveURL(/workspace=[0-9a-f]{32}/i);
  const secondWorkspace = new URL(page.url()).searchParams.get("workspace");
  expect(secondWorkspace).not.toBe(originalWorkspace);
  await expect(page.getByText(/No sources are available in this workspace\./i)).toBeVisible();

  await page.goto(originalReviewUrl);
  await expect(page.getByText(/Showing claims 1–1 of 1 matching 1 total/)).toBeVisible();
});
