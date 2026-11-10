export type UserRole = "FAMILY" | "ELDERLY";

export type LinkStatus = "PENDING" | "APPROVED" | "REJECTED" | "REVOKED";

export type ReminderStatus =
  | "PENDING"
  | "PROCESSING"
  | "AUDIO_READY"
  | "FAILED"
  | "COMPLETED"
  | "CANCELLED";

export type Recurrence = "ONCE" | "DAILY" | "WEEKLY";

export interface User {
  id: number;
  full_name: string;
  phone_number: string;
  role: UserRole;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: "bearer";
  user: User;
}

export interface FamilyLink {
  id: number;
  family_user_id: number;
  elderly_user_id: number;
  family_name: string;
  elderly_name: string;
  status: LinkStatus;
  requested_at: string;
  responded_at: string | null;
  created_at: string;
}

export interface ReminderLog {
  id: number;
  reminder_id: number;
  event_type: string;
  event_message: string | null;
  created_at: string;
}

export interface Reminder {
  id: number;
  title: string;
  message: string;
  elderly_user_id: number;
  created_by: number;
  scheduled_at: string;
  recurrence: Recurrence;
  status: ReminderStatus;
  created_at: string;
  updated_at: string;
  logs: ReminderLog[];
}

export interface AudioOccurrence {
  occurrence_at: string;
  status: ReminderStatus;
  audio_available: boolean;
  generated_at: string | null;
  attempt_count: number;
}

export interface ReminderAudioMetadata {
  reminder_id: number;
  occurrences: AudioOccurrence[];
}

export interface AuthSession {
  accessToken: string;
  user: User;
}