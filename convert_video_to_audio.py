import os
import sys
import subprocess
import argparse
import shutil
from pathlib import Path

# Supported video extensions to scan for in batch mode
VIDEO_EXTENSIONS = {'.mp4', '.mkv', '.avi', '.mov', '.wmv', '.flv', '.webm', '.m4v', '.3gp', '.ts'}

# Default audio formats and their codec settings
AUDIO_CODECS = {
    'wav': ['-c:a', 'pcm_s16le'],          # Uncompressed PCM 16-bit (Ideal for Transcription / Speech Recognition)
    'flac': ['-c:a', 'flac', '-compression_level', '8'],  # Lossless compressed
    'mp3': ['-c:a', 'libmp3lame'],
    'aac': ['-c:a', 'aac'],
    'm4a': ['-c:a', 'aac'],
    'ogg': ['-c:a', 'libvorbis']
}

def find_ffmpeg(custom_path=None):
    """
    Finds the ffmpeg executable from custom_path, PATH, or local directory.
    """
    if custom_path:
        p = Path(custom_path)
        if p.is_file() and p.name.lower().startswith("ffmpeg"):
            return str(p)
        if p.is_dir():
            exe = p / ("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
            if exe.is_file():
                return str(exe)

    # Check system PATH
    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return ffmpeg_in_path

    # Check current directory or script directory
    script_dir = Path(__file__).parent
    local_exe = script_dir / ("ffmpeg.exe" if os.name == 'nt' else "ffmpeg")
    if local_exe.is_file():
        return str(local_exe)

    return None

def convert_video_to_audio(
    input_path: str,
    output_path: str = None,
    audio_format: str = 'wav',
    bitrate: str = '320k',
    sample_rate: int = None,
    channels: int = None,
    transcription_mode: bool = False,
    ffmpeg_executable: str = None,
    overwrite: bool = True
) -> bool:
    """
    Converts a single video file to audio using FFmpeg with optional high-quality / transcription presets.
    """
    input_file = Path(input_path).resolve()
    if not input_file.exists():
        print(f"[ERROR] Input file does not exist: {input_file}")
        return False

    # Apply transcription preset if requested
    if transcription_mode:
        print("\n[PRESET] Applying Transcription Preset: Lossless WAV, 16kHz sample rate, Mono channel")
        audio_format = 'wav'
        if sample_rate is None:
            sample_rate = 16000  # 16kHz is optimal for Whisper & Speech-to-Text APIs
        if channels is None:
            channels = 1      # Mono reduces noise & file size for speech models

    audio_format = audio_format.lower().lstrip('.')
    if audio_format not in AUDIO_CODECS:
        print(f"[WARNING] Unknown format '{audio_format}'. Defaulting to PCM WAV codec.")
        codec_args = ['-c:a', 'pcm_s16le']
    else:
        codec_args = AUDIO_CODECS[audio_format]

    # Determine output file path
    if output_path:
        out_file = Path(output_path).resolve()
        if out_file.is_dir():
            out_file = out_file / f"{input_file.stem}.{audio_format}"
    else:
        out_file = input_file.parent / f"{input_file.stem}.{audio_format}"

    # Ensure target output directory exists
    out_file.parent.mkdir(parents=True, exist_ok=True)

    # Find FFmpeg binary
    ffmpeg_bin = find_ffmpeg(ffmpeg_executable)
    if not ffmpeg_bin:
        print("\n[ERROR] FFmpeg executable not found!")
        print("Please ensure FFmpeg is installed and added to system PATH,")
        print("or place 'ffmpeg.exe' in this script's directory,")
        print("or pass the path via --ffmpeg-path parameter.\n")
        return False

    # Build FFmpeg command
    cmd = [ffmpeg_bin]
    if overwrite:
        cmd.append('-y')
    else:
        cmd.append('-n')

    cmd.extend(['-i', str(input_file), '-vn'])  # -vn disables video stream

    # Add codec specifications
    cmd.extend(codec_args)

    # For MP3 / AAC / OGG: set highest quality / max bitrate if specified
    if audio_format == 'mp3':
        if bitrate == 'max' or bitrate == '320k':
            cmd.extend(['-b:a', '320k', '-q:a', '0'])  # Highest quality MP3 CBR 320k + VBR 0
        elif bitrate:
            cmd.extend(['-b:a', bitrate])
    elif audio_format in ['aac', 'm4a', 'ogg'] and bitrate:
        if bitrate == 'max':
            cmd.extend(['-b:a', '320k'])
        else:
            cmd.extend(['-b:a', bitrate])

    # Sample rate (-ar)
    if sample_rate:
        cmd.extend(['-ar', str(sample_rate)])

    # Channels (-ac)
    if channels:
        cmd.extend(['-ac', str(channels)])

    cmd.append(str(out_file))

    sr_desc = f"{sample_rate}Hz" if sample_rate else "Native"
    ch_desc = "Mono" if channels == 1 else ("Stereo" if channels == 2 else f"{channels}ch") if channels else "Native"
    print(f"Converting: '{input_file.name}' -> '{out_file.name}'")
    print(f"  Format: {audio_format.upper()} | Codec: {codec_args[1]} | Sample Rate: {sr_desc} | Channels: {ch_desc}")

    try:
        process = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        print(f"[SUCCESS] Converted successfully -> '{out_file}'\n")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] FFmpeg failed with exit code {e.returncode}")
        print(f"FFmpeg Error output:\n{e.stderr[-500:]}")
        return False
    except Exception as e:
        print(f"[ERROR] Unexpected error: {e}")
        return False

