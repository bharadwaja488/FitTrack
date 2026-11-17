export function isRecord(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

export function isRecordArray(value) {
  return Array.isArray(value) && value.every(isRecord)
}

export async function loadDashboardSection(request, validate, unavailableMessage) {
  try {
    const response = await request()
    if (!validate(response?.data)) throw new Error(unavailableMessage)
    return { data: response.data, loading: false, error: '' }
  } catch (error) {
    return {
      data: null,
      loading: false,
      error: error?.message || unavailableMessage,
    }
  }
}

export function finiteDisplay(value, digits = 0) {
  if (value == null || value === '') return '—'
  const number = Number(value)
  return Number.isFinite(number)
    ? digits > 0 ? number.toFixed(digits) : Math.round(number).toLocaleString()
    : '—'
}

export function isIsoDate(value) {
  if (typeof value !== 'string') return false
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value)
  if (!match) return false
  const [, year, month, day] = match.map(Number)
  const parsed = new Date(Date.UTC(year, month - 1, day))
  return parsed.getUTCFullYear() === year
    && parsed.getUTCMonth() === month - 1
    && parsed.getUTCDate() === day
}
