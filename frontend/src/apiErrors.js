function responseMessage(error) {
  const message = error?.response?.data?.error?.message
  return typeof message === 'string' && message.trim() ? message.trim() : ''
}

export function shouldClearAuthentication(status, url = '') {
  return status === 401 && !String(url).includes('/auth/login')
}

export function toApiError(error, url = '') {
  const status = error?.response?.status
  let message

  if (status === 401) {
    message = url.includes('/auth/login')
      ? responseMessage(error) || 'Email or password is incorrect.'
      : 'Your session has expired. Please log in again.'
  } else if (status === 403) {
    message = 'You do not have permission to complete this action.'
  } else if (status === 404) {
    message = 'The requested FitTrack item could not be found. Refresh and try again.'
  } else if (status === 422 || status === 400) {
    message = responseMessage(error) || 'Check the information and try again.'
  } else if (status === 429) {
    message = 'Too many requests. Wait a moment before trying again.'
  } else if (status >= 500) {
    message = 'FitTrack could not complete the request right now. Please try again.'
  } else if (status) {
    message = responseMessage(error) || 'The request could not be completed.'
  } else if (error?.code === 'ECONNABORTED' || error?.code === 'ETIMEDOUT') {
    message = 'FitTrack did not respond in time. Check your connection and try again.'
  } else if (error?.code === 'ERR_CANCELED') {
    message = 'The request was canceled.'
  } else {
    message = 'Unable to reach FitTrack. Check your connection and try again.'
  }

  const normalized = new Error(message)
  normalized.status = status
  normalized.code = error?.response?.data?.error?.code || error?.code || 'request_failed'
  return normalized
}
