import { expect, test } from "@playwright/test";

test("a judge starts a private copy and the tour tracks real progress", async ({ page }) => {
  // The landing page offers the tour first.
  await page.goto("/?role=Reviewer");
  await page.getByRole("link", { name: "Start the guided tour →" }).click();
  await expect(page.getByRole("heading", { name: "Start with your own copy" })).toBeVisible();

  await page.getByRole("button", { name: "Start my private demo copy" }).click();
  await expect(page).toHaveURL(/workspace=[0-9a-f]{32}/i);
  const workspace = new URL(page.url()).searchParams.get("workspace");
  await expect(page.getByText("1 of 9 steps complete")).toBeVisible();
  await expect(page.getByText(/Next: Verify the claims against their evidence/)).toBeVisible();

  // Step 2's link opens the Review page in the same private workspace.
  await page.getByRole("link", { name: "Open as Reviewer →" }).nth(1).click();
  await expect(page).toHaveURL(new RegExp(`Review_Claims.*workspace=${workspace}`));
  await expect(page.getByText(/Active workspace: Upload workspace/)).toBeVisible();
  await page.getByRole("button", { name: "Validate evidence links" }).click();
  await expect(page.getByText(/Last verified/)).toBeVisible();

  // Back on the tour, the completed step is recognised from stored data.
  await page.getByRole("link", { name: "Guided tour", exact: true }).first().click();
  await expect(page.getByText("2 of 9 steps complete")).toBeVisible();
  await expect(page.getByText(/Next: Resolve a conflict/)).toBeVisible();

  // The role links for later steps switch role and keep the workspace.
  await page.getByRole("link", { name: "Open as Departing →" }).click();
  await expect(page).toHaveURL(new RegExp(`Exit_Interview.*workspace=${workspace}`));
  await expect(page.getByText("Questions assigned to you")).toBeVisible();
  await expect(page.getByText(/Traceback|PermissionError/)).toHaveCount(0);
});
