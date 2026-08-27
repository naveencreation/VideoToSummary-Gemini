import os
import sys
import time
import argparse
import subprocess
import shutil
from pathlib import Path

def load_dotenv_file(env_path: Path):
    """
    Simple fallback parser for .env files to avoid external dependencies.
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

def find_ffmpeg(custom_path=None):
    """
    Locates ffmpeg executable.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and p.name.lower().startswith("ffmpeg"):
            return str(p)
        if p.is_dir():
            exe = p / ("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if exe.is_file():
                return str(exe)

    # Check common system install locations
    common_locations = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\ffmpeg.exe",
    ]
    for loc in common_locations:
        if os.path.isfile(loc):
            return loc

    which_path = shutil.which("ffmpeg")
    if which_path:
        return which_path

    return None

def split_audio_into_chunks(audio_file: Path, chunk_minutes: int, ffmpeg_bin: str, output_dir: Path) -> list:
    """
    Splits an audio file into fixed minute segments using FFmpeg.
    Returns a list of tuples: (chunk_file_path, start_seconds, duration_seconds)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    chunk_seconds = chunk_minutes * 60

    print(f"\n[CHUNKING] Splitting '{audio_file.name}' into ~{chunk_minutes}-minute chunks using FFmpeg...")
    
    pattern = str(output_dir / "chunk_%03d.wav")
    cmd = [
        ffmpeg_bin, "-y",
        "-i", str(audio_file),
        "-f", "segment",
        "-segment_time", str(chunk_seconds),
        "-c", "copy",
        pattern
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed to chunk audio: {e.stderr.decode('utf-8', errors='ignore')[-300:]}")
        sys.exit(1)

    chunk_files = sorted(list(output_dir.glob("chunk_*.wav")))
    print(f"[CHUNKING] Successfully split into {len(chunk_files)} audio chunks.")

    chunks_metadata = []
    for idx, chunk_path in enumerate(chunk_files):
        start_sec = idx * chunk_seconds
        chunks_metadata.append((chunk_path, start_sec))

    return chunks_metadata

def format_timestamp(seconds: int) -> str:
    """Formats seconds into MM:SS or HH:MM:SS."""
    m, s = divmod(seconds, 60)
    h, m = divmod(m, 60)
    if h > 0:
        return f"{h:02d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"

def transcribe_chunk(client_or_genai, is_new_sdk: bool, chunk_file: Path, start_seconds: int, model_name: str) -> str:
    """
    Transcribes a single audio chunk using Gemini.
    """
    start_time_str = format_timestamp(start_seconds)
    print(f" -> Uploading chunk '{chunk_file.name}' (Starts at {start_time_str})...")

    prompt = (
        f"Transcribe this audio chunk accurately and verbatim.\n"
        f"CRITICAL: The audio of this chunk starts at timestamp [{start_time_str}]. "
        f"Please format all timestamps relative to the whole audio file starting from [{start_time_str}] onwards. "
        f"Include speaker labels (e.g. Speaker 1, Speaker 2) and clean paragraph formatting."
    )

    if is_new_sdk:
        audio_file = client_or_genai.files.upload(file=str(chunk_file))
        
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = client_or_genai.files.get(name=audio_file.name)

        if audio_file.state.name == "FAILED":
            raise ValueError(f"File processing failed: {audio_file.error.message}")

        response = client_or_genai.models.generate_content(
            model=model_name,
            contents=[audio_file, prompt]
        )
        
        try:
            client_or_genai.files.delete(name=audio_file.name)
        except Exception:
            pass

        return response.text
    else:
        audio_file = client_or_genai.upload_file(str(chunk_file))
        
        while audio_file.state.name == "PROCESSING":
            time.sleep(2)
            audio_file = client_or_genai.get_file(audio_file.name)

        model = client_or_genai.GenerativeModel(model_name)
        response = model.generate_content([audio_file, prompt])

        try:
            audio_file.delete()
        except Exception:
            pass

        return response.text

def main():
    script_dir = Path(__file__).parent.resolve()
    load_dotenv_file(script_dir / ".env")

    parser = argparse.ArgumentParser(
        description="Chunked Audio Transcription using Gemini 2.5 Flash Lite"
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        default="video.wav",
        help="Input audio file path (default: video.wav)"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        default="final_transcript.md",
        help="Final stitched transcript file path (default: final_transcript.md)"
    )
    parser.add_argument(
        "-m", "--model",
        type=str,
        default="gemini-2.5-flash-lite",
        help="Gemini model (default: gemini-2.5-flash-lite)"
    )
    parser.add_argument(
        "-c", "--chunk-minutes",
        type=int,
        default=10,
        help="Duration of each chunk in minutes (default: 10 minutes)"
    )
    parser.add_argument(
        "--ffmpeg-path",
        type=str,
        default=r"C:\ffmpeg\bin",
        help="Path to ffmpeg directory or executable"
    )
    parser.add_argument(
        "--keep-chunks",
        action="store_true",
        help="Keep temporary chunk audio files after completion"
    )

    args = parser.parse_args()

    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("[ERROR] GEMINI_API_KEY not found in .env or environment variables.")
        sys.exit(1)

    # Initialize Gemini SDK
    is_new_sdk = False
    try:
        from google import genai
        client_sdk = genai.Client(api_key=api_key)
        is_new_sdk = True
        print("[INFO] Using official 'google-genai' SDK.")
    except ImportError:
        try:
            import google.generativeai as legacy_genai
            legacy_genai.configure(api_key=api_key)
            client_sdk = legacy_genai
            is_new_sdk = False
            print("[INFO] Using 'google-generativeai' SDK.")
        except ImportError:
            print("\n[ERROR] Google GenAI SDK not installed.")
            print("Please run: pip install google-genai\n")
            sys.exit(1)

    input_audio = Path(args.input).resolve()
    if not input_audio.is_file():
        print(f"[ERROR] Audio file not found: {input_audio}")
        sys.exit(1)

    ffmpeg_bin = find_ffmpeg(args.ffmpeg_path)
    if not ffmpeg_bin:
        print("[ERROR] FFmpeg not found. Please provide valid --ffmpeg-path.")
        sys.exit(1)

    chunks_dir = script_dir / "audio_chunks"
    transcripts_dir = script_dir / "chunk_transcripts"
    transcripts_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Chunk audio
    chunks = split_audio_into_chunks(input_audio, args.chunk_minutes, ffmpeg_bin, chunks_dir)

    # Step 2: Transcribe each chunk sequentially with caching
    print(f"\n[TRANSCRIPTION] Starting chunked transcription using '{args.model}'...")
    print("=" * 65)

    transcribed_files = []

    for idx, (chunk_file, start_sec) in enumerate(chunks, 1):
        chunk_transcript_file = transcripts_dir / f"{chunk_file.stem}_transcript.txt"
        transcribed_files.append(chunk_transcript_file)

        # Check if already transcribed (caching)
        if chunk_transcript_file.exists() and chunk_transcript_file.stat().st_size > 0:
            print(f"[{idx}/{len(chunks)}] Chunk '{chunk_file.name}' already transcribed. (Skipping re-transcription)")
            continue

        print(f"[{idx}/{len(chunks)}] Processing Chunk: {chunk_file.name} (Offset: {format_timestamp(start_sec)})")
        
        retry_count = 0
        success = False
        while retry_count < 3 and not success:
            try:
                text = transcribe_chunk(client_sdk, is_new_sdk, chunk_file, start_sec, args.model)
                chunk_transcript_file.write_text(text, encoding="utf-8")
                print(f"    [SUCCESS] Saved chunk transcript -> {chunk_transcript_file.name}")
                success = True
            except Exception as e:
                retry_count += 1
                print(f"    [RETRY {retry_count}/3] Chunk failed: {e}. Retrying in 5s...")
                time.sleep(5)

        if not success:
            print(f"[ERROR] Failed to transcribe chunk '{chunk_file.name}' after 3 attempts.")

    # Step 3: Patch & Stitch all transcripts together
    print("\n" + "=" * 65)
    print("[STITCHING] Combining all chunk transcripts into final output...")

    final_output_path = Path(args.output).resolve()
    with open(final_output_path, "w", encoding="utf-8") as outfile:
        outfile.write(f"# Complete Audio Transcript\n\n")
        outfile.write(f"- **Source File**: `{input_audio.name}`\n")
        outfile.write(f"- **Model**: `{args.model}`\n")
        outfile.write(f"- **Total Chunks**: {len(chunks)}\n\n")
        outfile.write("---\n\n")

        for idx, (chunk_file, start_sec) in enumerate(chunks, 1):
            txt_file = transcripts_dir / f"{chunk_file.stem}_transcript.txt"
            if txt_file.exists():
                content = txt_file.read_text(encoding="utf-8").strip()
                outfile.write(f"## Part {idx} (Starts at [{format_timestamp(start_sec)}])\n\n")
                outfile.write(content)
                outfile.write("\n\n---\n\n")

    print(f"[SUCCESS] Final complete transcript saved to: {final_output_path}")

    # Cleanup temporary audio chunks if not requested to keep
    if not args.keep_chunks:
        print("[CLEANUP] Cleaning up temporary audio chunk files...")
        shutil.rmtree(chunks_dir, ignore_errors=True)

    print("\n🎉 ALL DONE! Your final patched transcript is ready.")

if __name__ == "__main__":
    main()
