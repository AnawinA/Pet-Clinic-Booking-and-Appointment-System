import { useMutation, useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { fieldErrors } from "../../api/client";
import { endpoints } from "../../api/endpoints";
import type { AvailabilitySlot } from "../../api/types";
import { PetAvatar } from "../../components/PetAvatar";
import { pushToast } from "../../components/Toast";
import { EmptyState, ErrorText, Field, PageHeader, Spinner } from "../../components/ui";
import { bangkokToday, formatTime } from "../../lib/format";

export default function BookPage() {
  const navigate = useNavigate();
  const vets = useQuery({ queryKey: ["vets"], queryFn: endpoints.vets.list });
  const pets = useQuery({ queryKey: ["pets"], queryFn: endpoints.pets.list });

  const [date, setDate] = useState(bangkokToday(1));
  const [vetFilter, setVetFilter] = useState("");
  const [selected, setSelected] = useState<AvailabilitySlot | null>(null);
  const [petId, setPetId] = useState("");
  const [symptoms, setSymptoms] = useState("");

  const availability = useQuery({
    queryKey: ["availability", date, vetFilter],
    queryFn: () => endpoints.availability.list(date, vetFilter || undefined),
    refetchInterval: 5000,
  });

  useEffect(() => {
    setSelected(null);
  }, [date, vetFilter]);

  useEffect(() => {
    if (!petId && pets.data && pets.data.length > 0) setPetId(pets.data[0].id);
  }, [petId, pets.data]);

  const selectedPet = pets.data?.find((pet) => pet.id === petId);

  const groups = useMemo(() => {
    const map = new Map<string, { name: string; slots: AvailabilitySlot[] }>();
    for (const slot of availability.data ?? []) {
      const group = map.get(slot.vet_id) ?? { name: slot.vet_name, slots: [] };
      group.slots.push(slot);
      map.set(slot.vet_id, group);
    }
    return Array.from(map.entries());
  }, [availability.data]);

  const book = useMutation({
    mutationFn: () => {
      if (!selected) throw new Error("กรุณาเลือกช่วงเวลา");
      return endpoints.appointments.create({
        pet_id: petId,
        vet_id: selected.vet_id,
        slot_start: selected.slot_start,
        symptoms: symptoms.trim(),
      });
    },
    onSuccess: () => {
      pushToast("success", "จองนัดหมายสำเร็จ");
      navigate("/owner/appointments");
    },
  });

  const errors = fieldErrors(book.error);

  const submit = (event: React.FormEvent) => {
    event.preventDefault();
    if (!selected) {
      pushToast("error", "กรุณาเลือกช่วงเวลาที่ต้องการ");
      return;
    }
    if (!petId) {
      pushToast("error", "กรุณาเลือกสัตว์เลี้ยง");
      return;
    }
    if (!symptoms.trim()) {
      pushToast("error", "กรุณาระบุอาการเบื้องต้น");
      return;
    }
    book.mutate();
  };

  return (
    <div>
      <PageHeader title="จองนัดหมาย" subtitle="เลือกวันและช่วงเวลาที่ว่าง แล้วระบุอาการของสัตว์เลี้ยง" />

      <form className="space-y-5" onSubmit={submit}>
        <section className="card grid gap-3 sm:grid-cols-2">
          <Field label="วันที่">
            <input
              className="input"
              type="date"
              min={bangkokToday(0)}
              max={bangkokToday(30)}
              value={date}
              onChange={(event) => setDate(event.target.value)}
            />
          </Field>
          <Field label="สัตวแพทย์">
            <select className="input" value={vetFilter} onChange={(event) => setVetFilter(event.target.value)}>
              <option value="">ทั้งหมด</option>
              {vets.data?.map((vet) => (
                <option key={vet.id} value={vet.id}>
                  {vet.full_name}
                </option>
              ))}
            </select>
          </Field>
        </section>

        <section>
          <div className="mb-2 flex items-center justify-between">
            <h2 className="font-semibold">ช่วงเวลาที่ว่าง</h2>
            <span className="text-xs text-slate-500">อัปเดตทุก 5 วินาที</span>
          </div>
          <ErrorText error={availability.error} />
          {availability.isLoading ? <Spinner /> : null}
          {availability.data && availability.data.length === 0 ? (
            <EmptyState title="ไม่มีช่วงเวลาว่าง" hint="ลองเปลี่ยนวันหรือสัตวแพทย์" />
          ) : null}

          <div className="space-y-4">
            {groups.map(([vetId, group]) => (
              <div key={vetId} className="card">
                <h3 className="font-medium">{group.name}</h3>
                <div className="mt-2 flex flex-wrap gap-2">
                  {group.slots.map((slot) => {
                    const active =
                      selected?.vet_id === slot.vet_id && selected.slot_start === slot.slot_start;
                    return (
                      <button
                        key={`${slot.vet_id}-${slot.slot_start}`}
                        type="button"
                        onClick={() => setSelected(slot)}
                        className={`rounded-lg border px-3 py-1.5 text-sm ${
                          active
                            ? "border-brand-600 bg-brand-50 font-semibold text-brand-700"
                            : "border-slate-300 bg-white text-slate-700 hover:border-brand-500"
                        }`}
                      >
                        {formatTime(slot.slot_start)}
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="card space-y-3">
          <h2 className="font-semibold">รายละเอียดการนัด</h2>
          {selected ? (
            <p className="rounded-lg bg-brand-50 px-3 py-2 text-sm text-brand-800">
              เลือก {selected.vet_name} เวลา {formatTime(selected.slot_start)} น.
            </p>
          ) : null}

          <div className="flex items-end gap-2">
            {selectedPet ? (
              <PetAvatar petId={selectedPet.id} name={selectedPet.name} size="sm" />
            ) : null}
            <div className="min-w-0 flex-1">
              <Field label="สัตว์เลี้ยง">
                <select
                  className="input"
                  value={petId}
                  onChange={(event) => setPetId(event.target.value)}
                >
                  <option value="">เลือกสัตว์เลี้ยง</option>
                  {pets.data?.map((pet) => (
                    <option key={pet.id} value={pet.id}>
                      {pet.name} ({pet.species})
                    </option>
                  ))}
                </select>
              </Field>
            </div>
          </div>

          <Field label="อาการเบื้องต้น" error={errors.symptoms}>
            <textarea
              className="input min-h-24"
              required
              value={symptoms}
              onChange={(event) => setSymptoms(event.target.value)}
              placeholder="อธิบายอาการ เช่น ซึม ไม่กินอาหาร 2 วัน"
            />
          </Field>

          <ErrorText error={book.error} />
          <button type="submit" className="btn-primary w-full sm:w-auto" disabled={book.isPending}>
            {book.isPending ? "กำลังจอง..." : "ยืนยันการจอง"}
          </button>
        </section>
      </form>
    </div>
  );
}
