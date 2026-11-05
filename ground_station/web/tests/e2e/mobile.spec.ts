import { expect, postAlert, test, waitLive } from "./fixtures";

test.use({ viewport: { width: 375, height: 812 }, isMobile: true, hasTouch: true });

test("phone layout: no horizontal scroll, bottom tabs, alert sheet", async ({ page, demoDrone }) => {
  void demoDrone;
  await page.goto("/#/live");
  await waitLive(page);
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
  // wait for a person alert so the banner is up, then check nothing important is covered
  await expect(page.getByRole("alert", { name: /person detected/i })).toBeVisible({ timeout: 40_000 });
  await page.getByRole("button", { name: "Export" }).click({ trial: true });       // fails if obscured
  await page.getByRole("button", { name: "Mute alerts" }).click({ trial: true });
  await expect(page.getByRole("button", { name: "New mission" })).toBeHidden();    // desktop-only button
  const alertsBtn = page.getByRole("button", { name: /^Alerts/ });
  expect((await alertsBtn.boundingBox())!.height).toBeLessThan(40);               // label must not wrap
  await alertsBtn.click({ trial: true });                                          // not covered by the banner
  await page.getByRole("button", { name: /^Alerts/ }).click();
  await expect(page.getByRole("dialog", { name: "Alerts" })).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("navigation", { name: "Views" }).last().getByRole("link", { name: "Analytics" }).click();
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(375);
});

test("phone: tapping an alert on the map opens its details", async ({ page, request, demoDrone }) => {
  void demoDrone;
  const id = await postAlert(request, 12.9900, 77.6200, "smoke");
  await page.addInitScript(() => localStorage.setItem("gs-prefs-v3", JSON.stringify({ follow: false })));
  await page.goto("/?debug=1#/live");
  await waitLive(page);
  await page.evaluate(() => (window as any).__gsMap.jumpTo({ center: [77.62, 12.99], zoom: 18 }));
  await page.getByRole("button", { name: new RegExp(`smoke alert ${id},`) }).click();
  const sheet = page.getByRole("dialog", { name: "Alerts" });
  await expect(sheet).toBeVisible();
  await expect(sheet.getByRole("button", { name: "Acknowledge" })).toBeVisible();
});
