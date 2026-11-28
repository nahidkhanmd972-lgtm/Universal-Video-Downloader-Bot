
    cat << 'EOF' > bot.py
#!/usr/bin/env python3
import asyncio
import html
import logging
import os
import re
import shutil
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

from telegram import BotCommand, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction, ParseMode
from telegram.error import BadRequest, RetryAfter, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)
from telegram.request import HTTPXRequest

import config
import downloader
import tools
from database import DB, LANG_LABELS, is_admin, tr

fmt = logging.Formatter("%(asctime)s | %(levelname)s | %(name)s | %(message)s")
fh = RotatingFileHandler(config.LOG_FILE, maxBytes=2 * 1024 * 1024, backupCount=3, encoding="utf-8")
fh.setFormatter(fmt)
ch = logging.StreamHandler()
ch.setFormatter(fmt)
logging.basicConfig(level=logging.INFO, handlers=[ch, fh])
logger = logging.getLogger("NahidDownloaderPro")
logging.getLogger("httpx").setLevel(logging.WARNING)

EXECUTOR = ThreadPoolExecutor(max_workers=12 if config.IS_TERMUX else 16)
DL_SEMAPHORE: Optional[asyncio.Semaphore] = None
USER_ACTIVE_DL: set[int] = set()
ACTIVE_DL_COUNT = 0
QUEUE_WAIT_COUNT = 0


def build_main_menu(uid: int) -> InlineKeyboardMarkup:
    adm = (
        InlineKeyboardButton(tr(uid, "btn_admin_support"), url=f"https://t.me/{config.ADMIN_USERNAME}")
        if config.ADMIN_USERNAME
        else InlineKeyboardButton(tr(uid, "btn_admin_support"), callback_data="menu_admin_support")
    )
    grp = (
        InlineKeyboardButton(tr(uid, "btn_join_group"), url=config.GROUP_INVITE_LINK)
        if config.GROUP_INVITE_LINK.startswith("http")
        else InlineKeyboardButton(tr(uid, "btn_join_group"), callback_data="menu_join_group")
    )
    rows = [
        [InlineKeyboardButton(tr(uid, "btn_video"), callback_data="menu_video_dl"), InlineKeyboardButton(tr(uid, "btn_v2a"), callback_data="menu_v2a")],
        [InlineKeyboardButton(tr(uid, "btn_qr"), callback_data="menu_qr"), InlineKeyboardButton(tr(uid, "btn_age"), callback_data="menu_age_calc")],
        [InlineKeyboardButton(tr(uid, "btn_comment"), callback_data="menu_comment"), InlineKeyboardButton(tr(uid, "btn_bot_ai"), callback_data="menu_bot_ai")],
        [adm, grp],
        [InlineKeyboardButton(tr(uid, "btn_profile"), callback_data="menu_profile"), InlineKeyboardButton(tr(uid, "btn_stats"), callback_data="menu_stats")],
        [InlineKeyboardButton(tr(uid, "btn_help"), callback_data="menu_help"), InlineKeyboardButton(tr(uid, "btn_lang"), callback_data="menu_lang")],
    ]
    if is_admin(uid):
        rows.append([InlineKeyboardButton(tr(uid, "btn_admin_panel"), callback_data="menu_admin")])
    return InlineKeyboardMarkup(rows)


