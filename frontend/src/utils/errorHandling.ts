import type { AxiosError } from 'axios'

export const getApiErrorMessage = (error: unknown, fallback: string): string => {
  const axiosError = error as AxiosError<{ detail?: string; msg?: string }>
  const detail = axiosError?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  const msg = axiosError?.response?.data?.msg
  if (typeof msg === 'string' && msg.trim()) return msg
  const message = axiosError?.message
  if (typeof message === 'string' && message.trim()) return message
  return fallback
}
