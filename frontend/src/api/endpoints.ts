import { apiBlob, apiGet, apiSend, apiUpload } from "./client";
import type {
  Appointment,
  AppointmentStatus,
  AuditLog,
  AvailabilitySlot,
  BulkShiftCreatePayload,
  BulkShiftPreview,
  BulkShiftResult,
  ListResponse,
  Notification,
  Pet,
  PetCreate,
  PetHistoryEntry,
  QueueEntry,
  QueuePosition,
  RescheduleRequest,
  ScheduleEntry,
  Shift,
  StaffAppointmentResolution,
  StaffUpcomingAppointment,
  TokenResponse,
  TreatmentNote,
  User,
  Vet,
} from "./types";

function query(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

export const endpoints = {
  auth: {
    login: (email: string, password: string) =>
      apiSend<TokenResponse>("/auth/login", "POST", { email, password }),
    register: (payload: {
      email: string;
      password: string;
      full_name: string;
      phone?: string | null;
    }) => apiSend<User>("/auth/register", "POST", payload),
    me: () => apiGet<User>("/auth/me"),
    createStaff: (payload: {
      email: string;
      password: string;
      full_name: string;
      phone?: string | null;
      role: "VET" | "STAFF";
    }) => apiSend<User>("/auth/staff-accounts", "POST", payload),
    listStaff: () => apiGet<User[]>("/auth/staff-accounts"),
    upcomingAppointments: (id: string) =>
      apiGet<StaffUpcomingAppointment[]>(`/auth/staff-accounts/${id}/upcoming-appointments`),
    deleteStaff: (id: string, appointments: StaffAppointmentResolution[] = []) =>
      apiSend<{ message: string }>(`/auth/staff-accounts/${id}`, "DELETE", {
        appointments,
      }),
  },
  pets: {
    list: () => apiGet<Pet[]>("/pets"),
    create: (payload: PetCreate) => apiSend<Pet>("/pets", "POST", payload),
    update: (id: string, payload: Partial<PetCreate>) =>
      apiSend<Pet>(`/pets/${id}`, "PATCH", payload),
    photo: (id: string) => apiBlob(`/pets/${id}/photo`),
    uploadPhoto: (id: string, file: File) => apiUpload<Pet>(`/pets/${id}/photo`, file),
    deletePhoto: (id: string) => apiSend<Pet>(`/pets/${id}/photo`, "DELETE"),
    history: (id: string) => apiGet<PetHistoryEntry[]>(`/pets/${id}/history`),
  },
  vets: {
    list: () => apiGet<Vet[]>("/vets"),
  },
  availability: {
    list: (date: string, vetId?: string) =>
      apiGet<AvailabilitySlot[]>(`/availability${query({ date, vet_id: vetId })}`),
  },
  appointments: {
    list: () => apiGet<Appointment[]>("/appointments"),
    detail: (id: string) => apiGet<Appointment>(`/appointments/${id}`),
    create: (payload: {
      pet_id: string;
      vet_id: string;
      slot_start: string;
      symptoms: string;
    }) => apiSend<Appointment>("/appointments", "POST", payload),
    cancel: (id: string, reason?: string) =>
      apiSend<Appointment>(`/appointments/${id}/cancel`, "POST", { reason: reason ?? null }),
    queuePosition: (id: string) => apiGet<QueuePosition>(`/appointments/${id}/queue-position`),
    updateStatus: (id: string, status: AppointmentStatus, expectedVersion: number) =>
      apiSend<Appointment>(`/appointments/${id}/status`, "PATCH", {
        status,
        expected_version: expectedVersion,
      }),
    reschedule: (id: string, proposedSlotStart: string, expectedVersion: number) =>
      apiSend<Appointment>(`/appointments/${id}/reschedule`, "PATCH", {
        proposed_slot_start: proposedSlotStart,
        expected_version: expectedVersion,
      }),
    swap: (
      appointmentA: string,
      appointmentB: string,
      versionA: number,
      versionB: number,
    ) =>
      apiSend<Appointment[]>("/appointments/swap", "POST", {
        appointment_a_id: appointmentA,
        appointment_b_id: appointmentB,
        expected_version_a: versionA,
        expected_version_b: versionB,
      }),
    transfer: (id: string, vetId: string, expectedVersion: number) =>
      apiSend<Appointment>(`/appointments/${id}/transfer`, "POST", {
        vet_id: vetId,
        expected_version: expectedVersion,
      }),
    requestReschedule: (id: string, proposedSlotStart: string, reason: string) =>
      apiSend<RescheduleRequest>(`/appointments/${id}/reschedule-requests`, "POST", {
        proposed_slot_start: proposedSlotStart,
        reason,
      }),
    notes: (id: string) => apiGet<TreatmentNote[]>(`/appointments/${id}/treatment-notes`),
    addNote: (id: string, content: string) =>
      apiSend<TreatmentNote>(`/appointments/${id}/treatment-notes`, "POST", { content }),
  },
  queue: {
    live: (date: string, vetId: string) =>
      apiGet<ListResponse<QueueEntry>>(`/queue/live${query({ date, vet_id: vetId })}`, true),
  },
  schedule: {
    list: (date: string, vetId?: string) =>
      apiGet<ListResponse<ScheduleEntry>>(`/schedule${query({ date, vet_id: vetId })}`, true),
  },
  shifts: {
    list: (date?: string, vetId?: string) =>
      apiGet<Shift[]>(`/shifts${query({ date, vet_id: vetId })}`),
    create: (payload: {
      vet_id: string;
      shift_date: string;
      start_time: string;
      end_time: string;
    }) => apiSend<Shift>("/shifts", "POST", payload),
    bulkPreview: (payload: BulkShiftCreatePayload) =>
      apiSend<BulkShiftPreview>("/shifts/bulk/preview", "POST", payload),
    bulkCreate: (payload: BulkShiftCreatePayload) =>
      apiSend<BulkShiftResult>("/shifts/bulk", "POST", payload),
    update: (id: string, payload: { shift_date?: string; start_time?: string; end_time?: string }) =>
      apiSend<Shift>(`/shifts/${id}`, "PATCH", payload),
    remove: (id: string) => apiSend<{ message: string }>(`/shifts/${id}`, "DELETE"),
  },
  rescheduleRequests: {
    list: (status?: string) =>
      apiGet<RescheduleRequest[]>(`/reschedule-requests${query({ status })}`),
    approve: (id: string, reviewNote?: string) =>
      apiSend<RescheduleRequest>(`/reschedule-requests/${id}/approve`, "POST", {
        review_note: reviewNote ?? null,
      }),
    reject: (id: string, reviewNote?: string) =>
      apiSend<RescheduleRequest>(`/reschedule-requests/${id}/reject`, "POST", {
        review_note: reviewNote ?? null,
      }),
  },
  notifications: {
    list: (options?: { unreadOnly?: boolean; limit?: number }) =>
      apiGet<Notification[]>(
        `/notifications${query({
          unread_only: options?.unreadOnly,
          limit: options?.limit ?? 100,
        })}`,
      ),
    markRead: (id: string) => apiSend<Notification>(`/notifications/${id}/read`, "POST"),
  },
  audit: {
    list: (params?: { entityId?: string; action?: string; limit?: number }) =>
      apiGet<AuditLog[]>(
        `/audit-logs${query({
          entity_id: params?.entityId,
          action: params?.action,
          limit: params?.limit ?? 100,
        })}`,
      ),
  },
};
