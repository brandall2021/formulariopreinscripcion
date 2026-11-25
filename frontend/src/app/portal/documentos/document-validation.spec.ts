import { validateDocument } from './document-validation';

describe('validateDocument', () => {
  it('accepts a PDF under the 10 MB limit', () => {
    expect(validateDocument({ type: 'application/pdf', size: 1024 }))
      .toEqual({ valid: true, error: '' });
  });

  it('rejects unsupported MIME types', () => {
    expect(validateDocument({ type: 'image/gif', size: 1024 }).valid).toBeFalse();
  });

  it('rejects files larger than 10 MB', () => {
    expect(validateDocument({ type: 'image/png', size: 10485761 }).error)
      .toContain('10 MB');
  });
});
