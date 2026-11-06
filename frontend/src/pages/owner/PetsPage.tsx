import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import type { FormEvent } from "react";
import { fieldErrors } from "../../api/client";
import { endpoints } from "../../api/endpoints";
import type { Pet, PetCreate } from "../../api/types";
import { PetAvatar } from "../../components/PetAvatar";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, Field, PageHeader, Spinner } from "../../components/ui";
import { bangkokToday, formatDate } from "../../lib/format";

interface FormState {
  name: string;
  species: string;
  breed: string;
  sex: string;
  birth_date: string;
  weight_kg: string;
  medical_notes: string;
}

const EMPTY: FormState = {
  name: "",
  species: "Dog",
  breed: "",
  sex: "",
  birth_date: "",
  weight_kg: "",
  medical_notes: "",
};

export default function PetsPage() {
  const queryClient = useQueryClient();
  const pets = useQuery({ queryKey: ["pets"], queryFn: endpoints.pets.list });
  const [form, setForm] = useState<FormState>(EMPTY);
  const [editingId, setEditingId] = useState<string | null>(null);

  const buildPayload = (): PetCreate => ({
    name: form.name.trim(),
    species: form.species.trim(),
    breed: form.breed.trim() || null,
    sex: form.sex.trim() || null,
    birth_date: form.birth_date || null,
    weight_kg: form.weight_kg ? Number(form.weight_kg) : null,
    medical_notes: form.medical_notes.trim() || null,
  });

  const save = useMutation({
    mutationFn: () =>
      editingId ? endpoints.pets.update(editingId, buildPayload()) : endpoints.pets.create(buildPayload()),
    onSuccess: () => {
      pushToast("success", editingId ? "บันทึกข้อมูลสัตว์เลี้ยงแล้ว" : "เพิ่มสัตว์เลี้ยงแล้ว");
      setForm(EMPTY);
      setEditingId(null);
      void queryClient.invalidateQueries({ queryKey: ["pets"] });
    },
  });

  const upload = useMutation({
    mutationFn: ({ id, file }: { id: string; file: File }) =>
      endpoints.pets.uploadPhoto(id, file),
    onSuccess: (_pet, variables) => {
      pushToast("success", "อัปโหลดรูปแล้ว ระบบย่อขนาดให้อัตโนมัติ");
      void queryClient.invalidateQueries({ queryKey: ["pets"] });
      void queryClient.invalidateQueries({ queryKey: ["pet-photo", variables.id] });
    },
    onError: (error) => {
      pushToast("error", error instanceof Error ? error.message : "อัปโหลดรูปไม่สำเร็จ");
    },
  });

  const removePhoto = useMutation({
    mutationFn: (id: string) => endpoints.pets.deletePhoto(id),
    onSuccess: (_pet, id) => {
      pushToast("success", "ลบรูปแล้ว");
      queryClient.removeQueries({ queryKey: ["pet-photo", id] });
      void queryClient.invalidateQueries({ queryKey: ["pets"] });
    },
    onError: (error) => {
      pushToast("error", error instanceof Error ? error.message : "ลบรูปไม่สำเร็จ");
    },
  });

  const errors = fieldErrors(save.error);

  const update = (key: keyof FormState) => (event: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm((current) => ({ ...current, [key]: event.target.value }));

  const choosePhoto = (petId: string) => (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file) return;
    if (file.size > 8 * 1024 * 1024) {
      pushToast("error", "ไฟล์รูปต้องมีขนาดไม่เกิน 8 MB");
      return;
    }
    upload.mutate({ id: petId, file });
  };

  const startEdit = (pet: Pet) => {
    setEditingId(pet.id);
    setForm({
      name: pet.name,
      species: pet.species,
      breed: pet.breed ?? "",
      sex: pet.sex ?? "",
      birth_date: pet.birth_date ?? "",
      weight_kg: pet.weight_kg ?? "",
      medical_notes: pet.medical_notes ?? "",
    });
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!form.name.trim() || !form.species.trim()) {
      pushToast("error", "กรุณากรอกชื่อและชนิดของสัตว์เลี้ยง");
      return;
    }
    save.mutate();
  };

  return (
    <div>
      <PageHeader
        title="สัตว์เลี้ยงของฉัน"
        subtitle="จัดการข้อมูลสัตว์เลี้ยงและประวัติการรักษา"
        actions={
          editingId ? (
            <button
              type="button"
              className="btn-secondary"
              onClick={() => {
                setEditingId(null);
                setForm(EMPTY);
              }}
            >
              ยกเลิกการแก้ไข
            </button>
          ) : null
        }
      />

      <form className="card mb-6 grid gap-3 sm:grid-cols-2" onSubmit={submit}>
        <Field label="ชื่อสัตว์เลี้ยง" error={errors.name}>
          <input className="input" required value={form.name} onChange={update("name")} />
        </Field>
        <Field label="ชนิด" error={errors.species}>
          <input
            className="input"
            required
            value={form.species}
            onChange={update("species")}
            placeholder="Dog / Cat / Bird"
          />
        </Field>
        <Field label="พันธุ์">
          <input className="input" value={form.breed} onChange={update("breed")} />
        </Field>
        <Field label="เพศ">
          <input className="input" value={form.sex} onChange={update("sex")} placeholder="ผู้ / เมีย" />
        </Field>
        <Field label="วันเกิด" error={errors.birth_date}>
          <input
            className="input"
            type="date"
            max={bangkokToday(0)}
            value={form.birth_date}
            onChange={update("birth_date")}
          />
        </Field>
        <Field label="น้ำหนัก (กก.)" error={errors.weight_kg}>
          <input
            className="input"
            type="number"
            min={0}
            step="0.1"
            value={form.weight_kg}
            onChange={update("weight_kg")}
          />
        </Field>
        <div className="sm:col-span-2">
          <Field label="บันทึกทางการแพทย์">
            <textarea
              className="input min-h-20"
              value={form.medical_notes}
              onChange={update("medical_notes")}
            />
          </Field>
        </div>
        <div className="sm:col-span-2">
          <ErrorText error={save.error} />
          <button type="submit" className="btn-primary mt-3" disabled={save.isPending}>
            {save.isPending ? "กำลังบันทึก..." : editingId ? "บันทึกการแก้ไข" : "เพิ่มสัตว์เลี้ยง"}
          </button>
        </div>
      </form>

      {pets.isLoading ? <Spinner /> : null}
      <ErrorText error={pets.error} />
      {pets.data && pets.data.length === 0 ? (
        <EmptyState title="ยังไม่มีสัตว์เลี้ยง" hint="เพิ่มสัตว์เลี้ยงเพื่อเริ่มจองนัดหมาย" />
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2">
        {pets.data?.map((pet) => (
          <article key={pet.id} className="card">
            <div className="flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <PetAvatar petId={pet.id} name={pet.name} size="lg" />
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold">{pet.name}</h2>
                  <p className="text-sm text-slate-500">
                    {pet.species}
                    {pet.breed ? ` · ${pet.breed}` : ""}
                    {pet.sex ? ` · ${pet.sex}` : ""}
                  </p>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <label className={`btn-secondary inline-flex cursor-pointer text-xs ${upload.isPending ? "pointer-events-none opacity-60" : ""}`}>
                      {upload.isPending && upload.variables?.id === pet.id
                        ? "กำลังอัปโหลด..."
                        : pet.photo_updated_at
                          ? "เปลี่ยนรูป"
                          : "อัปโหลดรูป"}
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        className="sr-only"
                        disabled={upload.isPending}
                        onChange={choosePhoto(pet.id)}
                      />
                    </label>
                    {pet.photo_updated_at ? (
                      <button
                        type="button"
                        className="btn-secondary text-xs text-rose-600"
                        disabled={removePhoto.isPending}
                        onClick={() => {
                          if (window.confirm(`ลบรูปของ ${pet.name} ใช่หรือไม่?`)) {
                            removePhoto.mutate(pet.id);
                          }
                        }}
                      >
                        {removePhoto.isPending ? "กำลังลบ..." : "ลบรูป"}
                      </button>
                    ) : null}
                  </div>
                  <p className="mt-1 text-[11px] text-slate-400">ระบบย่อรูปอัตโนมัติ (ไม่เกิน 1024 px)</p>
                </div>
              </div>
              <button type="button" className="btn-secondary" onClick={() => startEdit(pet)}>
                แก้ไข
              </button>
            </div>
            <dl className="mt-3 grid grid-cols-2 gap-2 text-sm">
              <div>
                <dt className="text-xs text-slate-400">วันเกิด</dt>
                <dd>{pet.birth_date ? formatDate(pet.birth_date) : "-"}</dd>
              </div>
              <div>
                <dt className="text-xs text-slate-400">น้ำหนัก</dt>
                <dd>{pet.weight_kg ? `${pet.weight_kg} กก.` : "-"}</dd>
              </div>
            </dl>
            {pet.medical_notes ? (
              <p className="mt-3 rounded-lg bg-slate-50 p-2 text-sm text-slate-600">{pet.medical_notes}</p>
            ) : null}
          </article>
        ))}
      </div>
    </div>
  );
}
