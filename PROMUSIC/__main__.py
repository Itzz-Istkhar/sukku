
import asyncio
import importlib

from pyrogram import idle
from pytgcalls.exceptions import NoActiveGroupCall

import config
from PROMUSIC import LOGGER, app, userbot
from PROMUSIC.core.call import PRO
from PROMUSIC.misc import sudo
from PROMUSIC.plugins import ALL_MODULES
from PROMUSIC.utils.database import get_banned_users, get_gbanned
from config import BANNED_USERS


async def init():
    if not config.STRING1:
        LOGGER(__name__).error("String Session not filled, please provide a valid session.")
        exit()
    await sudo()
    try:
        users = await get_gbanned()
        for user_id in users:
            BANNED_USERS.add(user_id)
        users = await get_banned_users()
        for user_id in users:
            BANNED_USERS.add(user_id)
    except:
        pass
    await app.start()
    for all_module in ALL_MODULES:
        importlib.import_module("PROMUSIC.plugins" + all_module)
    LOGGER("PROMUSIC.plugins").info("𝐀𝐥𝐥 𝐅𝐞𝐚𝐭𝐮𝐫𝐞𝐬 𝐋𝐨𝐚𝐝𝐞𝐝 𝐁𝐚𝐛𝐲🥳...")
    await userbot.start()
    await PRO.start()
    try:
        await PRO.stream_call("https://te.legra.ph/file/29f784eb49d230ab62e9e.mp4")
    except NoActiveGroupCall:
        LOGGER("PROMUSIC").error(
            "𝗣𝗹𝗭 𝗦𝗧𝗔𝗥𝗧 𝗬𝗢𝗨𝗥 𝗟𝗢𝗚 𝗚𝗥𝗢𝗨𝗣 𝗩𝗢𝗜𝗖𝗘𝗖𝗛𝗔𝗧\𝗖𝗛𝗔𝗡𝗡𝗘𝗟\n\n𝗠𝗨𝗦𝗜𝗖 𝗕𝗢𝗧 𝗦𝗧𝗢𝗣........"
        )
        exit()
    except:
        pass
    await PRO.decorators()
    LOGGER("PROMUSIC").info(
        "╔═════ஜ۩۞۩ஜ════╗\n  ☠︎︎𝗠𝗔𝗗𝗘 𝗕𝗬 𝗣𝗿𝗼𝗕𝗼𝘁𝘀☠︎︎\n╚═════ஜ۩۞۩ஜ════╝"
    )
    await idle()
    await app.stop()
    await userbot.stop()
    LOGGER("PROMUSIC").info("𝗦𝗧𝗢𝗣 𝗣𝗿𝗼𝗕𝗼𝘁 𝗠𝗨𝗦𝗜𝗖🎻 𝗕𝗢𝗧..")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(init())
