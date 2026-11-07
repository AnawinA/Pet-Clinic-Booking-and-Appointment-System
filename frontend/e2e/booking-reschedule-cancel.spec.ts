import { expect, test } from "@playwright/test";
import type { APIRequestContext, Page } from "@playwright/test";

const PASSWORD = "Petcare123!";
const OWNER_EMAIL = "owner1@petcare.local";
const STAFF_EMAIL = "staff@petcare.local";
const PET_LABEL = "มะม่วง (Dog)";
const BANGKOK = "Asia/Bangkok";

interface Vet {
  id: string;
  full_name: string;
}

interface Slot {
  vet_id: string;
  vet_name: string;
  slot_start: string;
  slot_end: string;
}

function bangkokDate(offsetDays: number): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: BANGKOK }).format(
    new Date(Date.now() + offsetDays * 86_400_000),
  );
}

function bangkokDateOf(iso: string): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: BANGKOK }).format(new Date(iso));
}

function bangkokTime(iso: string): string {
  return new Intl.DateTimeFormat("th-TH", {
    timeZone: BANGKOK,
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

function bangkokInputValue(iso: string): string {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: BANGKOK,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date(iso));
  const value = (type: string) => parts.find((part) => part.type === type)?.value ?? "";
  return `${value("year")}-${value("month")}-${value("day")}T${value("hour")}:${value("minute")}`;
}

/**
 * เลือกสัตวแพทย์ที่มีช่วงเวลาว่างอย่างน้อย 2 ช่วงติดกันใน 6 วันข้างหน้า
 * เพื่อให้เทสจองสล็อตแรกแล้วเลื่อนไปสล็อตที่สองได้โดยไม่ชนของเดิม
 */
async function findFreeSlots(
  request: APIRequestContext,
): Promise<{ vet: Vet; first: Slot; second: Slot }> {
  const login = await request.post("/api/v1/auth/login", {
    data: { email: OWNER_EMAIL, password: PASSWORD },
  });
  expect(login.ok(), "ล็อกอิน API ไม่สำเร็จ — ตรวจว่า stack รันและ seed แล้ว").toBe(true);
  const token = ((await login.json()) as { access_token: string }).access_token;
  const headers = { Authorization: `Bearer ${token}` };

  const vetsResponse = await request.get("/api/v1/vets", { headers });
  expect(vetsResponse.ok()).toBe(true);
  const vets = (await vetsResponse.json()) as Vet[];

  for (let offset = 1; offset <= 6; offset += 1) {
    const date = bangkokDate(offset);
    for (const vet of vets) {
      const response = await request.get(`/api/v1/availability?date=${date}&vet_id=${vet.id}`, {
        headers,
      });
      if (!response.ok()) continue;
      const slots = (await response.json()) as Slot[];
      if (slots.length >= 2) return { vet, first: slots[0], second: slots[1] };
    }
  }
  throw new Error("ไม่พบช่วงเวลาว่างอย่างน้อย 2 ช่วงใน 6 วันข้างหน้า");
}

async function loginAs(page: Page, email: string, expectedUrl: RegExp): Promise<void> {
  await page.goto("/login");
  await page.getByLabel("อีเมล").fill(email);
  await page.getByLabel("รหัสผ่าน", { exact: true }).fill(PASSWORD);
  await page.getByRole("button", { name: "เข้าสู่ระบบ" }).click();
  await expect(page).toHaveURL(expectedUrl);
}

async function chooseVet(page: Page, vet: Vet): Promise<void> {
  const select = page.getByLabel("สัตวแพทย์");
  await expect(select.locator("option", { hasText: vet.full_name })).toHaveCount(1);
  await select.selectOption({ label: vet.full_name });
}

test("เจ้าของจอง → staff เลื่อนนัด → เจ้าของยกเลิก ผ่าน UI จริง", async ({ browser, request }) => {
  const { vet, first, second } = await findFreeSlots(request);
  const marker = `E2E-${Date.now()}`;
  const date = bangkokDateOf(first.slot_start);

  const ownerContext = await browser.newContext();
  const staffContext = await browser.newContext();
  const owner = await ownerContext.newPage();
  const staff = await staffContext.newPage();

  try {
    await test.step("owner จองนัดผ่านหน้าเว็บ", async () => {
      await loginAs(owner, OWNER_EMAIL, /\/owner\/appointments/);
      await owner.getByRole("link", { name: "จองนัด", exact: true }).click();
      await expect(owner).toHaveURL(/\/owner\/book/);

      await owner.getByLabel("วันที่").fill(date);
      await chooseVet(owner, vet);

      const group = owner
        .locator("div.card")
        .filter({ has: owner.getByRole("heading", { name: vet.full_name, exact: true }) });
      await expect(group).toBeVisible();
      await group
        .getByRole("button", { name: bangkokTime(first.slot_start), exact: true })
        .click();

      await owner.getByLabel("สัตว์เลี้ยง").selectOption({ label: PET_LABEL });
      await owner.getByLabel("อาการเบื้องต้น").fill(`ปวดท้องเล็กน้อย ${marker}`);
      await owner.getByRole("button", { name: "ยืนยันการจอง" }).click();

      await expect(owner.getByRole("status").filter({ hasText: "จองนัดหมายสำเร็จ" })).toBeVisible();
      await expect(owner).toHaveURL(/\/owner\/appointments/);

      const card = owner.locator("article").filter({ hasText: marker });
      await expect(card).toContainText("จองแล้ว");
      await expect(card).toContainText(bangkokTime(first.slot_start));
    });

    await test.step("staff เลื่อนนัดผ่านกระดานนัดหมาย", async () => {
      await loginAs(staff, STAFF_EMAIL, /\/staff\/board/);
      await staff.getByLabel("วันที่").fill(date);
      await chooseVet(staff, vet);

      const card = staff.locator("article").filter({ hasText: marker });
      await expect(card).toBeVisible();
      await expect(card).toContainText(bangkokTime(first.slot_start));

      await card.getByRole("button", { name: "เลื่อนนัด", exact: true }).click();
      const [secondDate, secondTime] = bangkokInputValue(second.slot_start).split("T");
      await staff.getByLabel("วันที่ใหม่ (เวลาไทย)").fill(secondDate);
      await staff.getByLabel("เวลาใหม่ (เวลาไทย)").fill(secondTime);
      await staff.getByRole("button", { name: "ยืนยันเลื่อนนัด" }).click();

      await expect(
        staff.getByRole("status").filter({ hasText: "เลื่อนนัดหมายแล้ว" }),
      ).toBeVisible();
      await expect(card).toContainText(bangkokTime(second.slot_start));
    });

    await test.step("owner ยกเลิกนัดผ่านหน้าเว็บ", async () => {
      await owner.goto("/owner/appointments");
      const card = owner.locator("article").filter({ hasText: marker });
      await expect(card).toContainText(bangkokTime(second.slot_start));

      await card.getByRole("button", { name: "ยกเลิกนัด", exact: true }).click();
      await owner.getByLabel("เหตุผล (ไม่บังคับ)").fill("E2E ทดสอบการยกเลิก");
      await owner.getByRole("button", { name: "ยืนยันยกเลิก" }).click();

      await expect(
        owner.getByRole("status").filter({ hasText: "ยกเลิกนัดหมายแล้ว" }),
      ).toBeVisible();
      await expect(card).toContainText("เหตุผลที่ยกเลิก: E2E ทดสอบการยกเลิก");
      await expect(card.getByText("ยกเลิก", { exact: true })).toBeVisible();
    });
  } finally {
    await ownerContext.close();
    await staffContext.close();
  }
});
