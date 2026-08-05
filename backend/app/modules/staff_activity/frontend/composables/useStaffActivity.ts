export interface StaffActivityLog {
  id: string;
  clinic_id: string;
  user_id: string | null;
  action_type: string;
  entity_type: string | null;
  entity_id: string | null;
  details: Record<string, unknown>;
  timestamp: string;
}

export interface StaffActivityLogListResponse {
  items: StaffActivityLog[];
  total: number;
}

export function useStaffActivity() {
  const api = useApi();

  async function list(
    filters: Record<string, any> = {},
  ): Promise<StaffActivityLogListResponse> {
    const qs = new URLSearchParams();
    for (const [k, v] of Object.entries(filters)) {
      if (v === undefined || v === null || v === "") continue;
      qs.append(k, String(v));
    }
    const url = `/api/v1/staff_activity/${qs.toString() ? `?${qs.toString()}` : ""}`;
    return await api.get<StaffActivityLogListResponse>(url);
  }

  async function get(id: string): Promise<StaffActivityLog> {
    return await api.get<StaffActivityLog>(`/api/v1/staff_activity/${id}`);
  }

  return { list, get };
}
