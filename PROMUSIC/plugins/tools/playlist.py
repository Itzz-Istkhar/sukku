import os
import time
import requests
from random import randint
from typing import Dict, List, Union

import yt_dlp
from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)
from pykeyboard import InlineKeyboard
from youtube_search import YoutubeSearch
from youtubesearchpython import VideosSearch, SearchVideos

from PROMUSIC import Carbon, app
from PROMUSIC.utils import close_markup
from PROMUSIC.utils.database import (
    add_served_chat,
    add_served_user,
    blacklisted_chats,
    get_lang,
    is_banned_user,
    is_on_off,
)
from PROMUSIC.utils.decorators.language import language, languageCB
from PROMUSIC.utils.inline.playlist import (
    botplaylist_markup,
    get_playlist_markup,
    warning_markup,
)
from PROMUSIC.utils.stream.stream import stream
from PROMUSIC.core.mongo import mongodb

from config import BANNED_USERS, OWNER_ID

SERVER_PLAYLIST_LIMIT = 50


playlistdb = mongodb.playlist
playlist = []

async def _get_playlists(chat_id: int) -> Dict[str, int]:
    _notes = await playlistdb.find_one({"chat_id": chat_id})
    if not _notes:
        return {}
    return _notes["notes"]


async def get_playlist_names(chat_id: int) -> List[str]:
    _notes = []
    for note in await _get_playlists(chat_id):
        _notes.append(note)
    return _notes


async def get_playlist(chat_id: int, name: str) -> Union[bool, dict]:
    name = name
    _notes = await _get_playlists(chat_id)
    if name in _notes:
        return _notes[name]
    else:
        return False


async def save_playlist(chat_id: int, name: str, note: dict):
    name = name
    _notes = await _get_playlists(chat_id)
    _notes[name] = note
    await playlistdb.update_one(
        {"chat_id": chat_id}, {"$set": {"notes": _notes}}, upsert=True
    )

async def delete_playlist(chat_id: int, name: str) -> bool:
    notesd = await _get_playlists(chat_id)
    name = name
    if name in notesd:
        del notesd[name]
        await playlistdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": notesd}},
            upsert=True,
        )
        return True
    return False

async def update_playlist(chat_id: int, name: str, note: dict):
    """
    Update the playlist with the given name and note for the specific chat_id.
    """
    _notes = await _get_playlists(chat_id)
    
    if name in _notes:
        _notes[name] = note
        await playlistdb.update_one(
            {"chat_id": chat_id},
            {"$set": {"notes": _notes}},
            upsert=True
        )
        return True
    return False  


ADDPLAYLIST_COMMAND = ("addsong")
PLAYLIST_COMMAND = ("playlist")
DELETESONG_COMMAND = ("delsong")


from pyrogram import filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, Message, CallbackQuery

PAGE_SIZE = 15  # Number of songs per page in expanded mode
COLLAPSE_SIZE = 5  # Number of songs per page in collapsed mode
expanded_users = set()  # Keeps track of users who expanded their playlist

