import fs from "fs";
import path from "path";

import { expect, test } from "@playwright/test";

const seed = JSON.parse(
  fs.readFileSync(path.join(process.cwd(), "e2e", ".seed.json"), "utf8"),
);

async function signIn(page: import("@playwright/test").Page, email: string, password: string) {
  await page.goto("/sign-in");
  await page.getByPlaceholder("Email").fill(email);
  await page.getByPlaceholder("Password").fill(password);
  await page.getByRole("button", { name: "Sign In" }).click();
  await page.waitForURL("**/");
}

test("regular user can browse seeded tasks and save preferences", async ({ page }) => {
  await signIn(page, seed.regular.email, seed.regular.password);

  await page.goto("/list");
  await expect(page.getByText(seed.completedSourceTitle)).toBeVisible();

  await page.goto(`/tasks/${seed.completedTaskId}`);
  await expect(page.getByText("This is a seeded clip")).toBeVisible();

  await page.goto("/settings");
  await page.getByRole("button", { name: /save preferences/i }).click();
  await expect(page.getByText(/preferences saved/i)).toBeVisible();

  await page.goto("/admin");
  await expect(page.getByText(/not an admin/i)).toBeVisible();
});


test("creator-focused clip setup requires source rights confirmation", async ({ page }) => {
  await signIn(page, seed.regular.email, seed.regular.password);
  await page.goto("/");

  await expect(page.getByText("Creator focus")).toBeVisible();
  const creatorSelect = page.getByRole("combobox").first();
  await creatorSelect.click();
  await page.getByRole("option", { name: /Kai Cenat/ }).click();
  await expect(creatorSelect).toContainText("Kai Cenat");

  await page.locator("#youtube-url").fill(
    "https://www.youtube.com/live/VZqAPdUvqnQ?si=playwright-test",
  );
  const submitButton = page.getByRole("button", { name: /process video/i });
  await expect(submitButton).toBeDisabled();

  await page.getByRole("checkbox").check();
  await expect(submitButton).toBeEnabled();
});

test("admin user can access the admin dashboard", async ({ page }) => {
  await signIn(page, seed.admin.email, seed.admin.password);

  await page.goto("/admin");
  await expect(page.getByText(/admin dashboard/i)).toBeVisible();
  await expect(
    page.getByRole("heading", { name: /currently processing tasks/i }),
  ).toBeVisible();
});
