const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

/**
 * API client for the interview system backend.
 * All methods throw on HTTP errors with descriptive messages.
 */

async function request(path, options = {}) {
  const url = `${API_BASE}${path}`;
  const res = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    ...options,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Request failed: ${res.status}`);
  }

  return res.json();
}

// ── Sessions ────────────────────────────────────────────────────────────────

export async function createSession(role) {
  return request('/api/v1/sessions', {
    method: 'POST',
    body: JSON.stringify({ role }),
  });
}

export async function getSession(sessionId) {
  return request(`/api/v1/sessions/${sessionId}`);
}

// ── Resume ──────────────────────────────────────────────────────────────────

export async function uploadResume(sessionId, file) {
  const formData = new FormData();
  formData.append('file', file);

  const url = `${API_BASE}/api/v1/sessions/${sessionId}/resume`;
  const res = await fetch(url, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — browser sets it with boundary for FormData
  });

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Upload failed: ${res.status}`);
  }

  return res.json();
}

// ── Interview ───────────────────────────────────────────────────────────────

export async function startInterview(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/start`, {
    method: 'POST',
  });
}

export async function getQuestions(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/questions`);
}

export async function getQuestion(sessionId, index) {
  return request(`/api/v1/sessions/${sessionId}/questions/${index}`);
}

export async function submitAnswer(sessionId, questionId, answerText) {
  return request(`/api/v1/sessions/${sessionId}/answers`, {
    method: 'POST',
    body: JSON.stringify({
      question_id: questionId,
      answer_text: answerText,
    }),
  });
}

// ── Summary ─────────────────────────────────────────────────────────────────

export async function generateSummary(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/summary`, {
    method: 'POST',
  });
}

export async function getSummary(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/summary`);
}

export async function getProgress(sessionId) {
  return request(`/api/v1/sessions/${sessionId}/progress`);
}