@app.on_message(filters.command(["playlist", "plist"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language
async def check_playlist(client, message: Message, _):
    user_id = message.from_user.id
    _playlist = await get_playlist_names(user_id)

    if not _playlist:
        return await message.reply_text(_["playlist_3"])

    is_expanded = user_id in expanded_users
    await send_playlist_page(client, message, user_id, 1, is_expanded, is_home=True)

async def send_playlist_page(client, event, user_id, page, is_expanded, is_home=False):
    """ Sends or updates the playlist page with navigation buttons and expansion/collapse state. """
    _playlist = await get_playlist_names(user_id)
    if not _playlist:
        return await event.message.edit_text("ʏᴏᴜ ʜᴀᴠᴇ ɴᴏ ᴘʟᴀʏʟɪsᴛ ɪɴ ᴍʏ ᴅᴀᴛᴀʙᴀsᴇ.") if isinstance(event, CallbackQuery) else await event.reply_text("ʏᴏᴜ ʜᴀᴠᴇ ɴᴏ ᴘʟᴀʏʟɪsᴛ.")

    total_songs = len(_playlist)
    songs_per_page = PAGE_SIZE if is_expanded else COLLAPSE_SIZE
    start, end = (page - 1) * songs_per_page, page * songs_per_page
    current_songs = _playlist[start:end]

    title = f"◆ {event.from_user.first_name}'s {'ғᴜʟʟ ' if is_expanded else ''}ᴘʟᴀʏʟɪsᴛ (Page {page})."
    msg = f"<blockquote>{title}</blockquote>\n\n<blockquote>"

    for idx, song in enumerate(current_songs, start=start + 1):
        _note = await get_playlist(user_id, song)
        msg += f"{idx}. {_note['title'].title()}\n"
    msg += "</blockquote>"

    keyboard = []
    nav_buttons = []

    # Ensure Previous and Next buttons always appear
    if start > 0:
        nav_buttons.append(InlineKeyboardButton("ʙᴀᴄᴋ", callback_data=f"playlist_page|{user_id}|{page-1}"))
    if end < total_songs:
        nav_buttons.append(InlineKeyboardButton("ɴᴇxᴛ", callback_data=f"playlist_page|{user_id}|{page+1}"))

    if is_expanded:
        keyboard.append([InlineKeyboardButton("ᴄᴏʟʟᴀᴘsᴇ", callback_data=f"collapse_playlist_{user_id}")])
    else:
        if total_songs > COLLAPSE_SIZE:
            keyboard.append([InlineKeyboardButton("ᴇxᴘᴀɴᴅ", callback_data=f"expand_playlist_{user_id}")])

    if nav_buttons:
        keyboard.append(nav_buttons)

    if nav_buttons and not is_home:
        keyboard.append([InlineKeyboardButton("ʜᴏᴍᴇ", callback_data=f"playlist_home|{user_id}")])

    keyboard.append([InlineKeyboardButton("ᴄʟᴏsᴇ", callback_data="close")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(msg, reply_markup=reply_markup)
    else:
        await event.reply_text(msg, reply_markup=reply_markup)

@app.on_callback_query(filters.regex(r"expand_playlist_(\d+)"))
async def expand_playlist(client, callback_query: CallbackQuery):
    """ Expands the playlist and applies it to all pages. """
    user_id = int(callback_query.data.split("_")[-1])

    if user_id != callback_query.from_user.id:
        return await callback_query.answer("ɪᴛ's ɴᴏᴛ ʏᴏᴜʀ ǫᴜᴇʀʏ, ɴᴏʀ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.", show_alert=True)

    expanded_users.add(user_id)  # Mark user as expanded
    await send_playlist_page(client, callback_query, user_id, 1, is_expanded=True, is_home=True)

@app.on_callback_query(filters.regex(r"collapse_playlist_(\d+)"))
async def collapse_playlist(client, callback_query: CallbackQuery):
    """ Collapses the playlist and applies it to all pages. """
    user_id = int(callback_query.data.split("_")[-1])

    if user_id != callback_query.from_user.id:
        return await callback_query.answer("ɪᴛ's ɴᴏᴛ ʏᴏᴜʀ ǫᴜᴇʀʏ, ɴᴏʀ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.", show_alert=True)

    expanded_users.discard(user_id)  # Remove user from expanded list
    await send_playlist_page(client, callback_query, user_id, 1, is_expanded=False, is_home=True)

@app.on_callback_query(filters.regex(r"playlist_page\|(\d+)\|(\d+)"))
async def paginate_playlist(client, callback_query: CallbackQuery):
    """ Handles playlist pagination when user clicks 'Next' or 'Previous'. """
    user_id, page = map(int, callback_query.data.split("|")[1:])

    if user_id != callback_query.from_user.id:
        return await callback_query.answer("ɪᴛ's ɴᴏᴛ ʏᴏᴜʀ ǫᴜᴇʀʏ, ɴᴏʀ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.", show_alert=True)

    is_expanded = user_id in expanded_users
    await send_playlist_page(client, callback_query, user_id, page, is_expanded)

@app.on_callback_query(filters.regex(r"playlist_home\|(\d+)"))
async def return_to_home(client, callback_query: CallbackQuery):
    """ Returns the user to the first page of the playlist. """
    user_id = int(callback_query.data.split("|")[1])

    if user_id != callback_query.from_user.id:
        return await callback_query.answer("ɪᴛ's ɴᴏᴛ ʏᴏᴜʀ ǫᴜᴇʀʏ, ɴᴏʀ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.", show_alert=True)

    is_expanded = user_id in expanded_users
    await send_playlist_page(client, callback_query, user_id, 1, is_expanded, is_home=True)

@app.on_message(filters.command(["delsong", "rmsong"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language
async def del_plist_msg(client, message: Message, _):
    _playlist = await get_playlist_names(message.from_user.id)
    if _playlist:
        get = await message.reply_text(_["playlist_2"])
    else:
        return await message.reply_text(_["playlist_3"])
    keyboard, count = await get_keyboard(_, message.from_user.id)
    await get.edit_text(
        _["playlist_7"].format(count), reply_markup=keyboard
    )


async def get_keyboard(_, user_id):
    keyboard = InlineKeyboard(row_width=5)
    _playlist = await get_playlist_names(user_id)
    count = len(_playlist)
    for x in _playlist:
        _note = await get_playlist(user_id, x)
        title = _note["title"]
        title = title.title()
        keyboard.row(
            InlineKeyboardButton(
                text=title,
                callback_data=f"del_playlist {x}",
            )
        )
    keyboard.row(
        InlineKeyboardButton(
            text=_["PL_B_5"],
            callback_data=f"delete_warning",
        ),
        InlineKeyboardButton(
            text="ᴄʟᴏsᴇ", callback_data=f"close"
        ),
    )
    return keyboard, count

@app.on_callback_query(filters.regex("play_playlist") & ~BANNED_USERS)
@languageCB
async def play_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    mode = callback_data.split(None, 1)[1]
    user_id = CallbackQuery.from_user.id
    _playlist = await get_playlist_names(user_id)
    if not _playlist:
        try:
            return await CallbackQuery.answer(
                _["playlist_3"],
                show_alert=True,
            )
        except:
            return
    chat_id = CallbackQuery.message.chat.id
    user_name = CallbackQuery.from_user.first_name
    await CallbackQuery.message.delete()
    result = []
    try:
        await CallbackQuery.answer()
    except:
        pass
    video = True if mode == "v" else None
    mystic = await CallbackQuery.message.reply_text(_["play_1"])
    for vidids in _playlist:
        result.append(vidids)
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            CallbackQuery.message.chat.id,
            video,
            streamtype="playlist",
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = (
            e
            if ex_type == "AssistantErr"
            else _["general_3"].format(ex_type)
        )
        return await mystic.edit_text(err)
    return await mystic.delete()

@app.on_message(filters.command(["playplaylist", "playplist" "pplist", "pplay"], prefixes=["/", "", "!", "."]) & ~BANNED_USERS)
@languageCB
async def play_playlist_command(client, message, _):
    mode = message.command[1] if len(message.command) > 1 else None
    user_id = message.from_user.id
    _playlist = await get_playlist_names(user_id)
    
    if not _playlist:
        try:
            return await message.reply(
                _["playlist_3"],
                quote=True,
            )
        except:
            return
    
    chat_id = message.chat.id
    user_name = message.from_user.first_name
    
    try:
        await message.delete()
    except:
        pass
    
    result = []
    video = True if mode == "v" else None
    
    mystic = await message.reply_text(_["play_1"])
    
    for vidids in _playlist:
        result.append(vidids)
    
    try:
        await stream(
            _,
            mystic,
            user_id,
            result,
            chat_id,
            user_name,
            message.chat.id,
            video,
            streamtype="playlist",
        )
    except Exception as e:
        ex_type = type(e).__name__
        err = (
            e
            if ex_type == "AssistantErr"
            else _["general_3"].format(ex_type)
        )
        return await mystic.edit_text(err)
    
    return await mystic.delete()
    

import json

@app.on_message(filters.command(["addsong", "addplay"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language
async def add_playlist(client, message: Message, _):
    if len(message.command) < 2:
        return await message.reply_text("ᴘʀᴏᴠɪᴅᴇ ᴍᴇ ᴀ sᴏɴɢ ɴᴀᴍᴇ ᴏʀ sᴏɴɢ ʟɪɴᴋ ᴏʀ ʏᴏᴜᴛᴜʙᴇ ᴘʟᴀʏʟɪsᴛ ʟɪɴᴋ ᴀғᴛᴇʀ ᴛʜᴇ ᴄᴏᴍᴍᴀɴᴅ...")

    query = message.command[1]
    
    if "youtube.com/playlist" in query:
        adding = await message.reply_text("ᴀᴅᴅɪɴɢ sᴏɴɢs ɪɴ ᴘʟᴀʏʟɪsᴛ...")
        try:
            from pytube import Playlist
            from pytube import YouTube
            
            playlist = Playlist(query)
            video_urls = playlist.video_urls
            
        except Exception as e:
            return await message.reply_text(f"ᴇʀʀᴏʀ : {e}")

        if not video_urls:
            return await message.reply_text("ɴᴏ sᴏɴɢs ғᴏᴜɴᴅ ɪɴ ᴛʜᴇ ᴘʟᴀʏʟɪsᴛ ʟɪɴᴋs.")

        user_id = message.from_user.id
        for video_url in video_urls:
            video_id = video_url.split("v=")[-1]
            
            try:
                yt = YouTube(video_url)
                title = yt.title
                duration = yt.length
            except Exception as e:
                return await message.reply_text(f"ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ᴠɪᴅᴇᴏ ɪɴғᴏ : {e}")

            plist = {
                "videoid": video_id,
                "title": title,
                "duration": duration,
            }
            
            await save_playlist(user_id, video_id, plist)
            keyboardes = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ᴡᴀɴᴛ ᴛᴏ ʀᴇᴍᴏᴠᴇ sᴏɴɢ?", callback_data=f"open_playlist {user_id}")
                ]
            ]
        )
        await adding.delete()
        return await message.reply_text(text="ᴀʟʟ sᴏɴɢs ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ғʀᴏᴍ ʏᴏᴜʀ ʏᴏᴜᴛᴜʙᴇ ᴘʟᴀʏʟɪsᴛ ʟɪɴᴋ.", reply_markup=keyboardes)
        pass
    if "youtube.com/@" in query:
        addin = await message.reply_text("ᴀᴅᴅɪɴɢ sᴏɴɢs ɪɴ ᴘʟᴀʏʟɪsᴛ...")
        try:
            from pytube import YouTube

            channel_username = query
            videos = YouTube_videos(f"{query}/videos")
            video_urls = [video['url'] for video in videos]

        except Exception as e:
            return await message.reply_text(f"ᴇʀʀᴏʀ : {e}")

        if not video_urls:
            return await message.reply_text("ɴᴏ sᴏɴɢs ғᴏᴜɴᴅ ɪɴ ᴛʜᴇ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ.")

        user_id = message.from_user.id
        for video_url in video_urls:
            videosid = query.split("/")[-1].split("?")[0]

            try:
                yt = YouTube(f"https://youtu.be/{videosid}")
                title = yt.title
                duration = yt.length
            except Exception as e:
                return await message.reply_text(f"ᴇʀʀᴏʀ ғᴇᴛᴄʜɪɴɢ ᴠɪᴅᴇᴏ ɪɴғᴏ : {e}")

            plist = {
                "videoid": video_id,
                "title": title,
                "duration": duration,
            }

            await save_playlist(user_id, video_id, plist)
            keyboardes = InlineKeyboardMarkup(
            [            
                [
                    InlineKeyboardButton("ᴡᴀɴᴛ ʀᴇᴍᴏᴠᴇ sᴏɴɢ?", callback_data=f"open_playlist {user_id}")
                ]
            ]
        )
        await addin.delete()
        return await message.reply_text(text="**ᴀʟʟ sᴏɴɢs ʜᴀs ʙᴇᴇɴ ᴀᴅᴅᴇᴅ sᴜᴄᴄᴇssғᴜʟʟʏ ғʀᴏᴍ ʏᴏᴜʀ ʏᴏᴜᴛᴜʙᴇ ᴄʜᴀɴɴᴇʟ ʟɪɴᴋ.", reply_markup=keyboardes)
        pass
    if "https://youtu.be" in query:
        try:
            add = await message.reply_text("**ᴀᴅᴅɪɴɢ sᴏɴɢs ɪɴ ᴘʟᴀʏʟɪsᴛ...")
            from pytube import Playlist
            from pytube import YouTube
            videoid = query.split("/")[-1].split("?")[0]
            user_id = message.from_user.id
            thumbnail = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
            _check = await get_playlist(user_id, videoid)
            if _check:
                try:
                    await add.delete()
                    return await message.reply_photo(thumbnail, caption=_["playlist_8"])
                except KeyError:
                    pass

            _count = await get_playlist_names(user_id)
            count = len(_count)
            if count == SERVER_PLAYLIST_LIMIT:
                try:
                    return await message.reply_text(_["playlist_9"].format(SERVER_PLAYLIST_LIMIT))
                except KeyError:
                    pass

            try:
                yt = YouTube(f"https://youtu.be/{videoid}")
                title = yt.title
                duration = yt.length
                thumbnail = f"https://img.youtube.com/vi/{videoid}/maxresdefault.jpg"
                plist = {
                    "videoid": videoid,
                    "title": title,
                    "duration": duration,
                }
                await save_playlist(user_id, videoid, plist)

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("ʀᴇᴍᴏᴠᴇ ғʀᴏᴍ ᴘʟᴀʏʟɪsᴛ", callback_data=f"remove_playlist {videoid}")
                        ]
                    ]
                )
                await add.delete()
                await message.reply_photo(thumbnail, caption="ᴀᴅᴅᴇᴅ sᴏɴɢ ɪɴ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.", reply_markup=keyboard)
            except Exception as e:
                print(f"Error: {e}")
                await message.reply_text(str(e))
        except Exception as e:
            return await message.reply_text(str(e))
            pass
    else:
        from PROMUSIC import YouTube
        query = " ".join(message.command[1:])
        print(query)

        try:
            results = YoutubeSearch(query, max_results=1).to_dict()
            link = f"https://youtube.com{results[0]['url_suffix']}"
            title = results[0]["title"][:40]
            thumbnail = results[0]["thumbnails"][0]
            thumb_name = f"{title}.jpg"
            thumb = requests.get(thumbnail, allow_redirects=True)
            open(thumb_name, "wb").write(thumb.content)
            duration = results[0]["duration"]
            videoid = results[0]["id"]
            views = results[0]["views"]
            channel_name = results[0]["channel"]

            user_id = message.from_user.id
            _check = await get_playlist(user_id, videoid)
            if _check:
                try:
                    return await message.reply_photo(thumbnail, caption=_["playlist_8"])
                except KeyError:
                    pass

            _count = await get_playlist_names(user_id)
            count = len(_count)
            if count == SERVER_PLAYLIST_LIMIT:
                try:
                    return await message.reply_text(_["playlist_9"].format(SERVER_PLAYLIST_LIMIT))
                except KeyError:
                    pass

            m = await message.reply("ᴀᴅᴅɪɴɢ sᴏɴɢ...")
            title, duration_min, _, _, _ = await YouTube.details(videoid, True)
            title = (title[:50]).title()
            plist = {
                "videoid": videoid,
                "title": title,
                "duration": duration_min,
            }

            await save_playlist(user_id, videoid, plist)

            keyboard = InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton("ʀᴇᴍᴏᴠᴇ ғʀᴏᴍ ᴘʟᴀʏʟɪsᴛ", callback_data=f"remove_playlist {videoid}")
                    ]
                ]
            )
            await m.delete()
            await message.reply_photo(thumbnail, caption="ᴀᴅᴅᴇᴅ sᴏɴɢ ɪɴ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ...", reply_markup=keyboard)

        except KeyError:
            return await message.reply_text("ɪɴᴠᴀʟɪᴅ ᴅᴀᴛᴀ ғᴏʀᴍᴀᴛ ʀᴇᴄᴇɪᴠᴇᴅ.")
        except Exception as e:
            pass

        
@app.on_callback_query(filters.regex("open_playlist") & ~BANNED_USERS)
@languageCB
async def open_playlist(client, CallbackQuery, _):
    _playlist = await get_playlist_names(CallbackQuery.from_user.id)
    if _playlist:
        get = await CallbackQuery.message.edit_text(_["playlist_2"])
    else:
        return await CallbackQuery.message.edit_text(_["playlist_3"])
    keyboard, count = await get_keyboard(_, CallbackQuery.from_user.id)
    await get.edit_text(_["playlist_7"].format(count), reply_markup=keyboard)


@app.on_callback_query(filters.regex("remove_playlist") & ~BANNED_USERS)
@languageCB
async def del_plist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    user_id = CallbackQuery.from_user.id
    deleted = await delete_playlist(
        CallbackQuery.from_user.id, videoid
    )
    if deleted:
        try:
            await CallbackQuery.answer(
                _["playlist_11"], show_alert=True
            )
        except:
            pass
    else:
        try:
            return await CallbackQuery.answer(
                _["playlist_12"], show_alert=True
            )
        except:
            return
    keyboards = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ʀᴇᴄᴏᴠᴇʀ sᴏɴɢ", callback_data=f"recover_playlist {videoid}")
                ]
            ]
        )
    return await CallbackQuery.edit_message_text(
    text="ʏᴏᴜʀ sᴏɴɢ ʜᴀs ʙᴇᴇɴ ᴅᴇʟᴇᴛᴇᴅ ғʀᴏᴍ ᴘʟᴀʏʟɪsᴛ...",
    reply_markup=keyboards
)


