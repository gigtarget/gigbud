"""Telegram video shuffle bot for Railway deployments.

The bot listens for the `/start` command, prompts the user for a YouTube
(or yt-dlp supported) URL, downloads the source video, removes the first and
last 5 seconds, cuts the middle into 2-second clips, shuffles the order, and
sends the final edit back to the user via Telegram.

The heavy lifting (downloading, splitting, rendering) is delegated to worker
threads so the asyncio event loop stays responsive. Progress updates are sent
back to the user throughout the pipeline so they can follow each stage.
"""

from __future__ import annotations

import asyncio
import datetime
import inspect
import logging
import os
import random
import shutil
import tempfile
from pathlib import Path
from typing import Awaitable, Callable, List, Tuple

import yt_dlp
from moviepy.editor import VideoFileClip, concatenate_videoclips
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
SEGMENT_SECONDS = 2.0
SKIP_START = 5.0
SKIP_END = 5.0
WAITING_FOR_URL = 1
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "outputs"))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")

# ---------------------------------------------------------------------------
# Video utilities
# ---------------------------------------------------------------------------

def download_youtube(url: str, outdir: str) -> str:
    """Download the best available MP4 using yt-dlp and return the file path."""
    ydl_opts = {
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(outdir, "%(id)s.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
    }

    logger.info("Downloading video via yt-dlp: %s", url)
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        video_id = info.get("id")
        for ext in ("mp4", "mkv", "webm", "m4a"):
            candidate = os.path.join(outdir, f"{video_id}.{ext}")
            if os.path.exists(candidate):
                logger.info("Downloaded video located at %s", candidate)
                return candidate
        fallback = ydl.prepare_filename(info)
        if os.path.exists(fallback):
            logger.info("Downloaded video located at %s", fallback)
            return fallback
    raise FileNotFoundError("Could not locate downloaded file from yt-dlp.")


def safe_subclip(clip: VideoFileClip, start: float, end: float) -> VideoFileClip:
    """Compatibility wrapper for MoviePy 1.x and 2.x subclip APIs."""
    if hasattr(clip, "subclip"):
        return clip.subclip(start, end)
    return clip.subclipped(start, end)


def split_into_segments(
    video_path: str,
    segment_len: float,
    skip_start: float = SKIP_START,
    skip_end: float = SKIP_END,
) -> Tuple[List[VideoFileClip], VideoFileClip]:
    """Load video, skip first/last few seconds, and cut into segments."""
    logger.info("Loading video for segmentation: %s", video_path)
    clip = VideoFileClip(video_path)
    duration = clip.duration
    logger.info("Original duration: %.2fs", duration)

    start_time = skip_start
    end_time = max(0.0, duration - skip_end)
    if end_time <= start_time:
        clip.close()
        raise ValueError("Video too short after trimming start and end sections.")

    logger.info(
        "Segmenting video between %.2fs and %.2fs with %.2fs segments",
        start_time,
        end_time,
        segment_len,
    )

    starts = [s for s in range(int(start_time), int(end_time), int(segment_len))]
    segments: List[VideoFileClip] = []
    for start in starts:
        end = min(start + segment_len, end_time)
        if end - start >= 0.15:
            segments.append(safe_subclip(clip, start, end))

    logger.info("Created %d segments", len(segments))
    return segments, clip


def assemble_and_write(
    segments: List[VideoFileClip],
    out_path: str,
    fps: float = 24,
    preset: str = "medium",
) -> None:
    """Shuffle, concatenate, and export the final video."""
    logger.info("Shuffling %d segments", len(segments))
    random.shuffle(segments)
    logger.info("Concatenating segments for final export")
    final_clip = concatenate_videoclips(segments, method="compose")

    logger.info("Writing shuffled video to %s", out_path)
    kwargs = {
        "codec": "libx264",
        "audio_codec": "aac",
        "temp_audiofile": "temp-audio.m4a",
        "remove_temp": True,
        "fps": fps,
        "threads": 4,
        "preset": preset,
    }
    signature = inspect.signature(final_clip.write_videofile)
    if "progress_bar" in signature.parameters:
        kwargs["progress_bar"] = True

    try:
        final_clip.write_videofile(out_path, **kwargs)
    finally:
        final_clip.close()
        for segment in segments:
            try:
                segment.close()
            except Exception:
                logger.debug("Segment close failed", exc_info=True)


UpdateStatusCallback = Callable[[str], Awaitable[None]]


async def shuffle_video_from_url(url: str, update_status: UpdateStatusCallback) -> Path:
    """Run the shuffle pipeline and return the path to the saved video."""
    loop = asyncio.get_running_loop()

    with tempfile.TemporaryDirectory(prefix="shuffle_bot_") as tmpdir:
        await update_status("📥 Downloading video…")
        input_path = await loop.run_in_executor(None, download_youtube, url, tmpdir)

        await update_status(
            "✂️ Splitting into 2-second segments (skipping first & last 5s)…"
        )
        segments, original_clip = await loop.run_in_executor(
            None,
            split_into_segments,
            input_path,
            SEGMENT_SECONDS,
            SKIP_START,
            SKIP_END,
        )
        if not segments:
            original_clip.close()
            raise ValueError("Video too short for segmentation.")

        base_name = Path(input_path).stem[:25] or "video"
        timestamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        temp_output_path = os.path.join(tmpdir, f"{base_name}_shuffled_{timestamp}.mp4")
        fps = getattr(original_clip, "fps", 24) or 24

        await update_status("🎬 Shuffling segments and rendering final cut…")
        await loop.run_in_executor(
            None,
            assemble_and_write,
            segments,
            temp_output_path,
            fps,
        )
        original_clip.close()

        await update_status("🗂️ Saving final video…")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        final_path = OUTPUT_DIR / Path(temp_output_path).name
        shutil.move(temp_output_path, final_path)
        logger.info("Final video stored at %s", final_path)
        return final_path


# ---------------------------------------------------------------------------
# Telegram bot handlers
# ---------------------------------------------------------------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Prompt the user for a URL after receiving /start."""
    message = (
        "👋 Send me a YouTube (or supported) URL and I'll shuffle it for you!\n"
        "I'll skip the first and last 5 seconds, cut the rest into 2-second clips,\n"
        "shuffle them, and send the final video back here.\n\n"
        "Paste the URL now, or /cancel to stop."
    )
    await update.message.reply_text(message)
    return WAITING_FOR_URL


async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancel the current conversation."""
    await update.message.reply_text("❎ Cancelled. Send /start when you're ready again!")
    return ConversationHandler.END


async def receive_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Handle the URL provided by the user and kick off processing."""
    if not update.message:
        return WAITING_FOR_URL

    url = (update.message.text or "").strip()
    if not url or not url.lower().startswith("http"):
        await update.message.reply_text(
            "Please send a valid URL starting with http or https, or /cancel to stop."
        )
        return WAITING_FOR_URL

    chat_id = update.effective_chat.id
    status_message = await update.message.reply_text("🚀 Got it! Preparing the shuffle pipeline…")

    async def update_status(text: str) -> None:
        nonlocal status_message
        try:
            status_message = await status_message.edit_text(text)
        except TelegramError as exc:  # Message might be identical or already edited
            logger.debug("Failed to edit status message: %s", exc)
            if "message is not modified" not in (exc.message or "").lower():
                status_message = await context.bot.send_message(chat_id=chat_id, text=text)

    async def process_pipeline() -> None:
        try:
            final_path = await shuffle_video_from_url(url, update_status)
            await update_status("📤 Uploading final video to Telegram…")
            with final_path.open("rb") as video_file:
                await context.bot.send_video(
                    chat_id=chat_id,
                    video=video_file,
                    caption=f"✅ Finished! {final_path.name}",
                )
            await update_status(
                "✅ All done!\n"
                f"Saved copy on the server at: {final_path.resolve()}"
            )
        except Exception as exc:  # pragma: no cover - best effort reporting
            logger.exception("Pipeline failed")
            await update_status("❌ Processing failed. Check logs and try again.")
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Sorry, something went wrong while processing that URL.\nError: {exc}",
            )

    context.application.create_task(process_pipeline())
    return ConversationHandler.END


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def main() -> None:
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN environment variable not set!")

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conversation = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            WAITING_FOR_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_url)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True,
    )
    application.add_handler(conversation)

    logger.info("🤖 Bot is running...")
    application.run_polling()


if __name__ == "__main__":
    main()
