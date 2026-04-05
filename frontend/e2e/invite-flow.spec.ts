/**
 * Full invite scenario: owner creates invite (API returns plain_token when EMAIL_CAPTURE_MODE=1),
 * new user accepts on /invite/:token, team page shows expected role label.
 * Requires: UI + API (e.g. docker compose), backend `EMAIL_CAPTURE_MODE=1`, same origin or CORS for API from tests.
 */
import { expect, test } from "@playwright/test";

const API_BASE = process.env.E2E_API_URL ?? "http://127.0.0.1:8000/api/v1";

test.describe.configure({ mode: "serial" });

test("owner invites, new user accepts and sees role on team page", async ({ browser, request }) => {
  const ownerPassword = `Owner_${Date.now()}_Aa1!`;
  const ownerEmail = `owner-inv-${Date.now()}@example.com`;
  const inviteeEmail = `invitee-${Date.now()}@example.com`;
  const inviteePassword = `Invitee_${Date.now()}_Aa1!`;

  const reg = await request.post(`${API_BASE}/auth/register`, {
    headers: { "Content-Type": "application/json" },
    data: { email: ownerEmail, password: ownerPassword, full_name: "Owner" },
  });
  expect(reg.ok(), await reg.text()).toBeTruthy();
  const ownerToken = (await reg.json()).access_token as string;

  const wsList = await request.get(`${API_BASE}/workspaces`, {
    headers: { Authorization: `Bearer ${ownerToken}` },
  });
  expect(wsList.ok(), await wsList.text()).toBeTruthy();
  const workspaces = (await wsList.json()) as { id: string; slug: string; role: string }[];
  expect(workspaces.length).toBeGreaterThan(0);
  const ws = workspaces[0];
  const wsRef = ws.slug || ws.id;

  const inv = await request.post(`${API_BASE}/workspaces/${wsRef}/invitations`, {
    headers: {
      Authorization: `Bearer ${ownerToken}`,
      "Content-Type": "application/json",
      "X-Workspace-Id": ws.id,
    },
    data: { email: inviteeEmail, role: "viewer" },
  });
  expect(inv.ok(), await inv.text()).toBeTruthy();
  const invBody = (await inv.json()) as { plain_token?: string | null };
  if (!invBody.plain_token || invBody.plain_token.length < 16) {
    test.skip(
      true,
      "API did not return plain_token — set backend EMAIL_CAPTURE_MODE=1 for this e2e (see CONTRIBUTING)."
    );
    return;
  }
  const plainToken = invBody.plain_token;

  const ctx = await browser.newContext();
  const page = await ctx.newPage();
  await page.goto(`/invite/${encodeURIComponent(plainToken)}`, { waitUntil: "load", timeout: 30_000 });
  await expect(page.getByRole("heading", { name: /Присоединиться/i })).toBeVisible({ timeout: 20_000 });

  await page.getByLabel(/Пароль/i).fill(inviteePassword);
  await page.getByRole("button", { name: /Создать аккаунт и войти/i }).click();
  await page.waitForURL(/\/documents/, { timeout: 45_000 });

  await page.goto(`/w/${ws.slug}/team`, { waitUntil: "load" });
  await expect(page.getByText("Наблюдатель", { exact: true }).first()).toBeVisible({ timeout: 20_000 });

  await ctx.close();
});
