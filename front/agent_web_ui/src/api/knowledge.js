const KNOWLEDGE_API_BASE = '/knowledge-api'

async function parseResponse(response) {
  let payload = null

  try {
    payload = await response.json()
  } catch (error) {
    payload = null
  }

  if (!response.ok) {
    const detail = payload?.detail || payload?.message || `HTTP ${response.status}`
    throw new Error(detail)
  }

  return payload
}

export async function uploadKnowledgeFile(formData) {
  const response = await fetch(`${KNOWLEDGE_API_BASE}/upload`, {
    method: 'POST',
    body: formData
  })

  return parseResponse(response)
}

export async function queryKnowledge(data) {
  const response = await fetch(`${KNOWLEDGE_API_BASE}/query`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json'
    },
    body: JSON.stringify(data)
  })

  return parseResponse(response)
}
