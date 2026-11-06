import { expect, test } from "@playwright/test";

test("หน้า login สลับแสดง/ซ่อนรหัสผ่านได้", async ({ page }) => {
  await page.goto("/login");

  const password = page.getByLabel("รหัสผ่าน", { exact: true });
  await password.fill("Petcare123!");
  await expect(password).toHaveAttribute("type", "password");

  await page.getByRole("button", { name: "แสดงรหัสผ่าน" }).click();
  await expect(password).toHaveAttribute("type", "text");
  await expect(password).toHaveValue("Petcare123!");

  await page.getByRole("button", { name: "ซ่อนรหัสผ่าน" }).click();
  await expect(password).toHaveAttribute("type", "password");
});

test("หน้า register สลับรหัสผ่านแต่ละช่องแยกกัน", async ({ page }) => {
  await page.goto("/register");

  const password = page.getByLabel("รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)", { exact: true });
  const confirm = page.getByLabel("ยืนยันรหัสผ่าน", { exact: true });

  await expect(page.getByRole("button", { name: "แสดงรหัสผ่าน" })).toHaveCount(2);

  const toggles = page.getByRole("button", { name: "แสดงรหัสผ่าน" });
  await toggles.nth(0).click();

  await expect(password).toHaveAttribute("type", "text");
  await expect(confirm).toHaveAttribute("type", "password");

  await page.getByRole("button", { name: "แสดงรหัสผ่าน" }).click();
  await expect(confirm).toHaveAttribute("type", "text");

  await expect(page.getByRole("button", { name: "ซ่อนรหัสผ่าน" })).toHaveCount(2);
});