@app.on_callback_query(filters.regex("recover_playlist") & ~BANNED_USERS)
@languageCB
async def add_playlist(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    user_id = CallbackQuery.from_user.id
    _check = await get_playlist(user_id, videoid)
    if _check:
        try:
            return await CallbackQuery.answer(
                _["playlist_8"], show_alert=True
            )
        except:
            return
    _count = await get_playlist_names(user_id)
    count = len(_count)
    if count == SERVER_PLAYLIST_LIMIT:
        try:
            return await CallbackQuery.answer(
                _["playlist_9"].format(SERVER_PLAYLIST_LIMIT),
                show_alert=True,
            )
        except:
            return
    (
        title,
        duration_min,
        duration_sec,
        thumbnail,
        vidid,
    ) = await YouTube.details(videoid, True)
    title = (title[:50]).title()
    plist = {
        "videoid": vidid,
        "title": title,
        "duration": duration_min,
    }
    await save_playlist(user_id, videoid, plist)
    try:
        title = (title[:30]).title()
        keyboardss = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("ʀᴇᴍᴏᴠᴇ ᴀɢᴀɪɴ", callback_data=f"remove_playlist {videoid}")
                ]
            ]
        )
        return await CallbackQuery.edit_message_text(text="ʀᴇᴄᴏᴠᴇʀᴇᴅ sᴏɴɢ ɪɴ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ...",
            reply_markup=keyboardss
        )
    except:
        return

