import { expect, test } from "@playwright/test";

test("auth pages render", async ({ page }) => {
  await page.goto("/login");
  await expect(page).toHaveURL(/login/);
  await expect(page.getByText(/вход|login/i)).toBeVisible();

  await page.goto("/register");
  await expect(page).toHaveURL(/register/);
  await expect(page.getByText(/регист|register/i)).toBeVisible();
});
