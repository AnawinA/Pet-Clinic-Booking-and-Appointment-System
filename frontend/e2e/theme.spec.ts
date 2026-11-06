import { expect, test } from "@playwright/test";

const PASSWORD = "Petcare123!";
const OWNER_EMAIL = "owner1@petcare.local";

async function useLightTheme(page: import("@playwright/test").Page): Promise<void> {
  await page.goto("/login");
  await page.evaluate(() => localStorage.setItem("petcare.theme", "light"));
  await page.reload();
}

test("สลับ light/dark และจำค่าไว้หลัง reload", async ({ page }) => {
  await useLightTheme(page);

  const html = page.locator("html");
  const toggle = page.getByRole("button", { name: "สลับโหมดสว่างและมืด" });

  await expect(html).not.toHaveClass(/dark/);
  await expect(toggle).toHaveAttribute("aria-pressed", "false");

  await toggle.click();
  await expect(html).toHaveClass(/dark/);
  await expect(toggle).toHaveAttribute("aria-pressed", "true");

  await page.reload();
  await expect(html).toHaveClass(/dark/);
  await expect(toggle).toHaveAttribute("aria-pressed", "true");

  await toggle.click();
  await expect(html).not.toHaveClass(/dark/);
});

test("dashboard ใช้พื้นผิว dark mode กับ body และการ์ดจริง", async ({ page }) => {
  await useLightTheme(page);

  await page.getByLabel("อีเมล").fill(OWNER_EMAIL);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
  await expect(page).toHaveURL(/\/owner\/appointments/);
  await expect(page.locator("main .card").first()).toBeVisible();

  await page.getByRole("button", { name: "สลับโหมดสว่างและมืด" }).click();
  await expect(page.locator("html")).toHaveClass(/dark/);

  // The theme transition is 300ms; wait for computed surfaces to settle.
  await expect
    .poll(() => page.evaluate(() => getComputedStyle(document.body).backgroundColor))
    .not.toBe("rgb(248, 250, 252)");
  await expect
    .poll(() =>
      page.evaluate(() => {
        const card = document.querySelector("main .card");
        return card ? getComputedStyle(card).backgroundColor : null;
      }),
    )
    .not.toBe("rgb(255, 255, 255)");

  const colors = await page.evaluate(() => ({
    body: getComputedStyle(document.body).backgroundColor,
    card: document.querySelector("main .card")
      ? getComputedStyle(document.querySelector("main .card")!).backgroundColor
      : null,
  }));

  expect(colors.body).not.toBe("rgb(248, 250, 252)");
  expect(colors.card).not.toBe("rgb(255, 255, 255)");
});