@app.on_callback_query(filters.regex("add_playlist") & ~BANNED_USERS)
@languageCB
async def add_playlist(client, CallbackQuery, _):
    await CallbackQuery.answer("ᴛᴏ ᴀᴅᴅ ᴀ sᴏɴɢ ɪɴ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ ᴊᴜsᴛ ᴛʏᴘᴇ /addplaylist 'song name'", show_alert=True)
    

@app.on_callback_query(filters.regex("PRO_playlist") & ~BANNED_USERS)
@languageCB
async def add_playlist(client, CallbackQuery, _):
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    user_id = CallbackQuery.from_user.id
    _check = await get_playlist(user_id, videoid)
    if _check:
        try:
            from PROMUSIC import YouTube
            return await CallbackQuery.answer(
                _["playlist_8"], show_alert=True
            )
        except:
            return
    _count = await get_playlist_names(user_id)
    count = len(_count)
    if count == SERVER_PLAYLIST_LIMIT:
        try:
            return await CallbackQuery.answer(
                _["playlist_9"].format(SERVER_PLAYLIST_LIMIT),
                show_alert=True,
            )
        except:
            return
    (
        title,
        duration_min,
        duration_sec,
        thumbnail,
        vidid,
    ) = await YouTube.details(videoid, True)
    title = (title[:50]).title()
    plist = {
        "videoid": vidid,
        "title": title,
        "duration": duration_min,
    }
    await save_playlist(user_id, videoid, plist)
    try:
        title = (title[:30]).title()
        return await CallbackQuery.answer(
            _["playlist_10"].format(title), show_alert=True
        )
    except:
        return

