import os
import sys
import argparse
import re
from pathlib import Path

def load_dotenv_file(env_path: Path):
    """
    Simple fallback parser for .env files.
    """
    if not env_path.is_file():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#') or '=' not in line:
                continue
            key, value = line.split('=', 1)
            key = key.strip()
            value = value.strip().strip("'").strip('"')
            if key and not os.environ.get(key):
                os.environ[key] = value

def extract_chunk_index(file_path: Path) -> int:
    """Extracts numerical index from filename for sorting (e.g. chunk_001_transcript.txt -> 1)."""
    match = re.search(r'chunk_(\d+)', file_path.name)
    if match:
        return int(match.group(1))
    return 0

def load_all_transcripts(transcripts_dir: Path) -> tuple:
    """Reads and concatenates all transcript text files in chronological order."""
    if not transcripts_dir.is_dir():
        print(f"[ERROR] Transcripts directory not found: {transcripts_dir}")
        return "", []

    txt_files = sorted(list(transcripts_dir.glob("*.txt")), key=extract_chunk_index)
    if not txt_files:
        print(f"[ERROR] No .txt transcript files found in {transcripts_dir}")
        return "", []

    full_text = []
    print(f"\n[INFO] Loading {len(txt_files)} transcript chunk(s) from '{transcripts_dir.name}':")
    for f in txt_files:
        print(f"  - Reading {f.name} ({f.stat().st_size} bytes)")
        content = f.read_text(encoding="utf-8").strip()
        full_text.append(f"--- START OF {f.name} ---\n{content}\n--- END OF {f.name} ---")

    combined_transcript = "\n\n".join(full_text)
    return combined_transcript, txt_files

def generate_summary_with_gemini(combined_text: str, model_name: str, api_key: str) -> str:
    """Sends the full combined transcript to Gemini API with an expert summarization prompt."""

    # Expert Master Prompt designed for comprehensive, high-value summarization
    system_prompt = (
        "You are an elite executive AI assistant, analyst, and transcription expert.\n"
        "You have been provided with the complete multi-chunk transcript of a recording.\n\n"
        "YOUR GOAL:\n"
        "Generate a comprehensive, highly structured, and deep summary of the entire transcript. "
        "Do NOT omit important context, technical details, audit/regulatory rules, or specific examples discussed.\n\n"
        "STRUCTURE YOUR SUMMARY AS FOLLOWS:\n\n"
        "# 📑 Executive Master Summary\n\n"
        "## 📌 High-Level Summary\n"
        "- A concise 4-6 bullet point executive overview of the core topic, purpose, and key conclusions of the discussion.\n\n"
        "## 🔑 Key Themes & Core Concepts\n"
        "- Detail the major themes covered throughout the recording with clear headings and explanation.\n\n"
        "## 🎯 Key Decisions, Action Items & Next Steps\n"
        "- List all explicit decisions made, required actions, owner/auditor responsibilities, or future roadmap items.\n\n"
        "## 👥 Speaker Contributions & Diarization Insights\n"
        "- Summarize key points, perspectives, and arguments presented by specific speakers (e.g., SPEAKER_0, SPEAKER_1).\n\n"
        "## 🔍 Comprehensive Topic-by-Topic Breakdown\n"
        "- In-depth narrative of each section of the discussion, incorporating specific technical jargon, rules, triggers, or processes.\n\n"
        "## ⏱️ Chronological Key Moments & Timestamps\n"
        "- Highlight critical discussion timestamps mentioned in the transcript and what was covered at those points.\n"
    )

    full_user_content = f"{system_prompt}\n\n=== FULL TRANSCRIPT DATA ===\n\n{combined_text}"

    # Try official google-genai SDK first, fallback to legacy google-generativeai
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        
        print(f"\n[GEMINI] Generating summary using model '{model_name}' via google-genai SDK...")
        response = client.models.generate_content(
            model=model_name,
            contents=full_user_content
        )
        return response.text

    except ImportError:
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            
            print(f"\n[GEMINI] Generating summary using model '{model_name}' via legacy SDK...")
            model = legacy_genai.GenerativeModel(model_name)
            response = model.generate_content(full_user_content)
            return response.text

        except ImportError:
            print("\n[ERROR] Neither 'google-genai' nor 'google-generativeai' SDK is installed.")
            print("Please run: pip install google-genai\n")
            sys.exit(1)

def main():
    script_dir = Path(__file__).parent.resolve()
    load_dotenv_file(script_dir / ".env")

    parser = argparse.ArgumentParser(
        description="Generate a comprehensive master summary from transcript chunks using Gemini 2.5 Flash Lite"
    )
    parser.add_argument(
        "-d", "--directory",
        type=str,
        default="chunk_transcripts",
        help="Directory containing transcript .txt files (default: chunk_transcripts)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="summary.txt",
        help="Output summary file (default: summary.txt)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="gemini-2.5-flash-lite",
        help="Gemini model name (default: gemini-2.5-flash-lite)"
    )

    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not found in .env or environment variables.")
        sys.exit(1)

    transcripts_dir = (script_dir / args.directory).resolve()
    combined_transcript, files = load_all_transcripts(transcripts_dir)

    if not combined_transcript:
        print("[ERROR] No content to summarize. Exiting.")
        sys.exit(1)

    summary_text = generate_summary_with_gemini(combined_transcript, args.model, api_key)

    output_path = (script_dir / args.output).resolve()
    output_path.write_text(summary_text, encoding="utf-8")

    print(f"\n" + "="*60)
    print(f" SUCCESS! Master Summary generated and saved.")
    print(f" Saved to: {output_path}")
    print(f" Total Chunks Summarized: {len(files)}")
    print(f"==================================================\n")

if __name__ == "__main__":
    main()
