import { AnswerData, Patient, Source } from '../types';

export class QueryApiError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'QueryApiError';
  }
}

interface QueryPatientPayload {
  age?: number;
  sex?: string;
  contraindications: string[];
  anamnesis?: string;
}

interface QuerySource {
  source_number: number;
  title: string;
  path: string | null;
  snippet: string | null;
  url: string | null;
}

interface QueryResponse {
  query_id: string;
  answer: string;
  sources: QuerySource[];
}

const NO_ANSWER_TEXT = 'не найден подтверждающий источник';

export function toPatientPayload(patient: Patient | null): QueryPatientPayload | undefined {
  if (!patient) return undefined;

  const contraindications = [...patient.contraindications, ...patient.allergies].filter(Boolean);
  const anamnesis = patient.chronic.length > 0 ? patient.chronic.join(', ') : undefined;

  return {
    age: patient.age,
    sex: patient.sex,
    contraindications,
    ...(anamnesis ? { anamnesis } : {}),
  };
}

export function extractCitations(answer: string): { text: string; citations: number[] } {
  const pattern = /\[(?:Источник\s+)?(\d+)\]/g;
  const citations = [...new Set(
    [...answer.matchAll(pattern)].map((match) => Number(match[1])),
  )].sort((a, b) => a - b);

  const text = answer.replace(/\[(?:Источник\s+)?(\d+)\]/g, ' ').replace(/\s{2,}/g, ' ').trim();
  return { text, citations };
}

export function mapQueryResponse(question: string, data: QueryResponse): AnswerData {
  const { text, citations } = extractCitations(data.answer);

  const sources: Source[] = data.sources.map((source) => ({
    id: source.source_number,
    title: source.title,
    wikiDate: source.path ?? '',
    quote: source.snippet ?? '',
    url: source.url ?? '',
  }));

  return {
    question,
    timestamp: new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }),
    queryId: data.query_id,
    sections: [
      {
        key: 'summary',
        title: 'Кратко',
        text,
        citations,
      },
    ],
    sources,
  };
}

export function isNoAnswer(data: QueryResponse): boolean {
  return data.sources.length === 0 || data.answer.toLowerCase().includes(NO_ANSWER_TEXT);
}

export async function askKnowledgeBase(
  question: string,
  patient: Patient | null,
): Promise<QueryResponse> {
  const patientPayload = toPatientPayload(patient);
  const apiBase = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000';
  const response = await fetch(`${apiBase}/api/v1/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      question,
      top_k: 5,
      ...(patientPayload ? { patient: patientPayload } : {}),
    }),
  });

  if (!response.ok) {
    let detail = `Ошибка запроса: ${response.status}`;
    try {
      const payload = await response.json();
      if (typeof payload?.detail === 'string') {
        detail = payload.detail;
      }
    } catch {
      // keep status message
    }
    throw new QueryApiError(detail);
  }

  return response.json() as Promise<QueryResponse>;
}