DELETE_ALL_PLAYLIST_COMMAND = ("delplaylist")

@app.on_message(filters.command(["delplaylist", "rmplaylist" "rmplist"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language
async def delete_all_playlists(client, message, _):
    from PROMUSIC import YouTube
    user_id = message.from_user.id
    _playlist = await get_playlist_names(user_id)
    if _playlist:
        try:
            upl = warning_markup(_)
            await message.reply_text(_["playlist_14"], reply_markup=upl)
        except:
            pass
    else:
        await message.reply_text(_["playlist_3"])

        
@app.on_callback_query(filters.regex("del_playlist") & ~BANNED_USERS)
@languageCB
async def del_plist(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    callback_data = CallbackQuery.data.strip()
    videoid = callback_data.split(None, 1)[1]
    user_id = CallbackQuery.from_user.id
    deleted = await delete_playlist(
        CallbackQuery.from_user.id, videoid
    )
    if deleted:
        try:
            await CallbackQuery.answer(
                _["playlist_11"], show_alert=True
            )
        except:
            pass
    else:
        try:
            return await CallbackQuery.answer(
                _["playlist_12"], show_alert=True
            )
        except:
            return
    keyboard, count = await get_keyboard(_, user_id)
    return await CallbackQuery.edit_message_reply_markup(
        reply_markup=keyboard
    )



@app.on_callback_query(
    filters.regex("delete_whole_playlist") & ~BANNED_USERS
)
@languageCB
async def del_whole_playlist(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    
    await CallbackQuery.answer("ᴏᴋ ᴡᴀɪᴛ...\n\nᴅᴇʟᴇᴛɪɴɢ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ...", show_alert=True)
    _playlist = await get_playlist_names(CallbackQuery.from_user.id)
    for x in _playlist:
        await delete_playlist(CallbackQuery.from_user.id, x)

    return await CallbackQuery.edit_message_text(_["playlist_13"])

@app.on_callback_query(
    filters.regex("get_playlist_playmode") & ~BANNED_USERS
)
@languageCB
async def get_playlist_playmode_(client, CallbackQuery, _):
    try:
        await CallbackQuery.answer()
    except:
        pass
    buttons = get_playlist_markup(_)
    return await CallbackQuery.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(
    filters.regex("delete_warning") & ~BANNED_USERS
)
@languageCB
async def delete_warning_message(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    try:
        await CallbackQuery.answer()
    except:
        pass
    upl = warning_markup(_)
    return await CallbackQuery.edit_message_text(
        _["playlist_14"], reply_markup=upl
    )


@app.on_callback_query(filters.regex("home_play") & ~BANNED_USERS)
@languageCB
async def home_play_(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    try:
        await CallbackQuery.answer()
    except:
        pass
    buttons = botplaylist_markup(_)
    return await CallbackQuery.edit_message_reply_markup(
        reply_markup=InlineKeyboardMarkup(buttons)
    )


@app.on_callback_query(
    filters.regex("del_back_playlist") & ~BANNED_USERS
)
@languageCB
async def del_back_playlist(client, CallbackQuery, _):
    from PROMUSIC import YouTube
    user_id = CallbackQuery.from_user.id
    _playlist = await get_playlist_names(user_id)
    if _playlist:
        try:
            await CallbackQuery.answer(
                _["playlist_2"], show_alert=True
            )
        except:
            pass
    else:
        try:
            return await CallbackQuery.answer(
                _["playlist_3"], show_alert=True
            )
        except:
            return
    keyboard, count = await get_keyboard(_, user_id)
    return await CallbackQuery.edit_message_text(
        _["playlist_7"].format(count), reply_markup=keyboard
    )


@app.on_message(filters.command("pstats") & filters.user(OWNER_ID))
async def total_stats(client, message: Message):
    total_users = 0
    total_playlists = 0
    total_deleted = 0
    total_songs = 0
    total_cloned_songs = 0
    total_cloned_playlists = 0
    total_clones = 0  
    async for data in playlistdb.find():
        total_users += 1
        user_playlists = data.get("notes", {})
        total_playlists += len(user_playlists)
        total_deleted += data.get("deleted_count", 0)

        for playlist_data in user_playlists.values():
            songs = playlist_data.get("songs", [])
            total_songs += len(songs)

            if playlist_data.get("is_cloned", False):
                total_cloned_songs += len(songs)
                total_cloned_playlists += 1
                total_clones += playlist_data.get("clone_count", 0)  # Track clones per playlist

    stats_message = (
        f"**ᴘʟᴀʏʟɪsᴛ sᴛᴀᴛs**\n\n"
        f"• **ᴘʟᴀʏʟɪsᴛs :** {total_users}\n"
        f"• **ᴛᴏᴛᴀʟ sᴏɴɢs :** {total_playlists}\n"
    )

    await message.reply_text(stats_message)

@app.on_message(filters.command(["cloneplaylist", "cloneplist"], prefixes=["/", "!", "."]) & ~BANNED_USERS)
@language
async def clone_playlist(client, message: Message, _):
    if not message.reply_to_message or not message.reply_to_message.from_user:
        return await message.reply_text("ʀᴇᴘʟʏ ᴛᴏ ᴀ ᴜsᴇʀ ᴛᴏ ᴄʟᴏɴᴇ ᴛʜᴇɪʀ ᴘʟᴀʏʟɪsᴛ.")

    target_user_id = message.reply_to_message.from_user.id
    user_id = message.from_user.id

    if target_user_id == user_id:
        return await message.reply_text("ʜᴏᴡ ᴜsᴇʀ ᴄᴀɴ ᴄʟᴏɴᴇ ᴏᴡɴ ᴘʟᴀʏʟɪsᴛ ?")

    target_playlist = await _get_playlists(target_user_id)
    if not target_playlist:
        return await message.reply_text("ᴛʜᴇ ᴜsᴇʀ ʜᴀs ɴᴏᴛ ᴄʀᴇᴀᴛᴇᴅ ᴀɴʏ ᴘʟᴀʏʟɪsᴛ.")

    user_playlist = await _get_playlists(user_id)
    for name, data in target_playlist.items():
        if name not in user_playlist:
            await save_playlist(user_id, name, data)

            if "clone_count" not in data:
                data["clone_count"] = 0
            data["clone_count"] += 1
            await update_playlist(target_user_id, name, data)  

    await message.reply_text("ᴀʟʟ sᴏɴɢs ғʀᴏᴍ ᴛʜᴇ ᴜsᴇʀ'ꜱ ᴘʟᴀʏʟɪsᴛ ʜᴀᴠᴇ ʙᴇᴇɴ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴘʟᴀʏʟɪsᴛ.")