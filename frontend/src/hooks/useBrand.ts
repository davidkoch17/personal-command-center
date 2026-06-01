import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { api } from "@/lib/api"
import type { BrandVideoCreateRequest } from "@/lib/types"

export interface VideoCard {
  name: string
  title: string
  platform: string
  stage: string
  posting_date: string
  modified: string
}

export interface Pipeline {
  stages: string[]
  by_stage: Record<string, VideoCard[]>
}

export interface HorizontalSlice {
  section: string
  title: string
  filename: string
  videos: { name: string; title: string; stage: string; content: string }[]
}

export interface VideoSection {
  filename: string
  title: string
  content: string
}

export interface VideoWorkspaceState {
  name: string
  status: {
    title: string
    platform: string
    stage: string
    posting_date: string
    [k: string]: unknown
  }
  stages: string[]
  sections: VideoSection[]
}

export function usePipeline() {
  return useQuery({
    queryKey: ["brand", "pipeline"],
    queryFn: () => api.get<Pipeline>("/api/brand"),
  })
}

export function useHorizontalSlice(section: string) {
  return useQuery({
    queryKey: ["brand", "slice", section],
    queryFn: () => api.get<HorizontalSlice>(`/api/brand/all/${section}`),
  })
}

export function useVideoWorkspace(name: string | undefined) {
  return useQuery({
    queryKey: ["brand", "video", name],
    queryFn: () =>
      api.get<VideoWorkspaceState>(`/api/brand/videos/${encodeURIComponent(name!)}`),
    enabled: !!name,
  })
}

export function useCreateVideo() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (req: BrandVideoCreateRequest) =>
      api.post<{ ok: boolean; name: string; path: string }>("/api/brand/videos", req),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["brand"] }),
  })
}

export function useRunBrandSkill(name: string | undefined) {
  return useMutation({
    mutationFn: ({ skill, question }: { skill: string; question?: string }) =>
      api.post<{ ok: boolean; run_id: string }>(
        `/api/brand/videos/${encodeURIComponent(name!)}/skill`,
        { skill, question },
      ),
  })
}
