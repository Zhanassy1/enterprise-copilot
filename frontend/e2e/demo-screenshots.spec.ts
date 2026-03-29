/**
 * Съёмка демо-скриншотов в docs/assets/screenshots/
 * Требуется: API и UI (docker compose). Опционально Celery worker для сценария с индексацией.
 * Полный набор (+ documents с «Готово», summary.png): DEMO_SCREENSHOTS_WITH_INGEST=1 npm run demo:screenshots
 */
import * as path from "path";
import { expect, test } from "@playwright/test";

const API_BASE = process.env.E2E_API_URL ?? "http://127.0.0.1:8000/api/v1";
const WITH_INGEST = process.env.DEMO_SCREENSHOTS_WITH_INGEST === "1";
const shotDir = path.join(process.cwd(), "..", "docs", "assets", "screenshots");

function shot(name: string) {
  return path.join(shotDir, name);
}

test.describe.configure({ mode: "serial" });

test.describe("demo screenshots", () => {
  test.use({ viewport: { width: 1440, height: 900 } });

  const password = "DemoShot_" + Math.random().toString(36).slice(2, 10) + "A1!";
  let email: string;

  test.beforeAll(async ({ request }) => {
    const fs = await import("fs");
    fs.mkdirSync(shotDir, { recursive: true });
    email = `screenshot-demo-${Date.now()}@example.com`;
    const res = await request.post(`${API_BASE}/auth/register`, {
      headers: { "Content-Type": "application/json" },
      data: { email, password, full_name: "Demo Screenshots" },
    });
    expect(res.ok(), `register failed: ${res.status()} ${await res.text()}`).toBeTruthy();
  });

  test("marketing: landing + pricing", async ({ page }) => {
    await page.goto("/login");
    await page.evaluate(() => {
      localStorage.removeItem("ec_token");
      localStorage.removeItem("ec_workspace_id");
    });
    await page.goto("/");
    await expect(page.getByRole("heading", { name: /Находите ответы в своих документах/i })).toBeVisible({
      timeout: 20000,
    });
    await page.screenshot({ path: shot("landing.png"), fullPage: true });

    await page.goto("/pricing");
    await expect(page.getByRole("heading", { name: /Планы Free, Pro и Team/i })).toBeVisible();
    await page.screenshot({ path: shot("pricing.png"), fullPage: true });
  });

  test("app: documents, jobs, billing, search, chat, audit", async ({ page }) => {
    if (WITH_INGEST) test.setTimeout(240_000);
    const ingestFixture = path.join(__dirname, "fixtures", "demo-ingest.txt");

    await page.goto("/login");
    await page.getByLabel("Email").fill(email);
    await page.getByLabel("Пароль").fill(password);
    await page.getByRole("button", { name: "Войти" }).click();
    await page.waitForURL(/\/documents/, { timeout: 25000 });

    if (WITH_INGEST) {
      await page.getByRole("button", { name: "Загрузить" }).click();
      await page.locator('input[type="file"]').setInputFiles(ingestFixture);
      await expect(page.getByText("demo-ingest.txt").first()).toBeVisible({ timeout: 60_000 });
      await expect(page.getByText("Готово", { exact: true }).first()).toBeVisible({ timeout: 120_000 });
      await page.screenshot({ path: shot("documents.png"), fullPage: true });

      await page.getByTitle("Краткое содержание").first().click();
      await expect(page.getByRole("heading", { name: "Краткое содержание" })).toBeVisible();
      await expect(page.getByRole("dialog").locator(".animate-spin")).toHaveCount(0, { timeout: 60_000 });
      await page.screenshot({ path: shot("summary.png"), fullPage: true });
      await page.keyboard.press("Escape");
    } else {
      await page.screenshot({ path: shot("documents.png"), fullPage: true });
    }

    await page.goto("/jobs");
    await expect(page.getByRole("heading", { name: "Очередь обработки" })).toBeVisible();
    await page.screenshot({ path: shot("jobs.png"), fullPage: true });

    await page.goto("/billing");
    await expect(page.getByRole("heading", { name: "План и лимиты" })).toBeVisible();
    await page.screenshot({ path: shot("billing.png"), fullPage: true });

    await page.goto("/search");
    await expect(page.getByRole("heading", { name: "Поиск", exact: true })).toBeVisible();
    await page.screenshot({ path: shot("search.png"), fullPage: true });

    await page.goto("/chat");
    await expect(page.getByText("Диалоги").first()).toBeVisible();
    await page.screenshot({ path: shot("chat.png"), fullPage: true });

    await page.goto("/audit");
    await expect(page.getByRole("heading", { name: "Журнал аудита" })).toBeVisible();
    await page.screenshot({ path: shot("audit.png"), fullPage: true });
  });
});
