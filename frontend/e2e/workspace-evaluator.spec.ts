/**
 * Пятиминутный контур приложения: регистрация через API, вход, ключевые экраны workspace.
 * Требуется стек с API (`E2E_API_URL`, по умолчанию http://127.0.0.1:8000/api/v1).
 * Если /healthz недоступен — весь describe пропускается (удобно для CI без бэкенда).
 */
import { expect, test } from "@playwright/test";

const API_BASE = process.env.E2E_API_URL ?? "http://127.0.0.1:8000/api/v1";
const API_ORIGIN = API_BASE.replace(/\/api\/v1\/?$/, "");

test.describe.configure({ mode: "serial" });

test.describe("workspace evaluator (API + UI)", () => {
  const password = `E2eWs_${Date.now().toString(36)}_Aa1!`;
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

    email = `e2e-eval-${Date.now()}@example.com`;
    const reg = await request.post(`${API_BASE}/auth/register`, {
      headers: { "Content-Type": "application/json" },
      data: { email, password, full_name: "E2E Evaluator" },
    });
    if (!reg.ok()) {
      throw new Error(`register failed: ${reg.status()} ${await reg.text()}`);
    }
  });

  test.beforeEach(async () => {
    test.skip(!apiReachable, "API not reachable — start docker compose and set E2E_API_URL if needed");
  });

  test("login and core workspace routes render", async ({ page }) => {
    await page.goto("/login", { waitUntil: "load" });
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL(/\/w\/[^/]+\/documents/, { timeout: 30_000 });

    await expect(page.getByRole("heading", { name: "Документы", exact: true })).toBeVisible({
      timeout: 15_000,
    });

    const slug = new URL(page.url()).pathname.match(/^\/w\/([^/]+)\//)?.[1];
    expect(slug, "workspace slug from URL").toBeTruthy();

    await page.goto(`/w/${slug}/jobs`);
    await expect(page.getByRole("heading", { name: "Очередь обработки" })).toBeVisible();

    await page.goto(`/w/${slug}/billing`);
    await expect(page.getByRole("heading", { name: "План и лимиты" })).toBeVisible();

    await page.goto(`/w/${slug}/team`);
    await expect(page.getByRole("heading", { name: "Команда и доступ" })).toBeVisible();

    await page.goto(`/w/${slug}/search`);
    await expect(page.getByRole("heading", { name: "Поиск", exact: true })).toBeVisible();

    await page.goto(`/w/${slug}/chat`);
    await expect(page.getByText("Диалоги").first()).toBeVisible();

    await page.goto(`/w/${slug}/audit`);
    await expect(page.getByRole("heading", { name: "Журнал аудита" })).toBeVisible();
  });
});