def build_back_menu(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_back"), callback_data="menu_home")]])


def build_cancel_input_menu(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_cancel"), callback_data="menu_home")]])


def build_lang_menu(uid: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en")],
        [InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn")],
        [InlineKeyboardButton("🇲🇾 Bahasa Melayu", callback_data="setlang_ms")],
        [InlineKeyboardButton(tr(uid, "btn_back"), callback_data="menu_home")],
    ])


def build_cancel_dl_kb(uid: int, jid: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_cancel_dl"), callback_data=f"cancel_{jid}")]])


def format_progress(uid: int, p: dict[str, Any]) -> str:
    dl, tot = int(p.get("downloaded", 0)), int(p.get("total", 0))
    spd, eta = float(p.get("speed", 0.0)), float(p.get("eta", 0.0))
    pct = min(99.9, (dl / tot * 100.0)) if tot > 0 else 0.0
    f = max(0, min(12, int(pct // 8.33)))
    return tr(uid, "dl_progress").format(
        bar="█" * f + "░" * (12 - f),
        pct=pct,
        dl_mb=dl / (1024 * 1024),
        tot_mb=(tot / (1024 * 1024)) if tot > 0 else 0.0,
        spd_mb=(spd / (1024 * 1024)) if spd > 0 else 0.0,
        eta=f"{int(eta)}s" if eta > 0 else "...",
    )


def _sync_user(u: Update) -> int:
    DB.upsert_user(u.effective_user.id, u.effective_user.username, u.effective_user.first_name)
    return u.effective_user.id


def _render_profile(uid: int) -> str:
    r = DB.get_user(uid) or {}
    uname = f"@{html.escape(r['username'])}" if r.get("username") else "N/A"
    return tr(uid, "profile_text").format(
        name=html.escape(r.get("first_name") or "User"),
        user_id=uid,
        username=uname,
        lang_label=LANG_LABELS.get(r.get("language", "en"), LANG_LABELS["en"]),
        downloads=r.get("downloads_count", 0),
        qr_count=r.get("qr_count", 0),
        v2a_count=r.get("v2a_count", 0),
    )


def _render_stats(uid: int) -> str:
    g = DB.get_global_stats()
    return tr(uid, "stats_text").format(
        users=g["total_users"], downloads=g["total_downloads"], qr_count=g["total_qr"], v2a_count=g["total_v2a"]
    )


def _render_admin_panel() -> str:
    g = DB.get_global_stats()
    return (
        "🛡️ <b>Admin Panel</b>\n\n"
        f"• <b>Host:</b> <code>{html.escape(config.HOST_ENV)}</code>\n"
        f"• <b>FFmpeg:</b> <code>{'OK' if config.get_ffmpeg_bin() else 'Missing'}</code> | "
        f"<b>Groq:</b> <code>{'Active' if config.GROQ_API_KEY else 'Off'}</code>\n"
        f"• <b>Users:</b> <code>{g['total_users']:,}</code> | <b>Downloads:</b> <code>{g['total_downloads']:,}</code>\n\n"
        "<code>/adminstats</code> | <code>/broadcast &lt;msg&gt;</code> | <code>/logs</code>"
    )


async def _delete_later(bot: Any, cid: int, mid: int, delay: int = 6) -> None:
    await asyncio.sleep(delay)
    try:
        await bot.delete_message(chat_id=cid, message_id=mid)
    except Exception:
        pass


async def set_bot_commands(app: Application) -> None:
    try:
        await app.bot.set_my_commands([
            BotCommand("start", "Menu"),
            BotCommand("help", "Guide"),
            BotCommand("lang", "Language"),
            BotCommand("profile", "Profile"),
            BotCommand("stats", "Stats"),
        ])
    except Exception:
        pass


async def start_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sync_user(u)
    c.user_data["mode"] = None
    await u.message.reply_text(
        tr(uid, "welcome").format(name=html.escape(u.effective_user.first_name or "User")),
        reply_markup=build_main_menu(uid),
        parse_mode=ParseMode.HTML,
    )


async def help_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sync_user(u)
    c.user_data["mode"] = None
    await u.message.reply_text(
        tr(uid, "help_text").format(admin=html.escape(config.ADMIN_USERNAME or "Admin")),
        reply_markup=build_back_menu(uid),
        parse_mode=ParseMode.HTML,
    )


async def lang_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sync_user(u)
    c.user_data["mode"] = None
    await u.message.reply_text(tr(uid, "lang_prompt"), reply_markup=build_lang_menu(uid), parse_mode=ParseMode.HTML)


async def profile_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sync_user(u)
    c.user_data["mode"] = None
    await u.message.reply_text(_render_profile(uid), reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)


async def stats_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid = _sync_user(u)
    c.user_data["mode"] = None
    await u.message.reply_text(_render_stats(uid), reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)


async def adminstats_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(_sync_user(u)):
        await u.message.reply_text("⛔ Admin only.")
        return
    await u.message.reply_text(_render_admin_panel(), parse_mode=ParseMode.HTML)


async def broadcast_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(_sync_user(u)):
        await u.message.reply_text("⛔ Admin only.")
        return
    msg = " ".join(c.args).strip()
    if not msg:
        await u.message.reply_text("Usage: /broadcast <message>")
        return
    uids = DB.get_all_user_ids()
    sent = failed = 0
    st = await u.message.reply_text(f"📢 Sending to {len(uids)} users...")
    for uid in uids:
        try:
            await c.bot.send_message(chat_id=uid, text=msg)
            sent += 1
        except RetryAfter as r:
            await asyncio.sleep(r.retry_after + 0.5)
            try:
                await c.bot.send_message(chat_id=uid, text=msg)
                sent += 1
            except Exception:
                failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.05)
    await st.edit_text(f"✅ Sent: {sent}, Failed: {failed}")


async def logs_command(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not is_admin(_sync_user(u)):
        await u.message.reply_text("⛔ Admin only.")
        return
    lp = Path(config.LOG_FILE)
    if not lp.exists():
        await u.message.reply_text("No logs.")
        return
    with open(lp, "r", encoding="utf-8", errors="replace") as f:
        tail = "".join(f.readlines()[-30:])[-3800:]
    await u.message.reply_text(f"<pre>{html.escape(tail or 'Empty')}</pre>", parse_mode=ParseMode.HTML)


async def callback_handler(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    q = u.callback_query
    user = q.from_user
    DB.upsert_user(user.id, user.username, user.first_name)
    data = q.data or ""
    await q.answer()

    if data.startswith("cancel_"):
        jid = data.removeprefix("cancel_")
        with downloader.STATE_LOCK:
            downloader.ACTIVE_CANCELS[jid] = True
        try:
            await q.edit_message_text(tr(user.id, "dl_cancelled"), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
        return

    if data.startswith("setlang_"):
        DB.set_lang(user.id, data.removeprefix("setlang_"))
        c.user_data["mode"] = None
        await q.edit_message_text(
            f"{tr(user.id, 'lang_updated')}\n\n{tr(user.id, 'welcome').format(name=html.escape(user.first_name or 'User'))}",
            reply_markup=build_main_menu(user.id),
            parse_mode=ParseMode.HTML,
        )
        return

    if data == "menu_bot_ai":
        if not config.GROQ_API_KEY:
            await q.edit_message_text(tr(user.id, "ai_disabled"), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
        else:
            c.user_data["mode"] = "bot_ai"
            await q.edit_message_text(tr(user.id, "ai_prompt"), reply_markup=build_cancel_input_menu(user.id), parse_mode=ParseMode.HTML)
        return

    if data == "menu_admin" and is_admin(user.id):
        c.user_data["mode"] = None
        await q.edit_message_text(_render_admin_panel(), reply_markup=build_back_menu(user.id), parse_mode=ParseMode.HTML)
        return

    routes = {
        "menu_home": (None, tr(user.id, "welcome").format(name=html.escape(user.first_name or "User")), build_main_menu(user.id)),
        "menu_video_dl": ("video_dl", tr(user.id, "video_prompt").format(max_mb=config.MAX_DOWNLOAD_MB), build_back_menu(user.id)),
        "menu_qr": ("qr", tr(user.id, "qr_prompt"), build_back_menu(user.id)),
        "menu_v2a": ("v2a", tr(user.id, "v2a_prompt"), build_back_menu(user.id)),
        "menu_age_calc": ("age_calc", tr(user.id, "age_prompt"), build_cancel_input_menu(user.id)),
        "menu_comment": ("feedback", tr(user.id, "comment_prompt"), build_cancel_input_menu(user.id)),
        "menu_join_group": (None, tr(user.id, "group_not_set").format(admin=html.escape(config.ADMIN_USERNAME or "Admin")), build_back_menu(user.id)),
        "menu_admin_support": (None, tr(user.id, "admin_not_set"), build_back_menu(user.id)),
        "menu_profile": (None, _render_profile(user.id), build_back_menu(user.id)),
        "menu_stats": (None, _render_stats(user.id), build_back_menu(user.id)),
        "menu_help": (None, tr(user.id, "help_text").format(admin=html.escape(config.ADMIN_USERNAME or "Admin")), build_back_menu(user.id)),
        "menu_lang": (None, tr(user.id, "lang_prompt"), build_lang_menu(user.id)),
    }
    if data in routes:
        mode_val, text_val, kb_val = routes[data]
        c.user_data["mode"] = mode_val
        await q.edit_message_text(text_val, reply_markup=kb_val, parse_mode=ParseMode.HTML)


async def process_video_download(u: Update, c: ContextTypes.DEFAULT_TYPE, url: str) -> None:
    global DL_SEMAPHORE, ACTIVE_DL_COUNT, QUEUE_WAIT_COUNT
    uid, cid = u.effective_user.id, u.effective_chat.id

    if uid in USER_ACTIVE_DL:
        w = await c.bot.send_message(chat_id=cid, text="⏳ <b>Previous download is still running.</b>", parse_mode=ParseMode.HTML)
        asyncio.create_task(_delete_later(c.bot, cid, w.message_id, 5))
        return

    if DL_SEMAPHORE is None:
        DL_SEMAPHORE = asyncio.Semaphore(config.MAX_CONCURRENT_DOWNLOADS)

    _, plat_label = downloader.detect_platform(url)
    footer = f"👨‍💻 Admin: @{html.escape(config.ADMIN_USERNAME or 'Admin')}"
    jid = uuid.uuid4().hex[:10]
    td = config.TEMP_ROOT / f"nahid_dl_{jid}"
    USER_ACTIVE_DL.add(uid)

    with downloader.STATE_LOCK:
        downloader.ACTIVE_CANCELS[jid] = False
        downloader.JOB_PROGRESS[jid] = {"downloaded": 0, "total": 0, "speed": 0.0, "eta": 0.0}

    queued = ACTIVE_DL_COUNT >= config.MAX_CONCURRENT_DOWNLOADS
    if queued:
        QUEUE_WAIT_COUNT += 1
        init_txt = f"⏳ <b>{plat_label} — Queue #{QUEUE_WAIT_COUNT}</b>\nWaiting for a free slot..."
    else:
        init_txt = f"{plat_label}\n{tr(uid, 'dl_starting')}"

    st = await c.bot.send_message(chat_id=cid, text=init_txt, reply_markup=build_cancel_dl_kb(uid, jid), parse_mode=ParseMode.HTML)
    loop = asyncio.get_running_loop()
    loop_active = True

    async def progress_updater() -> None:
        last_txt = ""
        while loop_active and not downloader.is_job_cancelled(jid):
            await asyncio.sleep(3.5)
            if not loop_active or downloader.is_job_cancelled(jid):
                break
            with downloader.STATE_LOCK:
                prog = dict(downloader.JOB_PROGRESS.get(jid, {}))
            if prog.get("downloaded", 0) <= 0:
                continue
            card = f"{plat_label}\n{format_progress(uid, prog)}"
            if card != last_txt and not downloader.is_job_cancelled(jid):
                last_txt = card
                try:
                    await st.edit_text(card, reply_markup=build_cancel_dl_kb(uid, jid), parse_mode=ParseMode.HTML)
                except RetryAfter as r:
                    await asyncio.sleep(r.retry_after)
                except TelegramError:
                    pass

    ptask: Optional[asyncio.Task] = None
    try:
        async with DL_SEMAPHORE:
            if queued:
                QUEUE_WAIT_COUNT = max(0, QUEUE_WAIT_COUNT - 1)
            if downloader.is_job_cancelled(jid):
                return
            ACTIVE_DL_COUNT += 1
            try:
                await st.edit_text(f"{plat_label}\n{tr(uid, 'dl_starting')}", reply_markup=build_cancel_dl_kb(uid, jid), parse_mode=ParseMode.HTML)
            except TelegramError:
                pass

            ptask = asyncio.create_task(progress_updater())
            td.mkdir(parents=True, exist_ok=True)
            try:
                vp, fb_url, skip_mb = await asyncio.wait_for(
                    loop.run_in_executor(EXECUTOR, downloader.run_download_pipeline, url, td, jid),
                    timeout=config.DOWNLOAD_TIMEOUT_SEC,
                )
            except asyncio.TimeoutError:
                with downloader.STATE_LOCK:
                    downloader.ACTIVE_CANCELS[jid] = True
                loop_active = False
                if ptask:
                    ptask.cancel()
                du = await loop.run_in_executor(EXECUTOR, downloader.extract_direct_stream_url, downloader.clean_url(url))
                if du and du.startswith("http"):
                    await st.edit_text(f"⏱️ <b>Direct Link Ready ({plat_label})</b>\n{footer}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_direct_dl"), url=du)]]), parse_mode=ParseMode.HTML)
                else:
                    await st.edit_text("⏱️ <b>Download timed out.</b>", parse_mode=ParseMode.HTML)
                return

            loop_active = False
            if ptask:
                ptask.cancel()
            if downloader.is_job_cancelled(jid):
                return

            if skip_mb > 0 and fb_url:
                await st.edit_text(f"{tr(uid, 'dl_too_large').format(size_mb=skip_mb)}\n\n{footer}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_direct_dl"), url=fb_url)]]), parse_mode=ParseMode.HTML)
                DB.increment_stat(uid, "downloads_count")
                return

            if not vp or not vp.exists():
                if fb_url and fb_url.startswith("http"):
                    await st.edit_text(f"{tr(uid, 'dl_too_large').format(size_mb=50.0)}\n\n{footer}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_direct_dl"), url=fb_url)]]), parse_mode=ParseMode.HTML)
                else:
                    await st.edit_text(tr(uid, "dl_failed"), parse_mode=ParseMode.HTML)
                return

            fsize = vp.stat().st_size
            if fsize <= config.MAX_TG_UPLOAD_BYTES:
                await st.edit_text(tr(uid, "dl_uploading"), parse_mode=ParseMode.HTML)
                await c.bot.send_chat_action(chat_id=cid, action=ChatAction.UPLOAD_VIDEO)
                with open(vp, "rb") as vf:
                    await c.bot.send_video(chat_id=cid, video=vf, caption=f"{plat_label} • {tr(uid, 'dl_success')}\n{footer}", supports_streaming=True, read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML)
                DB.increment_stat(uid, "downloads_count")
                try:
                    await st.delete()
                except TelegramError:
                    pass
            else:
                smb = fsize / (1024 * 1024)
                await st.edit_text(tr(uid, "dl_splitting").format(size_mb=smb), parse_mode=ParseMode.HTML)
                parts = await loop.run_in_executor(EXECUTOR, downloader.split_video_for_telegram, vp, td)
                if parts:
                    await c.bot.send_chat_action(chat_id=cid, action=ChatAction.UPLOAD_VIDEO)
                    for idx, pp in enumerate(parts, start=1):
                        with open(pp, "rb") as pf:
                            await c.bot.send_video(chat_id=cid, video=pf, caption=f"{plat_label} • Part {idx}/{len(parts)}\n{footer}", supports_streaming=True, read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML)
                    DB.increment_stat(uid, "downloads_count")
                    try:
                        await st.delete()
                    except TelegramError:
                        pass
                else:
                    du = fb_url or await loop.run_in_executor(EXECUTOR, downloader.extract_direct_stream_url, downloader.clean_url(url))
                    if du and du.startswith("http"):
                        await st.edit_text(f"{tr(uid, 'dl_too_large').format(size_mb=smb)}\n\n{footer}", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(tr(uid, "btn_direct_dl"), url=du)]]), parse_mode=ParseMode.HTML)
                    else:
                        await st.edit_text(tr(uid, "dl_too_large_no_url").format(size_mb=smb), parse_mode=ParseMode.HTML)
    except downloader.DownloadCancelledError:
        logger.info("Job %s cancelled", jid)
    except Exception as exc:
        logger.exception("Video DL error: %s", exc)
        try:
            await st.edit_text(tr(uid, "dl_failed"), parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    finally:
        loop_active = False
        ACTIVE_DL_COUNT = max(0, ACTIVE_DL_COUNT - 1)
        USER_ACTIVE_DL.discard(uid)
        if ptask and not ptask.done():
            ptask.cancel()
        with downloader.STATE_LOCK:
            downloader.ACTIVE_CANCELS.pop(jid, None)
            downloader.JOB_PROGRESS.pop(jid, None)
        shutil.rmtree(td, ignore_errors=True)


async def process_qr_text(u: Update, c: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
    uid = u.effective_user.id
    if len(raw_text.encode("utf-8")) > config.MAX_TEXT_PASTE_BYTES:
        await u.message.reply_text(tr(uid, "qr_text_failed"), parse_mode=ParseMode.HTML)
        return
    st = await u.message.reply_text(tr(uid, "qr_uploading_text"), parse_mode=ParseMode.HTML)
    td = config.TEMP_ROOT / f"nahid_qr_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()
    try:
        td.mkdir(parents=True, exist_ok=True)
        pu = await loop.run_in_executor(EXECUTOR, tools.upload_text_to_paste_rs, raw_text)
        if not pu:
            await st.edit_text(tr(uid, "qr_text_failed"), parse_mode=ParseMode.HTML)
            return
        qp = await loop.run_in_executor(EXECUTOR, tools.generate_qr_png, pu, td / "qr.png")
        with open(qp, "rb") as img:
            await c.bot.send_photo(chat_id=u.effective_chat.id, photo=img, caption=tr(uid, "qr_done").format(url=html.escape(pu), admin=html.escape(config.ADMIN_USERNAME or "Admin")), reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)
        DB.increment_stat(uid, "qr_count")
        try:
            await st.delete()
        except TelegramError:
            pass
    except Exception as exc:
        logger.exception("QR text error: %s", exc)
        await st.edit_text(tr(uid, "qr_text_failed"), parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(td, ignore_errors=True)


async def process_qr_photo(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid, msg = u.effective_user.id, u.message
    if msg.photo:
        obj, fname = msg.photo[-1], "photo.jpg"
    elif msg.document and (msg.document.mime_type or "").startswith("image/"):
        obj, fname = msg.document, (msg.document.file_name or "image.png")
    else:
        await msg.reply_text(tr(uid, "qr_need_input"), parse_mode=ParseMode.HTML)
        return
    if (getattr(obj, "file_size", 0) or 0) > config.MAX_TG_DOWNLOAD_BYTES:
        await msg.reply_text(tr(uid, "v2a_too_big"), parse_mode=ParseMode.HTML)
        return
    st = await msg.reply_text(tr(uid, "qr_uploading_photo"), parse_mode=ParseMode.HTML)
    td = config.TEMP_ROOT / f"nahid_qrimg_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()
    try:
        td.mkdir(parents=True, exist_ok=True)
        local_img = td / Path(fname).name
        tgf = await obj.get_file()
        await tgf.download_to_drive(custom_path=str(local_img))
        cu = await loop.run_in_executor(EXECUTOR, tools.upload_image_to_catbox, local_img)
        if not cu:
            await st.edit_text(tr(uid, "qr_photo_failed"), parse_mode=ParseMode.HTML)
            return
        qp = await loop.run_in_executor(EXECUTOR, tools.generate_qr_png, cu, td / "qr.png")
        with open(qp, "rb") as img:
            await c.bot.send_photo(chat_id=u.effective_chat.id, photo=img, caption=tr(uid, "qr_done").format(url=html.escape(cu), admin=html.escape(config.ADMIN_USERNAME or "Admin")), reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)
        DB.increment_stat(uid, "qr_count")
        try:
            await st.delete()
        except TelegramError:
            pass
    except Exception as exc:
        logger.exception("QR photo error: %s", exc)
        await st.edit_text(tr(uid, "qr_photo_failed"), parse_mode=ParseMode.HTML)
    finally:
        shutil.rmtree(td, ignore_errors=True)


async def process_video_to_audio(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    uid, msg = u.effective_user.id, u.message
    if not msg:
        return
    vobj = msg.video or msg.video_note or (msg.document if msg.document and (msg.document.mime_type or "").startswith("video/") else None)
    if not vobj:
        await msg.reply_text(tr(uid, "v2a_need_video"), parse_mode=ParseMode.HTML)
        return
    if (getattr(vobj, "file_size", 0) or 0) > config.MAX_TG_DOWNLOAD_BYTES:
        await msg.reply_text(tr(uid, "v2a_too_big"), parse_mode=ParseMode.HTML)
        return
    st = await msg.reply_text(tr(uid, "v2a_processing"), parse_mode=ParseMode.HTML)
    td = config.TEMP_ROOT / f"nahid_v2a_{uuid.uuid4().hex[:10]}"
    loop = asyncio.get_running_loop()
    try:
        td.mkdir(parents=True, exist_ok=True)
        rn = getattr(vobj, "file_name", None) or "audio_track.mp4"
        stem = re.sub(r"[^A-Za-z0-9_-]", "_", Path(rn).stem).strip("_") or "audio_track"
        ip = td / f"{stem}{Path(rn).suffix or '.mp4'}"
        try:
            tgf = await vobj.get_file()
            await tgf.download_to_drive(custom_path=str(ip))
        except BadRequest:
            await st.edit_text(tr(uid, "v2a_too_big"), parse_mode=ParseMode.HTML)
            return

        out_audio, ecode, edet = await loop.run_in_executor(EXECUTOR, tools.extract_audio_with_ffmpeg, ip, td, stem)
        if not out_audio:
            if ecode == "NO_FFMPEG":
                await st.edit_text("❌ <b>FFmpeg missing!</b>", parse_mode=ParseMode.HTML)
            elif ecode == "NO_AUDIO":
                await st.edit_text("❌ <b>No audio track in video!</b>", parse_mode=ParseMode.HTML)
            else:
                await st.edit_text(f"{tr(uid, 'v2a_failed')}\n\n<code>{html.escape(edet)}</code>", parse_mode=ParseMode.HTML)
            return
        if out_audio.stat().st_size > config.MAX_TG_UPLOAD_BYTES:
            await st.edit_text(tr(uid, "v2a_out_too_big"), parse_mode=ParseMode.HTML)
            return

        await c.bot.send_chat_action(chat_id=u.effective_chat.id, action=ChatAction.UPLOAD_VOICE)
        with open(out_audio, "rb") as afh:
            await c.bot.send_audio(chat_id=u.effective_chat.id, audio=afh, filename=out_audio.name, title=stem, caption=tr(uid, "v2a_done").format(admin=html.escape(config.ADMIN_USERNAME or "Admin")), reply_markup=build_back_menu(uid), read_timeout=300, write_timeout=300, parse_mode=ParseMode.HTML)
        DB.increment_stat(uid, "v2a_count")
        try:
            await st.delete()
        except TelegramError:
            pass
    except Exception as exc:
        logger.exception("V2A error: %s", exc)
        try:
            await st.edit_text(f"{tr(uid, 'v2a_failed')}\n\n<code>{html.escape(str(exc)[:200])}</code>", parse_mode=ParseMode.HTML)
        except TelegramError:
            pass
    finally:
        shutil.rmtree(td, ignore_errors=True)


async def process_age_calculator(u: Update, c: ContextTypes.DEFAULT_TYPE, raw_text: str) -> None:
    uid = u.effective_user.id
    res = tools.calculate_exact_age(raw_text)
    if not res:
        await u.message.reply_text(tr(uid, "age_invalid"), reply_markup=build_cancel_input_menu(uid), parse_mode=ParseMode.HTML)
        return
    c.user_data["mode"] = None
    msg = (
        "🎂 <b>YOUR AGE DETAILS</b>\n\n"
        f"📅 <b>Date of Birth:</b> <code>{res['dob_str']}</code>\n"
        f"🎉 <b>Years:</b> <code>{res['years']}</code>\n"
        f"📆 <b>Months:</b> <code>{res['months']}</code>\n"
        f"☀️ <b>Days:</b> <code>{res['days']}</code>\n"
        f"⏳ <b>Total Days Lived:</b> <code>{res['total_days']:,}</code>"
    )
    if config.GROQ_API_KEY:
        note = await asyncio.get_running_loop().run_in_executor(
            EXECUTOR, tools.query_groq_ai,
            "Write 1 short friendly sentence (max 25 words) congratulating the user on their age. Do not recalculate.",
            f"DOB: {res['dob_str']}, Age: {res['years']}y {res['months']}m {res['days']}d.",
        )
        if note:
            msg += f"\n\n🤖 <i>{html.escape(note)}</i>"
    msg += "\n\nThank you for using Nahid Age Calculator!"
    await u.message.reply_text(msg, reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)


async def process_bot_ai(u: Update, c: ContextTypes.DEFAULT_TYPE, question: str) -> None:
    uid = u.effective_user.id
    if not config.GROQ_API_KEY:
        c.user_data["mode"] = None
        await u.message.reply_text(tr(uid, "ai_disabled"), reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)
        return
    w = await u.message.reply_text("🤖 <i>Thinking...</i>", parse_mode=ParseMode.HTML)
    sys_p = f"You are the assistant for 'Nahid Video Downloader Pro' Telegram Bot (Admin: @{config.ADMIN_USERNAME}). Features: Video Downloader (YT/FB/IG/TikTok up to 100MB), QR Code, Video to MP3, Age Calculator (DD-MM-YYYY), Comment/Feedback, Admin Support, Join Group. Reply concisely in the user's language."
    ans = await asyncio.get_running_loop().run_in_executor(EXECUTOR, tools.query_groq_ai, sys_p, question[:500])
    if ans:
        await w.edit_text(f"🤖 {html.escape(ans)}", reply_markup=build_cancel_input_menu(uid), parse_mode=ParseMode.HTML)
    else:
        await w.edit_text("⚠️ AI is busy right now.", reply_markup=build_back_menu(uid), parse_mode=ParseMode.HTML)


async def handle_text_message(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not u.message or not u.message.text:
        return
    uid, cid, user = _sync_user(u), u.effective_chat.id, u.effective_user
    text, mode = u.message.text.strip(), c.user_data.get("mode")

    maybe_url = downloader.extract_first_url(text)
    if mode != "qr" and maybe_url and downloader.is_supported_video_url(maybe_url):
        c.user_data["mode"] = None
        try:
            await u.message.delete()
        except Exception:
            pass
        await process_video_download(u, c, maybe_url)
        return

    if mode == "feedback":
        c.user_data["mode"] = None
        if config.ADMIN_ID:
            uname = f"@{html.escape(user.username)}" if user.username else "No Username"
            amsg = f"💬 <b>New Comment / Feedback</b>\n\n👤 {html.escape(user.first_name or 'User')} ({uname})\n🆔 <code>{user.id}</code>\n\n📝 {html.escape(text)}"
            try:
                await c.bot.send_message(chat_id=config.ADMIN_ID, text=amsg, parse_mode=ParseMode.HTML)
            except Exception:
                pass
        await u.message.reply_text(tr(uid, "comment_sent"), reply_markup=build_main_menu(uid), parse_mode=ParseMode.HTML)
        return

    if mode == "age_calc":
        await process_age_calculator(u, c, text)
        return
    if mode == "bot_ai":
        await process_bot_ai(u, c, text)
        return
    if mode == "qr":
        await process_qr_text(u, c, text)
        return
    if mode == "v2a":
        try:
            await u.message.delete()
        except Exception:
            pass
        w = await c.bot.send_message(chat_id=cid, text=tr(uid, "v2a_need_video"), parse_mode=ParseMode.HTML)
        asyncio.create_task(_delete_later(c.bot, cid, w.message_id, 5))
        return

    try:
        await u.message.delete()
    except Exception:
        pass
    w = await c.bot.send_message(chat_id=cid, text=tr(uid, "stray_text_warn"), parse_mode=ParseMode.HTML)
    asyncio.create_task(_delete_later(c.bot, cid, w.message_id, 6))


async def handle_photo_message(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not u.message:
        return
    uid = _sync_user(u)
    if c.user_data.get("mode") == "qr":
        await process_qr_photo(u, c)
    else:
        try:
            await u.message.delete()
        except Exception:
            pass
        w = await c.bot.send_message(chat_id=u.effective_chat.id, text=tr(uid, "use_qr_mode"), parse_mode=ParseMode.HTML)
        asyncio.create_task(_delete_later(c.bot, u.effective_chat.id, w.message_id, 6))


async def handle_video_message(u: Update, c: ContextTypes.DEFAULT_TYPE) -> None:
    if not u.message:
        return
    uid = _sync_user(u)
    if c.user_data.get("mode") == "v2a":
        await process_video_to_audio(u, c)
    else:
        try:
            await u.message.delete()
        except Exception:
            pass
        w = await c.bot.send_message(chat_id=u.effective_chat.id, text=tr(uid, "use_v2a_mode"), parse_mode=ParseMode.HTML)
        asyncio.create_task(_delete_later(c.bot, u.effective_chat.id, w.message_id, 6))


async def error_handler(u: object, c: ContextTypes.DEFAULT_TYPE) -> None:
    logger.error("Unhandled error: %s", c.error, exc_info=c.error)


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(f"Nahid Downloader Pro Online | {config.HOST_ENV}".encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        return


def start_health_server_if_needed() -> None:
    port_env = os.getenv("PORT", "").strip()
    if not port_env and not (os.getenv("RENDER") or os.getenv("RENDER_SERVICE_ID") or os.getenv("RAILWAY_ENVIRONMENT")):
        return
    try:
        srv = HTTPServer(("0.0.0.0", int(port_env or "8080")), HealthHandler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
    except OSError:
        pass


def main() -> None:
    if not config.BOT_TOKEN:
        logger.critical("BOT_TOKEN missing in .env!")
        raise SystemExit(1)
    logger.info("Env: %s | FFmpeg: %s | MaxDL: %d MB", config.HOST_ENV, config.get_ffmpeg_bin() or "missing", config.MAX_DOWNLOAD_MB)
    start_health_server_if_needed()

    req = HTTPXRequest(connect_timeout=60.0, read_timeout=300.0, write_timeout=300.0, pool_timeout=60.0)
    app = ApplicationBuilder().token(config.BOT_TOKEN).request(req).post_init(set_bot_commands).build()
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("lang", lang_command))
    app.add_handler(CommandHandler("profile", profile_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("adminstats", adminstats_command))
    app.add_handler(CommandHandler("broadcast", broadcast_command))
    app.add_handler(CommandHandler("logs", logs_command))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(MessageHandler(filters.PHOTO | filters.Document.IMAGE, handle_photo_message))
    app.add_handler(MessageHandler(filters.VIDEO | filters.VIDEO_NOTE | filters.Document.VIDEO, handle_video_message))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))
    app.add_error_handler(error_handler)

    logger.info("Nahid Video Downloader Pro is ONLINE (%s)!", config.HOST_ENV)
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
EOF