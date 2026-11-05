import { expect, test, waitLive } from "./fixtures";

test("works with every non-station request blocked", async ({ page, hosts, demoDrone }) => {
  void demoDrone;
  const aborted: string[] = [];
  await page.route((url) => url.host !== "127.0.0.1:5077", (route) => { aborted.push(route.request().url()); return route.abort(); });
  await page.goto("/#/live");
  await waitLive(page);
  await page.goto("/#/analytics");
  await expect(page.getByRole("heading", { name: "Analytics" })).toBeVisible();
  await page.goto("/#/missions");
  await expect(page.getByRole("heading", { name: "Missions" })).toBeVisible();
  expect(aborted, "requests to other hosts").toEqual([]);
  expect([...hosts]).toEqual(["127.0.0.1:5077"]);
});
