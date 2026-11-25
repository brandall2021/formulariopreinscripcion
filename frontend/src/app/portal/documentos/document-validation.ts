export const MAX_DOCUMENT_BYTES = 10485760;
export const ALLOWED_DOCUMENT_MIMES = [
  'application/pdf', 'image/jpeg', 'image/png',
] as const;

export function validateDocument(file: Pick<File, 'type' | 'size'>) {
  if (!ALLOWED_DOCUMENT_MIMES.includes(file.type as typeof ALLOWED_DOCUMENT_MIMES[number])) {
    return { valid: false, error: 'Formato no permitido. Usá PDF, JPG o PNG.' };
  }
  if (file.size > MAX_DOCUMENT_BYTES) {
    return { valid: false, error: 'El archivo supera el máximo de 10 MB.' };
  }
  return { valid: true, error: '' };
}
