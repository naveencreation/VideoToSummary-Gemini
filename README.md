# VideoToSummary-Gemini

An end-to-end Python pipeline to convert video recordings into audio, generate timestamps and accurate transcriptions with chunking using Google Gemini, and produce structured executive summaries.

---

## 📁 Repository Structure & File Placement

Place your input video in the root directory (e.g., `video.mp4`).

```
VideoToSummary-Gemini/
├── video.mp4                 <-- [INPUT] Place your source video here
├── video.wav                 <-- [GENERATED] Extracted audio from Step 1
├── convert_video_to_audio.py <-- Step 1: Video to Audio extractor
├── transcribe_with_gemini.py <-- Step 2: Chunking & Transcription
├── summarize_transcripts.py  <-- Step 3: Executive Summarizer
├── chunk_transcripts/        <-- [GENERATED] Per-chunk transcript text files
├── final_transcript.md       <-- [GENERATED] Full stitched transcript
├── summary.md                <-- [GENERATED] Final structured summary
├── .env.example              <-- Environment template
├── .env                      <-- Your Gemini API key configuration
└── README.md
```

---

## ⚙️ Prerequisites & Setup

### 1. Install FFmpeg
Ensure FFmpeg is installed and accessible on your system PATH.
- **Windows (winget)**: `winget install Gyan.FFmpeg`
- **Windows (manual)**: Download from [gyan.dev/ffmpeg/builds](https://www.gyan.dev/ffmpeg/builds/) and add the `bin` folder to your System PATH (or pass `--ffmpeg-path` to the scripts).
- **macOS (Homebrew)**: `brew install ffmpeg`
- **Linux (Ubuntu/Debian)**: `sudo apt update && sudo apt install ffmpeg`

### 2. Install Python Dependencies
```bash
pip install google-genai
```
*(Optional fallback: `pip install google-generativeai`)*

### 3. Configure API Key
Create a `.env` file from the provided template:

```bash
# Windows PowerShell
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Open `.env` and insert your Google Gemini API key:
```ini
GEMINI_API_KEY="your_actual_gemini_api_key"
```
> Get an API key from [Google AI Studio](https://aistudio.google.com/app/apikey).

---

## 🚀 Step-by-Step Workflow

### Step 1: Extract Audio from Video (`convert_video_to_audio.py`)

Extracts 16-bit lossless PCM WAV audio optimized for speech recognition (16kHz, mono).

**Usage:**
```bash
python convert_video_to_audio.py -i video.mp4 -t
```

**Common Options:**
| Argument | Description | Default |
| :--- | :--- | :--- |
| `-i, --input` | Path to video file or directory | *(Interactive prompt)* |
| `-o, --output` | Output audio file or directory path | Same directory as input |
| `-t, --transcription` | Optimize preset: Lossless WAV, 16kHz sample rate, Mono | `False` |
| `-f, --format` | Target format (`wav`, `flac`, `mp3`, `aac`, `m4a`, `ogg`) | `wav` |
| `--ffmpeg-path` | Custom path to FFmpeg binary/folder | Auto-detected |

---

### Step 2: Transcribe Audio with Gemini (`transcribe_with_gemini.py`)

Splits the audio into 10-minute segments, transcribes each segment sequentially with Gemini (including timestamp tags), and stitches all chunks into `final_transcript.md`.

*Features automatic caching: if a chunk fails or is interrupted, re-running the script resumes where it left off.*

**Usage:**
```bash
python transcribe_with_gemini.py -i video.wav -o final_transcript.md
```

**Common Options:**
| Argument | Description | Default |
| :--- | :--- | :--- |
| `-i, --input` | Input audio file path | `video.wav` |
| `-o, --output` | Output markdown transcript file | `final_transcript.md` |
| `-m, --model` | Gemini model name | `gemini-3.5-flash-lite` |
| `-c, --chunk-minutes`| Duration of each audio chunk in minutes | `10` |
| `--keep-chunks` | Keep temporary WAV chunk files after completion | `False` (deleted) |
| `--ffmpeg-path` | Custom path to FFmpeg binary/folder | `C:\ffmpeg\bin` / Auto |

---

### Step 3: Generate Master Summary (`summarize_transcripts.py`)

Reads all chunk transcripts from `chunk_transcripts/` in chronological order and prompts Gemini to produce a comprehensive, structured executive summary.

**Usage:**
```bash
python summarize_transcripts.py -m gemini-3.5-flash-lite -o summary.md
```

**Common Options:**
| Argument | Description | Default |
| :--- | :--- | :--- |
| `-d, --directory` | Directory containing `.txt` transcript chunks | `chunk_transcripts` |
| `-o, --output` | Output summary file name | `summary.txt` |
| `-m, --model` | Gemini model name | `gemini-3.5-flash-lite` |

---

## 📊 Summary Output Structure

The final `summary.md` document provides:
1. **Executive Summary**: Core topic, speakers/presenters, and primary objective.
2. **Key Discussion Points & Deep Dive**: Chronological and thematic breakdown with timestamps.
3. **Decisions & Outcomes**: Key conclusions agreed upon during the recording.
4. **Action Items & Next Steps**: Specific deliverables and assigned responsibilities.
5. **Important Mentions & Reference Timestamps**: Direct references to relevant parts of the video.