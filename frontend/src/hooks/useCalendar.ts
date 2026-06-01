import { useQuery } from "@tanstack/react-query"
import { api } from "@/lib/api"

export interface CalendarEvent {
  title: string
  start: string | null
  end: string | null
  location: string
  description: string
}

export interface CalendarResponse {
  configured: boolean
  events: CalendarEvent[]
}

export function useCalendar(days = 30) {
  return useQuery({
    queryKey: ["calendar", days],
    queryFn: () =>
      api.get<CalendarResponse>(`/api/integrations/calendar?days=${days}`),
  })
}
