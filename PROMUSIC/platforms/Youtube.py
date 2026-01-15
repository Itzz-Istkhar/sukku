import asyncio
import os
import re
import json
from typing import Union
import requests
import yt_dlp
from pyrogram.enums import MessageEntityType
from pyrogram.types import Message
from youtubesearchpython.__future__ import VideosSearch
from PROMUSIC.utils.database import is_on_off
from PROMUSIC.utils.formatters import time_to_seconds
import os
import glob
import random
import logging
from ..logging import LOGGER
import aiohttp
import config
# Puraani YT_API_KEY import hata di hai
from config import YT_API_URL

YT_API_KEYS = {
    1: "30DxNexGenBotsab35bb", # bitesmm
    2: "30DxNexGenBots8c8be6", # Code365Days
    3: "30DxNexGenBots413666", # FilmiGo
    4: "30DxNexGenBotsc834ee", # OwnSocialPanel
    5: "30DxNexGenBots21bf59", # MxFly
    6: "30DxNexGenBots13aa2d", # StoreJyan
    7: "30DxNexGenBots0f9173", # ProCookies FireFox
    8: "30DxNexGenBots5a1f0a", # YasirAkhtar
    9: "30DxNexGenBots5a1f0a", # YasirAlam 1 20
    10: "30DxNexGenBots008766", # probotscookies firefox 
    11: "30DxNexGenBots438140", # Nilag Offer 
    12: "30DxNexGenBotsbac8c9", # naji 1500
    13: "30DxNexGenBotse9e610" # yasircpr
}

# Yeh naya set hai expired keys ko store karne ke liye
EXPIRED_API_KEYS = set()


def cookie_txt_file():
    cookie_dir = f"{os.getcwd()}/cookies"
    cookies_files = [f for f in os.listdir(cookie_dir) if f.endswith(".txt")]

    cookie_file = os.path.join(cookie_dir, random.choice(cookies_files))
    return cookie_file


# --- YEH RAHA AAPKA NAYA DOWNLOAD_SONG FUNCTION ---

async def download_song(link: str):
    """
    Downloads a song using the API, with key rotation.
    Cycles through YT_API_KEYS, skipping keys in EXPIRED_API_KEYS.
    """
    video_id = link.split('v=')[-1].split('&')[0]

    download_folder = "downloads"
    # Aapke original code ke hisaab se file check
    for ext in ["mp3", "m4a", "webm"]:
        file_path = f"{download_folder}/{video_id}.{ext}"
        if os.path.exists(file_path):
            #print(f"File already exists: {file_path}")
            return file_path
            
    download_url = None
    data = None # Successful response ka data store karne ke liye

    async with aiohttp.ClientSession() as session:
        # Woh keys nikalo jo expired nahi hain
        available_keys = []
        for key_num in sorted(YT_API_KEYS.keys()):
            key_val = YT_API_KEYS[key_num]
            if key_val not in EXPIRED_API_KEYS:
                available_keys.append(key_val)
        
        if not available_keys:
            LOGGER(__name__).error(
                "Saari API keys expire ho chuki hain. API download nahi ho sakta."
            )
            return None

        # Har available key ko try karo
        for api_key in available_keys:
            song_url = f"{YT_API_URL}/song/{video_id}?api={api_key}"
            LOGGER(__name__).error(
                f"Trying API Key: ...{api_key[-6:]}"
            )
            
            try:
                # "downloading" status ke liye inner loop
                while True:  
                    async with session.get(song_url) as response:
                        if response.status != 200:
                            raise Exception(f"API request failed with status code {response.status}")
                        
                        try:
                            data = await response.json()
                        except aiohttp.ContentTypeError:
                            text_response = await response.text()
                            LOGGER(__name__).error(f"API key {api_key} ne JSON nahi diya: {text_response[:200]}")
                            raise Exception("Non-JSON response from API")

                        status = data.get("status", "").lower()
                        
                        if status == "downloading":
                            await asyncio.sleep(2)
                            continue  # Isi key se dobara check karo
                        
                        elif status == "error":
                            error_msg = data.get("error") or data.get("message") or "Unknown error"
                            error_msg_lower = error_msg.lower()
                            
                            # Check karo agar key expired hai
                            if "invalid api key" in error_msg_lower or \
                               "expired" in error_msg_lower or \
                               "reached" in error_msg_lower:
                                
                                LOGGER(__name__).error(f"API Key ...{api_key[-6:]} expire ho gayi hai: {error_msg}")
                                EXPIRED_API_KEYS.add(api_key)  # Expired set mein daal do
                                break  # Inner loop todo, agli key try karo (outer loop)
                            else:
                                # Koi aur error hai (jaise video nahi mili)
                                raise Exception(f"API error (key se related nahi): {error_msg}")
                        
                        elif status == "done":
                            download_url = data.get("link")
                            if not download_url:
                                raise Exception("API status 'done' hai par download URL nahi mila.")
                            LOGGER(__name__).error(f"Download link mil gaya: ...{api_key[-6:]}")
                            break  # Inner loop todo
                        
                        else:
                            raise Exception(f"Unexpected status '{status}' API se mila.")
                
                if download_url:
                    break  # Outer loop todo (link mil gaya hai)

            except Exception as e:
                LOGGER(__name__).error(f"API key ...{api_key[-6:]} ke saath error: {e}")
                if "API error (key se related nahi)" in str(e):
                     LOGGER(__name__).error(f"Download attempt ruka gaya kyunki API ne video error diya.")
                     return None
                # Agar key ka error nahi tha, to bhi agli key try karo

        # --- Key loop ke baad ---

        if not download_url:
            LOGGER(__name__).error(f"Sabhi available keys try karne ke baad bhi download URL nahi mila.")
            return None

        # --- File download karo (aapke original code ke mutabik) ---
        try:
            file_format = data.get("format", "mp3")
            file_extension = file_format.lower()
            file_name = f"{video_id}.{file_extension}"
            download_folder = "downloads"
            os.makedirs(download_folder, exist_ok=True)
            file_path = os.path.join(download_folder, file_name)

            async with session.get(download_url) as file_response:
                if file_response.status != 200:
                    LOGGER(__name__).error(f"File download nahi hua: HTTP status {file_response.status}")
                    return None
                
                with open(file_path, 'wb') as f:
                    while True:
                        chunk = await file_response.content.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                return file_path
        except aiohttp.ClientError as e:
            LOGGER(__name__).error(f"Network ya client error download ke waqt: {e}")
            return None
        except Exception as e:
            LOGGER(__name__).error(f"Song download karte waqt error: {e}")
            return None
            
    return None

