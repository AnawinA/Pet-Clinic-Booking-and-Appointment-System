import { expect, test } from "@playwright/test";

test("หน้า register แสดงระดับความแข็งแรงและคำแนะนำของรหัสผ่าน", async ({ page }) => {
  await page.goto("/register");

  const password = page.getByLabel("รหัสผ่าน (อย่างน้อย 8 ตัวอักษร)", { exact: true });
  const meter = page.getByRole("progressbar");

  await expect(meter).toHaveCount(0);

  await password.fill("abc");
  await expect(meter).toHaveAttribute("aria-valuenow", "1");
  await expect(page.getByText("สั้นเกินไป")).toBeVisible();
  await expect(page.getByText("ใช้อย่างน้อย 8 ตัวอักษร")).toBeVisible();

  await password.fill("Abcdef12");
  await expect(meter).toHaveAttribute("aria-valuenow", "2");
  await expect(page.getByText("ปานกลาง")).toBeVisible();
  await expect(page.getByText("เพิ่มอักขระพิเศษ")).toBeVisible();

  await password.fill("Abcdef12!@xy");
  await expect(meter).toHaveAttribute("aria-valuenow", "4");
  await expect(page.getByText("แข็งแรงมาก")).toBeVisible();
  await expect(page.getByText("พร้อมใช้งาน")).toBeVisible();
});
