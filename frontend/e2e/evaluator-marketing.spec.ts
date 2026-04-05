/**
 * Статический контур демо: маркетинг, якорь «1 минута», тарифы.
 * Запускается против `next start` или dev — без API.
 */
import { expect, test } from "@playwright/test";

test.describe("evaluator marketing & demo entry", () => {
  test("landing: hero, demo block, primary CTAs", async ({ page }) => {
    await page.goto("/", { waitUntil: "load" });
    await expect(page.locator("main h1")).toContainText(/Находите ответы в своих документах/i, {
      timeout: 20_000,
    });
    await expect(page.getByRole("link", { name: /Демо за 1 минуту/i })).toBeVisible();

    const demo = page.locator("#demo-quick-1min");
    await expect(demo.getByRole("heading", { name: "Демо за одну минуту" })).toBeVisible();
    await expect(demo.getByRole("link", { name: /Скриншоты на GitHub/i })).toBeVisible();
    await expect(demo.getByRole("link", { name: /README: 5 минут/i })).toBeVisible();

    await expect(page.getByRole("link", { name: /Попробовать бесплатно/i })).toBeVisible();
    await expect(page.getByRole("link", { name: /Смотреть тарифы/i })).toBeVisible();
  });

  test("pricing: plans and evaluator links", async ({ page }) => {
    await page.goto("/pricing", { waitUntil: "load" });
    await expect(page.getByRole("main").getByText("Тарифы", { exact: true })).toBeVisible();
    await expect(page.getByRole("heading", { name: /Планы Free, Pro и Team/i })).toBeVisible();

    await expect(page.locator("#pricing-plan-free")).toBeVisible();
    await expect(page.locator("#pricing-plan-pro")).toBeVisible();
    await expect(page.locator("#pricing-plan-team")).toBeVisible();

    await expect(page.getByRole("link", { name: /Чек-лист оценки за 5 минут/i })).toBeVisible();
  });
});
