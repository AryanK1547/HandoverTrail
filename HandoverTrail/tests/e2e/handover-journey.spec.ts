import { expect, test } from "@playwright/test";

test("reviewer releases a cited handover and Incoming acknowledges it", async ({ page }) => {
  await page.goto("/?workspace=demo&role=Reviewer");
  await page.getByRole("link", { name: "Review", exact: true }).click();
  await page.getByRole("button", { name: "Validate evidence links" }).click();
  await expect(page.getByText("Evidence checked", { exact: true }).first()).toBeVisible();

  await page.getByLabel("Search claim text").fill("Payment webhook owner is Alex Chen");
  await page.getByLabel("Search claim text").press("Enter");
  await expect(page.getByText(/Showing claims 1–1 of 1 matching 13 total/)).toBeVisible();
  await page.getByRole("button", { name: "Approve claim" }).click();
  await expect(page.getByRole("button", { name: "Approve claim" })).toHaveCount(0);
  await page.reload();
  await expect(page.getByText("1 approved", { exact: true })).toBeVisible();
  await page.getByLabel("Search claim text").fill("Payment webhook owner is Alex Chen");
  await page.getByLabel("Search claim text").press("Enter");
  await expect(page.getByText(/Showing claims 1–1 of 1 matching 13 total/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve claim" })).toHaveCount(0);
  await page.getByRole("link", { name: "Handover", exact: true }).click();
  await page.getByRole("button", { name: "Release current approved handover" }).click();
  await expect(page.getByText(/Latest release: version 1/)).toBeVisible();

  await page.goto("/Handover_View?workspace=demo&role=Incoming");
  await expect(
    page.getByText(/latest fixed snapshot a Reviewer approved for release/i),
  ).toBeVisible();

  await page.goto("/Upload_Sources?workspace=demo&role=Incoming");
  await expect(page.getByText("Only Admin or Reviewer can add or parse sources.")).toBeVisible();
  await expect(page.locator('input[type="file"]')).toHaveCount(0);
  await page.goto("/Review_Claims?workspace=demo&role=Incoming");
  await expect(
    page.getByText("Incoming does not review candidate claims. Only a released snapshot is shown."),
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Approve claim" })).toHaveCount(0);

  await page.goto("/Handover_View?workspace=demo&role=Incoming");
  await page.getByRole("button", { name: /Acknowledge receipt of version 1/ }).click();
  await expect(page.getByText(/You acknowledged version 1/)).toBeVisible();
});
