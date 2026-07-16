import React, { useMemo } from "react";
import { diff_match_patch } from "diff-match-patch";

/**
 * InlineDiff — renders a word-level diff between originalText and suggestedText.
 *
 * Deleted words are shown in red with strikethrough.
 * Added words are shown in green with an underline.
 * Unchanged words are shown in the default text color.
 *
 * Uses diff-match-patch's diff_wordMode equivalent (character diff after splitting
 * into word tokens) for precise, human-readable legal redlines.
 */
const dmp = new diff_match_patch();

const DIFF_DELETE = -1;
const DIFF_INSERT = 1;
const DIFF_EQUAL = 0;

/**
 * Compute a word-level diff using the character-level DMP engine by encoding
 * each word as a unicode character, diffing, then decoding back to words.
 * This is the official DMP technique for word-mode diffing.
 */
function wordDiff(text1, text2) {
  // Encode words → chars
  const charCodes = {};
  const chars = [];
  let charCount = 0;

  function encodeText(text) {
    const words = text.split(/(\s+)/); // preserve whitespace tokens
    return words
      .map((word) => {
        if (!(word in charCodes)) {
          charCodes[word] = charCount;
          chars[charCount] = word;
          charCount++;
        }
        return String.fromCodePoint(charCodes[word]);
      })
      .join("");
  }

  const encoded1 = encodeText(text1);
  const encoded2 = encodeText(text2);

  const diffs = dmp.diff_main(encoded1, encoded2, false);

  // Decode back to words
  return diffs.map(([op, encoded]) => {
    const decoded = Array.from(encoded)
      .map((ch) => chars[ch.codePointAt(0)])
      .join("");
    return [op, decoded];
  });
}

/**
 * When >55% of the content is changed, word-level interleaving becomes
 * unreadable. Switch to a cleaner two-block view: old text struck through,
 * new text below in green.
 */
function churnRatio(diffs) {
  let equalLen = 0, changedLen = 0;
  for (const [op, text] of diffs) {
    if (op === DIFF_EQUAL) equalLen += text.length;
    else changedLen += text.length;
  }
  const total = equalLen + changedLen;
  return total === 0 ? 0 : changedLen / total;
}

const InlineDiff = ({ originalText, suggestedText }) => {
  const { diffs, useBlockView } = useMemo(() => {
    if (!originalText && !suggestedText) return { diffs: [], useBlockView: false };
    if (!originalText) return { diffs: [[DIFF_INSERT, suggestedText]], useBlockView: false };
    if (!suggestedText) return { diffs: [[DIFF_EQUAL, originalText]], useBlockView: false };
    if (originalText === suggestedText) return { diffs: [[DIFF_EQUAL, originalText]], useBlockView: false };
    const d = wordDiff(originalText, suggestedText);
    return { diffs: d, useBlockView: churnRatio(d) > 0.55 };
  }, [originalText, suggestedText]);

  if (!diffs.length) return null;

  const hasChanges = diffs.some(([op]) => op !== DIFF_EQUAL);

  return (
    <div className="space-y-3 animate-fade-up" style={{ animationDelay: "0.2s" }}>
      <h4 className="text-[11px] text-slate-400 font-bold flex items-center gap-1.5 uppercase tracking-wider">
        <svg className="w-3.5 h-3.5 text-indigo-400" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
        </svg>
        AI Redline Suggestion
      </h4>

      <div
        className="p-3.5 rounded-xl space-y-2"
        style={{
          background: "rgba(6,9,17,0.6)",
          border: "1px solid rgba(148,163,184,0.08)",
        }}
      >
        {!hasChanges ? (
          <p className="text-[11px] text-slate-300 leading-relaxed">{originalText}</p>
        ) : useBlockView ? (
          /* Block view for high-churn rewrites — cleaner than interleaved word diff */
          <>
            <p className="text-[11px] leading-relaxed line-through decoration-red-500/60 decoration-[1.5px]"
               style={{ color: "rgb(252,129,129)", background: "rgba(239,68,68,0.06)", borderRadius: "6px", padding: "6px 8px" }}>
              {originalText}
            </p>
            <p className="text-[11px] leading-relaxed font-medium"
               style={{ color: "rgb(110,231,183)", background: "rgba(16,185,129,0.08)", borderRadius: "6px", padding: "6px 8px" }}>
              {suggestedText}
            </p>
          </>
        ) : (
          <p className="text-[11px] leading-relaxed">
            {diffs.map(([op, text], i) => {
              if (op === DIFF_DELETE) {
                return (
                  <span
                    key={i}
                    className="line-through decoration-red-500/70 decoration-[1.5px]"
                    style={{ color: "rgb(252, 129, 129)", background: "rgba(239,68,68,0.08)", borderRadius: "2px", padding: "0 2px" }}
                  >
                    {text}
                  </span>
                );
              }
              if (op === DIFF_INSERT) {
                return (
                  <span
                    key={i}
                    className="font-semibold"
                    style={{ color: "rgb(110, 231, 183)", background: "rgba(16,185,129,0.1)", borderRadius: "2px", padding: "0 2px" }}
                  >
                    {text}
                  </span>
                );
              }
              return (
                <span key={i} className="text-slate-300">
                  {text}
                </span>
              );
            })}
          </p>
        )}
      </div>

      {/* Legend */}
      {hasChanges && (
        <div className="flex items-center gap-3 text-[9px] text-slate-500">
          <span className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: "rgba(239,68,68,0.2)", border: "1px solid rgba(239,68,68,0.3)" }}
            />
            Removed
          </span>
          <span className="flex items-center gap-1">
            <span
              className="inline-block w-3 h-3 rounded-sm"
              style={{ background: "rgba(16,185,129,0.2)", border: "1px solid rgba(16,185,129,0.3)" }}
            />
            Added
          </span>
        </div>
      )}
    </div>
  );
};

export default InlineDiff;
