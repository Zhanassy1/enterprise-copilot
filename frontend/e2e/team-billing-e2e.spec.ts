/**
 * End-to-end: team (members, invites, matrix) и billing (план, сравнение) на реальном API.
 * Запуск: поднять API + фронт, затем `npm run test:e2e:integrated` (см. package.json).
 * Без API тесты пропускаются (healthz).
 */
import { expect, test } from "@playwright/test";

const API_BASE = process.env.E2E_API_URL ?? "http://127.0.0.1:8000/api/v1";
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

test.describe.configure({ mode: "serial" });

test.describe("team and billing (API + UI)", () => {
  const password = `E2eTb_${Date.now().toString(36)}_Aa1!`;
  let email = "";
  let apiReachable = false;

  test.beforeAll(async ({ request }) => {
    try {
      const health = await request.get(`${API_ORIGIN}/healthz`, { timeout: 5_000 });
      apiReachable = health.ok();
    } catch {
      apiReachable = false;
    }
    if (!apiReachable) return;

    email = `e2e-tb-${Date.now()}@example.com`;
    const reg = await request.post(`${API_BASE}/auth/register`, {
      headers: { "Content-Type": "application/json" },
      data: { email, password, full_name: "E2E Team Billing" },
    });
    if (!reg.ok()) {
      throw new Error(`register failed: ${reg.status()} ${await reg.text()}`);
    }
  });

  test.beforeEach(async () => {
    test.skip(!apiReachable, "API not reachable — start backend and set E2E_API_URL if needed");
  });

  test("team page: members, invites, role matrix", async ({ page }) => {
    await page.goto("/login", { waitUntil: "load" });
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL(/\/w\/[^/]+\/documents/, { timeout: 30_000 });

    const slug = new URL(page.url()).pathname.match(/^\/w\/([^/]+)\//)?.[1];
    expect(slug, "workspace slug").toBeTruthy();

    await page.goto(`/w/${slug}/team`, { waitUntil: "load" });
    await expect(page.getByRole("heading", { name: "Команда и доступ" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Участники workspace", { exact: true })).toBeVisible();
    await expect(page.getByRole("columnheader", { name: "Участник" })).toBeVisible({ timeout: 20_000 });
    await expect(page.getByText("Ожидающие приглашения", { exact: true })).toBeVisible();
    await expect(page.getByText("Матрица ролей", { exact: true })).toBeVisible();
  });

  test("billing page: plan block and comparison", async ({ page }) => {
    await page.goto("/login", { waitUntil: "load" });
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL(/\/w\/[^/]+\/documents/, { timeout: 30_000 });

    const slug = new URL(page.url()).pathname.match(/^\/w\/([^/]+)\//)?.[1];
    expect(slug, "workspace slug").toBeTruthy();

    await page.goto(`/w/${slug}/billing`, { waitUntil: "load" });
    await expect(page.getByRole("heading", { name: "План и лимиты" })).toBeVisible({ timeout: 15_000 });

    await expect(page.getByText("Текущий план workspace", { exact: true })).toBeVisible({ timeout: 25_000 });
    await expect(page.getByRole("heading", { name: "Три уровня — один продукт", exact: true })).toBeVisible();
  });

  test("legacy flat /team redirects to /w/:slug/team", async ({ page }) => {
    await page.goto("/login", { waitUntil: "load" });
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL(/\/w\/[^/]+\/documents/, { timeout: 30_000 });

    await page.goto("/team", { waitUntil: "load" });
    await page.waitForURL(/\/w\/[^/]+\/team/, { timeout: 20_000 });
    await expect(page.getByRole("heading", { name: "Команда и доступ" })).toBeVisible({ timeout: 15_000 });
  });
});
