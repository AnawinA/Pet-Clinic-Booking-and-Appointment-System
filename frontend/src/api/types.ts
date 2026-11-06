export type UserRole = "OWNER" | "VET" | "STAFF";

export type AppointmentStatus =
  | "BOOKED"
  | "CHECKED_IN"
  | "IN_TREATMENT"
  | "COMPLETED"
  | "NO_SHOW"
  | "CANCELLED";

export interface User {
  id: string;
  email: string;
  full_name: string;
  phone: string | null;
  role: UserRole;
  is_active: boolean;
  created_at: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
  expires_at: string;
  user: User;
}

export interface Pet {
  id: string;
  owner_id: string;
  name: string;
  species: string;
  breed: string | null;
  sex: string | null;
  birth_date: string | null;
  weight_kg: string | null;
  medical_notes: string | null;
  photo_updated_at: string | null;
  created_at: string;
}

export interface PetCreate {
  name: string;
  species: string;
  breed?: string | null;
  sex?: string | null;
  birth_date?: string | null;
  weight_kg?: number | null;
  medical_notes?: string | null;
}

export interface Vet {
  id: string;
  full_name: string;
}

export interface AvailabilitySlot {
  vet_id: string;
  vet_name: string;
  slot_start: string;
  slot_end: string;
}

export interface Appointment {
  id: string;
  owner_id: string;
  owner_name: string | null;
  pet_id: string;
  pet_name: string | null;
  vet_id: string;
  vet_name: string | null;
  slot_start: string;
  slot_end: string;
  status: AppointmentStatus;
  symptoms: string;
  cancel_reason: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface QueueEntry {
  appointment_id: string;
  vet_id: string;
  vet_name: string;
  owner_id: string;
  owner_name: string;
  pet_id: string;
  pet_name: string;
  slot_start: string;
  slot_end: string;
  status: AppointmentStatus;
  ahead_count: number;
  estimated_start: string | null;
  updated_at: string;
}

export interface ScheduleEntry {
  appointment_id: string;
  version: number;
  vet_id: string;
  owner_id: string;
  owner_name: string;
  pet_id: string;
  pet_name: string;
  slot_start: string;
  slot_end: string;
  status: AppointmentStatus;
  symptoms: string;
  estimated_start: string | null;
  updated_at: string;
}

export interface QueuePosition {
  appointment_id: string;
  ahead_count: number;
  estimated_start: string | null;
  status: AppointmentStatus;
}

export interface Shift {
  id: string;
  vet_id: string;
  vet_name: string | null;
  shift_date: string;
  start_time: string;
  end_time: string;
  created_by: string;
  created_at: string;
}

export interface TreatmentNote {
  id: string;
  appointment_id: string;
  version: number;
  content: string;
  created_by: string;
  author_name: string | null;
  created_at: string;
}

export interface PetHistoryEntry {
  appointment: Appointment;
  treatment_notes: TreatmentNote[];
}

export interface RescheduleRequest {
  id: string;
  appointment_id: string;
  requested_by: string;
  requester_name: string | null;
  proposed_slot_start: string;
  reason: string;
  status: "PENDING" | "APPROVED" | "REJECTED";
  reviewed_by: string | null;
  reviewed_at: string | null;
  review_note: string | null;
  created_at: string;
}

export interface Notification {
  id: string;
  event_id: string;
  type: string;
  title: string;
  message: string;
  is_read: boolean;
  created_at: string;
}

export interface AuditLog {
  id: number;
  actor_id: string | null;
  actor_role: UserRole | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  request_id: string | null;
  created_at: string;
}

export interface ListResponse<T> {
  items: T[];
  server_time: string;
  etag?: string | null;
}