# --- BAAKI SAARA CODE WAISE KA WAISA HAI ---

async def check_file_size(link):
    async def get_format_info(link):
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies", cookie_txt_file(),
            "-J",
            link,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            LOGGER(__name__).error(f"Error:\n{stderr.decode()}")
            return None
        return json.loads(stdout.decode())

    def parse_size(formats):
        total_size = 0
        for format in formats:
            if 'filesize' in format:
                total_size += format['filesize']
        return total_size

    info = await get_format_info(link)
    if info is None:
        return None
    
    formats = info.get('formats', [])
    if not formats:
        LOGGER(__name__).error(f"No formats found.")
        return None
    
    total_size = parse_size(formats)
    return total_size

async def shell_cmd(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    out, errorz = await proc.communicate()
    if errorz:
        if "unavailable videos are hidden" in (errorz.decode("utf-8")).lower():
            return out.decode("utf-8")
        else:
            return errorz.decode("utf-8")
    return out.decode("utf-8")


class YouTubeAPI:
    def __init__(self):
        self.base = "https://www.youtube.com/watch?v="
        self.regex = r"(?:youtube\.com|youtu\.be)"
        self.status = "https://www.youtube.com/oembed?url="
        self.listbase = "https://youtube.com/playlist?list="
        self.reg = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

    async def exists(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if re.search(self.regex, link):
            return True
        else:
            return False

    async def url(self, message_1: Message) -> Union[str, None]:
        messages = [message_1]
        if message_1.reply_to_message:
            messages.append(message_1.reply_to_message)
        text = ""
        offset = None
        length = None
        for message in messages:
            if offset:
                break
            if message.entities:
                for entity in message.entities:
                    if entity.type == MessageEntityType.URL:
                        text = message.text or message.caption
                        offset, length = entity.offset, entity.length
                        break
            elif message.caption_entities:
                for entity in message.caption_entities:
                    if entity.type == MessageEntityType.TEXT_LINK:
                        return entity.url
        if offset in (None,):
            return None
        return text[offset : offset + length]

    async def details(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
            vidid = result["id"]
            if str(duration_min) == "None":
                duration_sec = 0
            else:
                duration_sec = int(time_to_seconds(duration_min))
        return title, duration_min, duration_sec, thumbnail, vidid

    async def title(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
        return title

    async def duration(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            duration = result["duration"]
        return duration

    async def thumbnail(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        return thumbnail

    async def video(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        proc = await asyncio.create_subprocess_exec(
            "yt-dlp",
            "--cookies",cookie_txt_file(),
            "-g",
            "-f",
            "best[height<=?720][width<=?1280]",
            f"{link}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if stdout:
            return 1, stdout.decode().split("\n")[0]
        else:
            return 0, stderr.decode()

    async def playlist(self, link, limit, user_id, videoid: Union[bool, str] = None):
        if videoid:
            link = self.listbase + link
        if "&" in link:
            link = link.split("&")[0]
        playlist = await shell_cmd(
            f"yt-dlp -i --get-id --flat-playlist --cookies {cookie_txt_file()} --playlist-end {limit} --skip-download {link}"
        )
        try:
            result = playlist.split("\n")
            for key in result:
                if key == "":
                    result.remove(key)
        except:
            result = []
        return result

    async def track(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        results = VideosSearch(link, limit=1)
        for result in (await results.next())["result"]:
            title = result["title"]
            duration_min = result["duration"]
            vidid = result["id"]
            yturl = result["link"]
            thumbnail = result["thumbnails"][0]["url"].split("?")[0]
        track_details = {
            "title": title,
            "link": yturl,
            "vidid": vidid,
            "duration_min": duration_min,
            "thumb": thumbnail,
        }
        return track_details, vidid

    async def formats(self, link: str, videoid: Union[bool, str] = None):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        ytdl_opts = {"quiet": True, "cookiefile" : cookie_txt_file()}
        ydl = yt_dlp.YoutubeDL(ytdl_opts)
        with ydl:
            formats_available = []
            r = ydl.extract_info(link, download=False)
            for format in r["formats"]:
                try:
                    str(format["format"])
                except:
                    continue
                if not "dash" in str(format["format"]).lower():
                    try:
                        format["format"]
                        format["filesize"]
                        format["format_id"]
                        format["ext"]
                        format["format_note"]
                    except:
                        continue
                    formats_available.append(
                        {
                            "format": format["format"],
                            "filesize": format["filesize"],
                            "format_id": format["format_id"],
                            "ext": format["ext"],
                            "format_note": format["format_note"],
                            "yturl": link,
                        }
                    )
        return formats_available, link

    async def slider(
        self,
        link: str,
        query_type: int,
        videoid: Union[bool, str] = None,
    ):
        if videoid:
            link = self.base + link
        if "&" in link:
            link = link.split("&")[0]
        a = VideosSearch(link, limit=10)
        result = (await a.next()).get("result")
        title = result[query_type]["title"]
        duration_min = result[query_type]["duration"]
        vidid = result[query_type]["id"]
        thumbnail = result[query_type]["thumbnails"][0]["url"].split("?")[0]
        return title, duration_min, thumbnail, vidid

    async def download(
        self,
        link: str,
        mystic,
        video: Union[bool, str] = None,
        videoid: Union[bool, str] = None,
        songaudio: Union[bool, str] = None,
        songvideo: Union[bool, str] = None,
        format_id: Union[bool, str] = None,
        title: Union[bool, str] = None,
    ) -> str:
        if videoid:
            link = self.base + link
        loop = asyncio.get_running_loop()
        def audio_dl():
            ydl_optssx = {
                "format": "bestaudio/best",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def video_dl():
            ydl_optssx = {
                "format": "(bestvideo[height<=?720][width<=?1280][ext=mp4])+(bestaudio[ext=m4a])",
                "outtmpl": "downloads/%(id)s.%(ext)s",
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "cookiefile" : cookie_txt_file(),
                "no_warnings": True,
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            info = x.extract_info(link, False)
            xyz = os.path.join("downloads", f"{info['id']}.{info['ext']}")
            if os.path.exists(xyz):
                return xyz
            x.download([link])
            return xyz

        def song_video_dl():
            formats = f"{format_id}+140"
            fpath = f"downloads/{title}"
            ydl_optssx = {
                "format": formats,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_txt_file(),
                "prefer_ffmpeg": True,
                "merge_output_format": "mp4",
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        def song_audio_dl():
            fpath = f"downloads/{title}.%(ext)s"
            ydl_optssx = {
                "format": format_id,
                "outtmpl": fpath,
                "geo_bypass": True,
                "nocheckcertificate": True,
                "quiet": True,
                "no_warnings": True,
                "cookiefile" : cookie_txt_file(),
                "prefer_ffmpeg": True,
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "mp3",
                        "preferredquality": "192",
                    }
                ],
            }
            x = yt_dlp.YoutubeDL(ydl_optssx)
            x.download([link])

        if songvideo:
            await download_song(link)
            fpath = f"downloads/{link}.mp3"
            return fpath
        elif songaudio:
            await download_song(link)
            fpath = f"downloads/{link}.mp3"
            return fpath
        elif video:
            if await is_on_off(1):
                direct = True
                downloaded_file = await download_song(link)
            else:
                proc = await asyncio.create_subprocess_exec(
                    "yt-dlp",
                    "--cookies",cookie_txt_file(),
                    "-g",
                    "-f",
                    "best[height<=?720][width<=?1280]",
                    f"{link}",
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                stdout, stderr = await proc.communicate()
                if stdout:
                    downloaded_file = stdout.decode().split("\n")[0]
                    direct = False
                else:
                    file_size = await check_file_size(link)
                    if not file_size:
                        LOGGER(__name__).error(f"None file Size")
                        return
                    total_size_mb = file_size / (1024 * 1024)
                    if total_size_mb > 250:
                        LOGGER(__name__).error(f"File size {total_size_mb:.2f} MB exceeds the 100MB limit.")
                        return None
                    direct = True
                    downloaded_file = await loop.run_in_executor(None, video_dl)
        else:
            direct = True
            downloaded_file = await download_song(link)
        return downloaded_file, direct
    
