import { expect, test } from "@playwright/test";

test("reviewer can validate, find claims, and resume after refresh", async ({ page }) => {
  await page.goto("/?role=Reviewer");
  await page.getByRole("link", { name: "Review", exact: true }).click();

  await page.getByRole("button", { name: "Validate evidence links" }).click();
  await expect(page.getByText("Evidence checked", { exact: true }).first()).toBeVisible();
  await expect(page.getByText(/Extraction complete/i)).toHaveCount(0);

  await page.getByLabel("Search claim text").fill("Stripe");
  await page.getByLabel("Search claim text").press("Enter");
  await expect(page.getByText(/Showing claims 1–3 of 3 matching 13 total/)).toBeVisible();
  await expect(page.getByText("Evidence checked", { exact: true }).first()).toBeVisible();

  const workspaceUrl = page.url();
  await page.reload();
  await expect(page).toHaveURL(workspaceUrl);
  await expect(page).toHaveURL(/role=Reviewer/i);
  await page.getByLabel("Search claim text").fill("Stripe");
  await page.getByLabel("Search claim text").press("Enter");
  await expect(page.getByText(/Showing claims 1–3 of 3 matching 13 total/)).toBeVisible();
});
