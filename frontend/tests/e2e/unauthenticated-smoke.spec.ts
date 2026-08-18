import { expect, test } from "@playwright/test";

test("unauthenticated application hydrates and renders the login boundary", async ({ page, request }) => {
  const consoleErrors: string[] = [];
  const failedRequests: string[] = [];
  page.on("console", (message) => {
    if (message.type() !== "error") return;
    const expectedAuthRejection = message.location().url.endsWith("/api/auth/me")
      && message.text().includes("401 (Unauthorized)");
    if (!expectedAuthRejection) consoleErrors.push(message.text());
  });
  page.on("requestfailed", (failedRequest) => {
    failedRequests.push(`${failedRequest.url()}: ${failedRequest.failure()?.errorText || "failed"}`);
  });

  const response = await page.goto("/");
  expect(response?.ok()).toBeTruthy();
  await expect(page).toHaveURL(/\/login$/);
  await expect(page.getByRole("heading", { name: "AEGIS ALPHA" })).toBeVisible();
  await expect(page.getByLabel("Authorized user")).toHaveValue("");
  await expect(page.getByRole("button", { name: "ENTER CONSOLE" })).toBeVisible();
  await expect(page.getByText("Trading execution is disabled")).toBeVisible();

  const assets = await page.locator('script[src], link[rel="stylesheet"]').evaluateAll((elements) =>
    elements.map((element) => element instanceof HTMLScriptElement ? element.src : (element as HTMLLinkElement).href),
  );
  expect(assets.length).toBeGreaterThan(0);
  for (const asset of assets) {
    const assetResponse = await request.get(asset);
    expect(assetResponse.ok(), `asset failed: ${asset}`).toBeTruthy();
  }

  expect((await request.get("/api/status")).status()).toBe(401);
  expect(failedRequests).toEqual([]);
  expect(consoleErrors).toEqual([]);
});

for (const route of ["/portfolio", "/strategies", "/performance", "/adjustments", "/activity", "/settings", "/roadmap", "/security", "/system"]) {
  test(`${route} enforces authentication with a rendered login page`, async ({ page }) => {
    await page.goto(route);
    await expect(page).toHaveURL(/\/login$/);
    await expect(page.getByRole("heading", { name: "AEGIS ALPHA" })).toBeVisible();
  });
}