def batch_convert(
    input_dir: str,
    output_dir: str = None,
    audio_format: str = 'wav',
    bitrate: str = '320k',
    sample_rate: int = None,
    channels: int = None,
    transcription_mode: bool = False,
    ffmpeg_executable: str = None
):
    """
    Converts all video files in a given directory to audio.
    """
    in_dir = Path(input_dir).resolve()
    if not in_dir.is_dir():
        print(f"[ERROR] Input directory does not exist: {in_dir}")
        return

    out_dir = Path(output_dir).resolve() if output_dir else in_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    video_files = [f for f in in_dir.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]

    if not video_files:
        print(f"[INFO] No supported video files found in '{in_dir}'.")
        return

    print(f"\nFound {len(video_files)} video file(s) to process in '{in_dir}'\n" + "-"*60)

    success_count = 0
    for video in video_files:
        out_fmt = 'wav' if transcription_mode else audio_format.lower().lstrip('.')
        out_file = out_dir / f"{video.stem}.{out_fmt}"
        if convert_video_to_audio(
            input_path=str(video),
            output_path=str(out_file),
            audio_format=audio_format,
            bitrate=bitrate,
            sample_rate=sample_rate,
            channels=channels,
            transcription_mode=transcription_mode,
            ffmpeg_executable=ffmpeg_executable
        ):
            success_count += 1

    print("-" * 60)
    print(f"Batch conversion completed: {success_count}/{len(video_files)} files converted successfully.\n")

def main():
    parser = argparse.ArgumentParser(
        description="Convert video file(s) to highest-quality audio tuned for Transcription / STT using FFmpeg."
    )
    parser.add_argument(
        "-i", "--input",
        type=str,
        help="Path to input video file OR directory containing videos"
    )
    parser.add_argument(
        "-o", "--output",
        type=str,
        help="Path to output audio file OR directory (optional)"
    )
    parser.add_argument(
        "-f", "--format",
        type=str,
        default="wav",
        choices=list(AUDIO_CODECS.keys()),
        help="Target audio format (default: wav - highest quality for transcription)"
    )
    parser.add_argument(
        "-b", "--bitrate",
        type=str,
        default="320k",
        help="Audio bitrate for lossy formats e.g. 320k, max (default: 320k)"
    )
    parser.add_argument(
        "-ar", "--sample-rate",
        type=int,
        help="Sample rate in Hz (e.g. 16000 for Whisper/Speech AI, 44100, 48000)"
    )
    parser.add_argument(
        "-ac", "--channels",
        type=int,
        choices=[1, 2],
        help="Audio channels (1 = Mono [recommended for STT], 2 = Stereo)"
    )
    parser.add_argument(
        "-t", "--transcription",
        action="store_true",
        help="Preset mode for Transcription: Lossless 16-bit WAV, 16kHz sample rate, Mono"
    )
    parser.add_argument(
        "--ffmpeg-path",
        type=str,
        help="Path to custom ffmpeg executable or directory"
    )

    args = parser.parse_args()

    # If no CLI args passed, prompt user interactively
    if not args.input:
        print("=== Video to Audio Converter for Transcription & High Quality (FFmpeg) ===")
        input_path = input("Enter video file or folder path: ").strip().strip('"').strip("'")
        if not input_path:
            print("No path provided. Exiting.")
            sys.exit(1)
        args.input = input_path

        trans_opt = input("Optimize specifically for AI Transcription (Whisper/STT)? [Y/n]: ").strip().lower()
        if trans_opt != 'n':
            args.transcription = True
        else:
            fmt = input("Enter audio format [wav/flac/mp3/aac/m4a/ogg] (default: wav): ").strip().lower()
            if fmt and fmt in AUDIO_CODECS:
                args.format = fmt

            ch_opt = input("Audio Channels? [1 = Mono (Speech), 2 = Stereo, Enter = Keep Original]: ").strip()
            if ch_opt in ['1', '2']:
                args.channels = int(ch_opt)

            sr_opt = input("Sample rate in Hz? [16000 (Whisper/STT), 44100, 48000, Enter = Keep Original]: ").strip()
            if sr_opt.isdigit():
                args.sample_rate = int(sr_opt)

    inp = Path(args.input).resolve()
    if inp.is_dir():
        batch_convert(
            input_dir=str(inp),
            output_dir=args.output,
            audio_format=args.format,
            bitrate=args.bitrate,
            sample_rate=args.sample_rate,
            channels=args.channels,
            transcription_mode=args.transcription,
            ffmpeg_executable=args.ffmpeg_path
        )
    elif inp.is_file():
        convert_video_to_audio(
            input_path=str(inp),
            output_path=args.output,
            audio_format=args.format,
            bitrate=args.bitrate,
            sample_rate=args.sample_rate,
            channels=args.channels,
            transcription_mode=args.transcription,
            ffmpeg_executable=args.ffmpeg_path
        )
    else:
        print(f"[ERROR] Invalid path: '{args.input}' is neither a file nor a directory.")

if __name__ == "__main__":
    main()
