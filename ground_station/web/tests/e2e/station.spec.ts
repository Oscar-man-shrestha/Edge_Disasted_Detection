import { expect, mapState, STATION, test, waitLive } from "./fixtures";

test.describe("ground station (real Flask station + demo drone)", () => {
  test("live: LIVE, moving drone, updating preview", async ({ page, demoDrone }) => {
    void demoDrone;
    await page.goto("/?debug=1#/live");
    await waitLive(page);
    await expect(page.locator(".gs-drone")).toBeVisible();
    const a = await mapState(page);
    const src1 = await page.getByAltText("Latest camera preview from the drone").first().getAttribute("src");
    await page.waitForTimeout(3500);
    const b = await mapState(page);
    expect(Math.abs(a!.lat - b!.lat) + Math.abs(a!.lng - b!.lng)).toBeGreaterThan(0);
    await expect.poll(() => page.getByAltText("Latest camera preview from the drone").first().getAttribute("src")).not.toBe(src1);
  });

  test("alert workflow: toast, acknowledge, resolve, reopen", async ({ page, demoDrone }) => {
    void demoDrone;
    await page.goto("/#/live");
    await waitLive(page);
    await expect(page.getByText(/New (fire|person|smoke) alert/).first()).toBeVisible({ timeout: 40_000 });
    const row = page.getByRole("region", { name: "Alerts" }).getByRole("listitem").first();
    await row.getByRole("button").click();
    const detail = page.getByRole("region", { name: "Alerts" });
    await detail.getByRole("button", { name: "Acknowledge" }).click();
    await expect(detail.getByText("acknowledged", { exact: true })).toBeVisible();
    await detail.getByRole("button", { name: "Resolve" }).click();
    await expect(detail.getByText("resolved", { exact: true })).toBeVisible();
    await detail.getByRole("button", { name: "Reopen" }).click();
    await expect(detail.getByText("acknowledged", { exact: true })).toBeVisible();
  });

  test("3D toggle tilts the map", async ({ page, demoDrone }) => {
    void demoDrone;
    await page.goto("/?debug=1#/live");
    await waitLive(page);
    await page.locator("body").press("3");
    await expect.poll(async () => (await mapState(page))!.pitch, { timeout: 5000 }).toBeGreaterThanOrEqual(45);
  });

  test("a remembered 3D preference is applied on load", async ({ page, demoDrone }) => {
    void demoDrone;
    await page.addInitScript(() => localStorage.setItem("gs-prefs-v3", JSON.stringify({ map3d: true })));
    await page.goto("/?debug=1#/live");
    await waitLive(page);
    await expect.poll(async () => (await mapState(page))?.pitch ?? 0, { timeout: 8000 }).toBeGreaterThanOrEqual(45);
  });

  test("replay: start shows no alerts, end shows all; ticks seek", async ({ page, request, demoDrone }) => {
    void demoDrone;
    await page.goto("/#/live");
    await waitLive(page);
    await expect(page.getByText(/New (fire|person|smoke) alert/).first()).toBeVisible({ timeout: 40_000 });
    const tl = await (await request.get(`${STATION}/api/missions/1/timeline`)).json();
    await page.goto("/#/replay/1");
    const slider = page.getByRole("slider", { name: "Replay time" });
    await slider.fill("0");
    await expect(page.locator(".gs-amark, .gs-cluster")).toHaveCount(0);
    const max = await slider.getAttribute("max");
    await slider.fill(max!);
    const located = tl.alerts.filter((a: any) => a.lat != null).length;
    // above 25 alerts the map clusters: count single markers plus each cluster's total
    const shownOnMap = () => page.evaluate(() =>
      document.querySelectorAll(".gs-amark").length +
      [...document.querySelectorAll(".gs-cluster b")].reduce((n, b) => n + Number(b.textContent), 0));
    await expect.poll(shownOnMap).toBeGreaterThanOrEqual(located);
    const label = page.locator(".tabular.font-mono").filter({ hasText: /^\d\d:\d\d:\d\d$/ }).first();
    const before = await label.textContent();
    await page.getByRole("button", { name: /alert #\d+ at/ }).first().click();
    await expect(label).not.toHaveText(before!);
  });

  test("analytics: charts render and KPI matches the API", async ({ page, request, demoDrone }) => {
    void demoDrone;
    await page.goto("/#/live");
    await waitLive(page);
    const a = (await (await request.get(`${STATION}/api/missions/1/timeline`)).json()).alerts.length;
    await page.goto("/#/analytics/1");
    await expect(page.locator('[data-testid^="chart-"] canvas')).toHaveCount(5);
    const k = Number((await page.getByTestId("kpi-alerts").locator(".font-mono").first().textContent())!.trim());
    const b = (await (await request.get(`${STATION}/api/missions/1/timeline`)).json()).alerts.length;
    expect(k).toBeGreaterThanOrEqual(a);
    expect(k).toBeLessThanOrEqual(b);
  });
});
