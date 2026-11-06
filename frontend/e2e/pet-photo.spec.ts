import { expect, test } from "@playwright/test";
import type { APIRequestContext } from "@playwright/test";

const PASSWORD = "Petcare123!";
const OWNER_EMAIL = "owner1@petcare.local";
const PET_NAME = "มะม่วง";

interface PetSummary {
  id: string;
  name: string;
}

async function ownerHeaders(request: APIRequestContext): Promise<Record<string, string>> {
  const login = await request.post("/api/v1/auth/login", {
    data: { email: OWNER_EMAIL, password: PASSWORD },
  });
  expect(login.ok()).toBe(true);
  const body = (await login.json()) as { access_token: string };
  return { Authorization: `Bearer ${body.access_token}` };
}

test("owner อัปโหลด ดูรูปเต็ม และลบรูปได้ โดยไม่ทำรูปเดิมหาย", async ({ page, request }) => {
  // Back up the real pet photo first: this test runs against the shared local stack.
  const headers = await ownerHeaders(request);
  const petsResponse = await request.get("/api/v1/pets", { headers });
  expect(petsResponse.ok()).toBe(true);
  const pets = (await petsResponse.json()) as PetSummary[];
  const pet = pets.find((item) => item.name === PET_NAME);
  if (!pet) throw new Error(`ไม่พบสัตว์เลี้ยง ${PET_NAME}`);

  const originalResponse = await request.get(`/api/v1/pets/${pet.id}/photo`, { headers });
  const originalPhoto = originalResponse.ok() ? await originalResponse.body() : null;

  try {
    await page.goto("/login");
    await page.getByLabel("อีเมล").fill(OWNER_EMAIL);
    await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
    await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
    await expect(page).toHaveURL(/\/owner\/appointments/);

    await page.goto("/owner/pets");
    const card = page.locator("article").filter({
      has: page.getByRole("heading", { name: PET_NAME, exact: true }),
    });
    await expect(card).toBeVisible();

    const upload = page.waitForResponse(
      (response) =>
        response.url().includes("/photo") && response.request().method() === "POST",
    );
    await card.locator('input[type="file"]').setInputFiles("public/login-hero.jpg");
    const response = await upload;
    expect(response.status()).toBe(200);

    await expect(card.getByRole("img", { name: `รูปของ ${PET_NAME}` })).toBeVisible();

    await card.getByRole("button", { name: `ดูรูปของ ${PET_NAME}` }).click();
    const dialog = page.getByRole("dialog", { name: `รูปของ ${PET_NAME}` });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByRole("img", { name: `รูปของ ${PET_NAME}` })).toBeVisible();
    await page.keyboard.press("Escape");
    await expect(dialog).toBeHidden();

    page.once("dialog", (confirm) => void confirm.accept());
    await card.getByRole("button", { name: "ลบรูป" }).click();
    await expect(card.getByRole("img", { name: `ยังไม่มีรูปของ ${PET_NAME}` })).toBeVisible();
    await expect(
      page.getByRole("status").filter({ hasText: "สัตว์เลี้ยงนี้ยังไม่มีรูป" }),
    ).toHaveCount(0);
  } finally {
    if (originalPhoto) {
      const restore = await request.post(`/api/v1/pets/${pet.id}/photo`, {
        headers,
        multipart: {
          file: {
            name: "restore.webp",
            mimeType: "image/webp",
            buffer: originalPhoto,
          },
        },
      });
      expect(restore.status()).toBe(200);
    } else {
      // No previous photo: remove any test image left behind by a mid-test failure.
      await request.delete(`/api/v1/pets/${pet.id}/photo`, { headers });
    }
  }
});
