/**
 * Translators turn a pasal into Lean code with a fixed signature.
 *
 * - `anthropic`: Claude via the Messages API (needs ANTHROPIC_API_KEY or an
 *   `ant auth login` profile).
 * - `fixtures`: hand-written example translations, including deliberate
 *   variation and mistakes, so the whole pipeline and UI can run without an
 *   API key. Results from it are marked illustrative everywhere.
 */
import Anthropic from '@anthropic-ai/sdk';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import type { BenchPasal } from '../src/lab/types';
import { fixtureFor } from './fixtures';
import { LEAN_DIR } from './lean';

export interface TranslateRequest {
  pasal: BenchPasal;
  /** The text to translate (the original, or a perturbed copy). */
  text: string;
  /** Sample index for the original text; perturbation id for a perturbed one. */
  sample: number | { perturbation: string };
}

export interface Translator {
  name: string;
  illustrative: boolean;
  translate(req: TranslateRequest): Promise<string>;
}

export function signature(p: BenchPasal): string {
  const params = p.params.map((x) => `(${x.name} : ${x.type})`).join(' ');
  return `def ${p.fn} ${params} : ${p.returns}`;
}

export const fixtureTranslator: Translator = {
  name: 'fixtures (contoh tulisan tangan)',
  illustrative: true,
  async translate({ pasal, sample }) {
    return fixtureFor(pasal.id, sample);
  },
};

const MODEL = 'claude-opus-5-5';

export async function anthropicTranslator(): Promise<Translator> {
  const client = new Anthropic();
  const prelude = await readFile(path.join(LEAN_DIR, 'HukumOS/Prelude.lean'), 'utf8');

  // Stable across every request so the prefix is cached.
  const system = `You translate articles (pasal) of Indonesian legislation into Lean 4 definitions.

You write against this library, which is already imported and opened (\`open HukumOS\`):

\`\`\`lean
${prelude}
\`\`\`

Rules:
- Output exactly one \`\`\`lean code block and nothing after it.
- Define the requested function with exactly the requested name and signature. You may add helper definitions before it.
- Translate only what the article says. Do not add conditions, exceptions or numbers that are not in the text. Where the text is genuinely unclear, choose the most natural reading and say which in a comment.
- After every line that comes from the text, add a comment \`-- dari: "<exact quote from the article>"\` quoting the words it encodes, copied verbatim.
- Core Lean 4 only (no Mathlib). No \`sorry\`, \`axiom\`, \`IO\`, \`#eval\`, attributes, \`import\`, \`namespace\` or \`open\` lines.
- Do not write proofs; definitions only.`;

  return {
    name: `anthropic:${MODEL}`,
    illustrative: false,
    async translate({ pasal, text }) {
      const user = `Article: UU 14/2008 ${pasal.cite}

"""
${text}
"""
${pasal.context ? `\nContext from related provisions (for reference, do not translate): ${pasal.context}\n` : ''}
Write this function:

\`\`\`lean
${signature(pasal)} := ...
\`\`\``;

      const response = await client.beta.messages.create({
        model: MODEL,
        max_tokens: 16000,
        betas: ['server-side-fallback-2026-07-01'],
        fallbacks: 'default',
        output_config: { effort: 'high' },
        cache_control: { type: 'ephemeral' },
        system,
        messages: [{ role: 'user', content: user }],
      });
      if (response.stop_reason === 'refusal') throw new Error(`Refused: ${response.stop_details?.category ?? 'unknown'}`);
      if (response.stop_reason === 'max_tokens') throw new Error('Hit max_tokens');
      const text_ = response.content.flatMap((b) => (b.type === 'text' ? [b.text] : [])).join('\n');
      const blocks = [...text_.matchAll(/```lean\s*\n([\s\S]*?)```/g)];
      if (blocks.length === 0) throw new Error('No ```lean block in the response');
      return blocks[blocks.length - 1][1];
    },
  };
}
