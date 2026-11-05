import { expect, mapState, postAlert, STATION, test, waitLive } from "./fixtures";

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

  test("map markers keep their identity across frames (clickable, focusable)", async ({ page, request, demoDrone }) => {
    void demoDrone;
    // >25 alerts -> clustered mode: a tight group (a cluster) plus spread-out singles (plain markers)
    for (let i = 0; i < 26; i++) await postAlert(request, 12.9705 + i * 0.00002, 77.5902 + (i % 5) * 0.00003);
    for (let i = 0; i < 4; i++) await postAlert(request, 12.9712 + i * 0.0012, 77.5918);
    await page.goto("/?debug=1#/live");
    await waitLive(page);
    const marker = page.locator(".gs-amark").first();
    await expect(marker).toBeVisible();
    await marker.evaluate((el) => { (window as any).__probe = el; });
    await page.waitForTimeout(1500);                          // follow mode re-centres every frame
    expect(await page.evaluate(() => (window as any).__probe.isConnected)).toBe(true);
  });

  test("fly to an alert from another view (palette) lands on the alert", async ({ page, request, demoDrone }) => {
    void demoDrone;
    const id = await postAlert(request, 12.9850, 77.6050, "person");
    await page.goto("/?debug=1#/missions");
    await expect(page.getByRole("heading", { name: "Missions" })).toBeVisible();
    await page.keyboard.press("Control+k");
    await page.getByPlaceholder("Type a command or search…").fill(`alert ${id} `);
    await page.keyboard.press("Enter");
    await expect(page).toHaveURL(/#\/live/);
    await expect.poll(async () => {
      const m = await mapState(page);
      return m ? Math.abs(m.lat - 12.985) + Math.abs(m.lng - 77.605) : 1;
    }, { timeout: 8000 }).toBeLessThan(0.002);
  });
});

