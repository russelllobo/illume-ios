import JSZip from 'jszip';
import { parseEpub } from '../src/documents';
import { documentPath } from '../src/lib';
import { SUPABASE_URL } from '../src/config';
import { signIn, loadLibrary } from '../src/supabase';

async function makeEpub(): Promise<Uint8Array> {
  const zip = new JSZip();
  zip.file('mimetype', 'application/epub+zip');
  zip.file(
    'META-INF/container.xml',
    `<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>`
  );
  zip.file(
    'OEBPS/content.opf',
    `<?xml version="1.0"?><package xmlns="http://www.idpf.org/2007/opf" version="3.0" unique-identifier="id"><metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>Smoke Book</dc:title><dc:creator>Test Author</dc:creator></metadata><manifest><item id="c1" href="ch1.xhtml" media-type="application/xhtml+xml"/><item id="c2" href="ch2.xhtml" media-type="application/xhtml+xml"/></manifest><spine><itemref idref="c1"/><itemref idref="c2"/></spine></package>`
  );
  const para = 'Lorem ipsum dolor sit amet consectetur adipiscing elit sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.';
  zip.file('OEBPS/ch1.xhtml', `<html><body><h1>Chapter One</h1><p>${para}</p><p>${para} Second.</p></body></html>`);
  zip.file('OEBPS/ch2.xhtml', `<html><body><h1>Chapter Two</h1><p>${para} Third.</p></body></html>`);
  return new Uint8Array(await zip.generateAsync({ type: 'uint8array' }));
}

describe('sim-blocked functional smoke', () => {
  it('parses a real EPUB end to end', async () => {
    const data = await makeEpub();
    const { book } = await parseEpub(data, 'smoke.epub');
    expect(book.title).toBe('Smoke Book');
    expect(book.author).toBe('Test Author');
    expect(book.chapters).toEqual(['Chapter One', 'Chapter Two']);
    expect(book.paragraphs.length).toBeGreaterThanOrEqual(4);
  }, 30000);

  it('storage paths are sane', () => {
    const p = documentPath('ABC-USER', 'DEF-BOOK', 'My File.epub', 'epub');
    expect(p).toBe('abc-user/def-book/My-File.epub');
  });

  it('supabase endpoint reachable, bad creds rejected cleanly', async () => {
    expect(SUPABASE_URL).toContain('supabase.co');
    await expect(signIn('no-such-user@example.com', 'wrongpassword123')).rejects.toThrow();
  }, 30000);

  it('rest rejects bad token', async () => {
    await expect(loadLibrary('bogus-token')).rejects.toThrow();
  }, 30000);
});
