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


test("user can confirm rights and upload a generated clip to a connected YouTube channel", async ({ page }) => {
  const uploadPayloads: Record<string, unknown>[] = [];

  await page.route("**/api/youtube/status", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        connected: true,
        channel: {
          id: "UCmovieShortsTest",
          title: "Movie Shorts E2E Channel",
          connected_at: new Date().toISOString(),
        },
      }),
    });
  });

  await page.route("**/api/youtube/upload", async (route) => {
    uploadPayloads.push(route.request().postDataJSON() as Record<string, unknown>);
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({
        uploaded: true,
        video_id: "e2eShortVideo123",
        video_url: "https://www.youtube.com/watch?v=e2eShortVideo123",
        privacy_status: "private",
      }),
    });
  });

  await page.route("**/api/youtube/disconnect", async (route) => {
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ connected: false }),
    });
  });

  await signIn(page, seed.regular.email, seed.regular.password);
  await page.goto(`/tasks/${seed.completedTaskId}`);

  await expect(page.getByText("Connected to")).toContainText("Movie Shorts E2E Channel");
  const uploadButton = page.getByRole("button", { name: /upload to youtube/i }).first();
  await uploadButton.click();

  const rightsCheckbox = page.getByLabel(/I own this video or have permission from the rights holder/i).first();
  await expect(rightsCheckbox).not.toBeChecked();

  const confirmButton = page.getByRole("button", { name: /confirm upload/i }).first();
  await expect(confirmButton).toBeDisabled();
  await rightsCheckbox.check();
  await expect(confirmButton).toBeEnabled();
  await confirmButton.click();

  await expect(page.getByRole("link", { name: /view on youtube/i }).first()).toHaveAttribute(
    "href",
    "https://www.youtube.com/watch?v=e2eShortVideo123",
  );
  expect(uploadPayloads).toHaveLength(1);
  expect(uploadPayloads[0]).toMatchObject({
    rights_confirmed: true,
    privacy_status: "private",
  });
  expect(uploadPayloads[0].clip_id).toBeTruthy();
  expect(uploadPayloads[0].title).toBeTruthy();

  await page.goto("/settings");
  await expect(page.getByText("Connected to")).toContainText("Movie Shorts E2E Channel");
  await page.getByRole("button", { name: /disconnect/i }).click();
  await expect(page.getByRole("button", { name: /connect youtube/i })).toBeVisible();
});
