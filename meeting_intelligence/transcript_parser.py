"""meeting_intelligence/transcript_parser.py — Parses and chunks meeting transcripts"""
import re
from typing import Dict, List


class TranscriptParser:
    """
    Accepts raw transcript text (.txt or plain string from PDF extraction).
    Cleans, normalises speaker names, and chunks into segments.
    Output feeds directly into DecisionExtractor.
    """

    def parse(self, raw_text: str) -> Dict:
        """Main entry point — returns structured transcript dict"""
        if not raw_text or not raw_text.strip():
            return {"segments": [], "speakers": [], "word_count": 0, "error": "empty transcript"}

        cleaned = self._clean(raw_text)
        segments = self._segment(cleaned)
        speakers = self._extract_speakers(segments)

        return {
            "raw_length": len(raw_text),
            "word_count": len(cleaned.split()),
            "speakers": speakers,
            "segments": segments,
            "full_text": cleaned,
        }

    def _clean(self, text: str) -> str:
        """Remove timestamps, normalise whitespace, fix encoding"""
        # Remove common timestamp patterns [00:01:23] or (00:01:23)
        text = re.sub(r"[\[\(]\d{1,2}:\d{2}(:\d{2})?[\]\)]", "", text)
        # Normalise multiple newlines
        text = re.sub(r"\n{3,}", "\n\n", text)
        # Remove trailing whitespace per line
        text = "\n".join(line.rstrip() for line in text.splitlines())
        return text.strip()

    def _segment(self, text: str) -> List[Dict]:
        """Split transcript into speaker segments"""
        segments = []
        # Pattern: "Speaker Name: text" or "SPEAKER NAME: text"
        pattern = re.compile(r"^([A-Z][A-Za-z\s\.\-]+):\s+(.+)", re.MULTILINE)
        matches = list(pattern.finditer(text))

        if not matches:
            # No speaker labels — treat as single block, chunk by paragraph
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            return [{"speaker": "Unknown", "text": p, "index": i} for i, p in enumerate(paragraphs)]

        for i, match in enumerate(matches):
            speaker = match.group(1).strip()
            start = match.start(2)
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            segment_text = text[start:end].strip()
            if segment_text:
                segments.append({
                    "index": i,
                    "speaker": speaker,
                    "text": segment_text,
                    "word_count": len(segment_text.split()),
                })
        return segments

    def _extract_speakers(self, segments: List[Dict]) -> List[str]:
        """Return unique speaker list preserving order of first appearance"""
        seen = set()
        speakers = []
        for seg in segments:
            sp = seg.get("speaker", "Unknown")
            if sp not in seen:
                seen.add(sp)
                speakers.append(sp)
        return speakers