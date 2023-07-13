import pak
import caseus

import asyncio
import itertools
import json

from pathlib import Path

import aiohttp
import aiofiles
import aiofiles.os

class Dumper(caseus.Client):
    EXTERNAL_DIR = "external"

    TRANSFORMICE_SWF_URL          = "http://www.transformice.com/Transformice.swf"
    TRANSFORMICE_CHARGEUR_SWF_URL = "http://www.transformice.com/TransformiceChargeur.swf"

    TRANSLATIONS_URL_FMT = "http://www.transformice.com/langues/tfm-{language}.gz"

    IMAGES_URL = "http://www.transformice.com/images/"

    MISC_IMAGES = [
        "x_transformice/x_interface/x_tag-collector.png",

        "M_0.png",
        "M_1.png",
    ]

    LIBRARY_PATH = "x_bibliotheques/"

    STATIC_FUR_LIBRARIES = [
        "x_fourrures.swf",
        "x_fourrures2.swf",
        "x_fourrures3.swf",
        "x_fourrures4.swf",
        "x_fourrures5.swf"
    ]

    MAX_STATIC_FUR_ID = 217

    SPECIFIC_FUR_LIBRARY_FMT = "fourrures/f{fur_id}.swf"

    STATIC_ITEM_LIBRARIES = [
        "x_meli_costumes.swf",
        "costume1.swf",
    ]

    STATIC_SHAMAN_OBJECT_LIBRARIES = [
        "x_items_chaman.swf",
    ]

    MAX_STATIC_SHAMAN_OBJECT_SKIN_ID = {
        # Base ID: Skin ID.

        1:  42,
        2:  46,
        3:  40,
        4:  43,
        6:  36,
        7:  9,
        10: 21,
        17: 35,
        28: 44,
    }

    SPECIFIC_SHAMAN_OBJECT_LIBRARY_FMT = "chamanes/o{base_id},{skin_id}.swf"

    EMOJI_PATH_FMT = "x_transformice/x_smiley/{emoji_id}.png"

    SHOP_INFO_FILE = "shop-info.json"

    def __init__(self, archive_dir, **kwargs):
        super().__init__(connect_to_satellite=False, **kwargs)

        self.archive_dir = Path(archive_dir)

        self.base_timestamp = None

        # A dictionary with positive keys as regular item IDs
        # and negative keys with shaman item IDs, with values
        # of 'ShopSpecialOfferPacket'.
        #
        # This is how the game stores them.
        self.special_offers = {}

        self.language_codes   = None
        self.load_shop_packet = None

    @property
    def shop_info_path(self):
        return self.archive_dir / self.SHOP_INFO_FILE

    def external_path(self, url):
        return self.archive_dir / self.EXTERNAL_DIR / url.split("://", 1)[1]

    async def download(self, url):
        download_path = self.external_path(url)

        if await aiofiles.os.path.exists(download_path):
            return

        await aiofiles.os.makedirs(download_path.parent, exist_ok=True)

        async with aiofiles.open(download_path, "wb") as f:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    await f.write(await response.read())

    async def download_translations(self, language):
        await self.download(self.TRANSLATIONS_URL_FMT.format(language=language))

    async def download_image(self, image):
        await self.download(self.IMAGES_URL + image)

    async def download_library(self, library):
        await self.download_image(self.LIBRARY_PATH + library)

    async def download_specific_fur(self, fur_id):
        await self.download_library(self.SPECIFIC_FUR_LIBRARY_FMT.format(fur_id=fur_id))

    async def download_specific_shaman_object(self, base_id, skin_id):
        await self.download_library(self.SPECIFIC_SHAMAN_OBJECT_LIBRARY_FMT.format(base_id=base_id, skin_id=skin_id))

    async def download_emoji(self, emoji_id):
        await self.download_image(self.EMOJI_PATH_FMT.format(emoji_id=emoji_id))

    async def on_start(self):
        if await aiofiles.os.path.exists(self.archive_dir):
            raise ValueError(f"Specified archive directory '{self.archive_dir}' already exists")

        await super().on_start()

        shop_info = dict(
            base_timestamp = self.base_timestamp,
            special_offers = [],
            items          = [],
            outfits        = [],
            shaman_objects = [],
            emojis         = [],
        )

        async with asyncio.TaskGroup() as tg:
            tg.create_task(
                self.download(self.TRANSFORMICE_SWF_URL)
            )

            tg.create_task(
                self.download(self.TRANSFORMICE_CHARGEUR_SWF_URL)
            )

            for image in self.MISC_IMAGES:
                tg.create_task(
                    self.download_image(image)
                )

            for code in self.language_codes:
                tg.create_task(
                    self.download_translations(code)
                )

            for library in itertools.chain(
                self.STATIC_FUR_LIBRARIES,
                self.STATIC_ITEM_LIBRARIES,
                self.STATIC_SHAMAN_OBJECT_LIBRARIES,
            ):
                tg.create_task(
                    self.download_library(library)
                )

            for offer in self.special_offers.values():
                shop_info["special_offers"].append(dict(
                    is_sale             = offer.is_sale,
                    is_regular_item     = offer.is_regular_item,
                    item_id             = offer.item_id,
                    ends_timestamp      = offer.ends_timestamp,
                    discount_percentage = offer.discount_percentage,
                ))

            for item in self.load_shop_packet.items:
                shop_info["items"].append(dict(
                    category_id = item.category_id,
                    item_id     = item.item_id,
                    num_colors  = item.num_colors,
                    is_new      = item.is_new,
                    info        = item.info.value,
                    cheese_cost = item.cheese_cost,
                    fraise_cost = item.fraise_cost,
                    needed_item = item.needed_item,
                ))

                if item.category_id == 22 and item.item_id > self.MAX_STATIC_FUR_ID:
                    tg.create_task(
                        self.download_specific_fur(item.item_id)
                    )

            for outfit in self.load_shop_packet.outfits:
                shop_info["outfits"].append(dict(
                    outfit_id  = outfit.outfit_id,
                    look       = outfit.look,
                    background = outfit.background.value,
                ))

            for shaman_object in self.load_shop_packet.shaman_objects:
                shop_info["shaman_objects"].append(dict(
                    shaman_object_id = shaman_object.shaman_object_id,
                    num_colors       = shaman_object.num_colors,
                    is_new           = shaman_object.is_new,
                    info             = shaman_object.info.value,
                    cheese_cost      = shaman_object.cheese_cost,
                    fraise_cost      = shaman_object.fraise_cost,
                ))

                base_id, skin_id = caseus.game.shaman_object_id_parts(shaman_object.shaman_object_id)
                if (
                    base_id not in self.MAX_STATIC_SHAMAN_OBJECT_SKIN_ID or

                    skin_id > self.MAX_STATIC_SHAMAN_OBJECT_SKIN_ID[base_id]
                ):
                    tg.create_task(
                        self.download_specific_shaman_object(base_id, skin_id)
                    )

            for emoji in self.load_shop_packet.emojis:
                shop_info["emojis"].append(dict(
                    emoji_id    = emoji.emoji_id,
                    cheese_cost = emoji.cheese_cost,
                    fraise_cost = emoji.fraise_cost,
                    is_new      = emoji.is_new,
                ))

                tg.create_task(
                    self.download_emoji(emoji.emoji_id)
                )

            async def write_shop_info():
                await aiofiles.os.makedirs(self.shop_info_path.parent, exist_ok = True)
                async with aiofiles.open(self.shop_info_path, "w") as f:
                    await f.write(json.dumps(shop_info, separators=(",", ":")))

            tg.create_task(write_shop_info())

    @pak.packet_listener(caseus.serverbound.HandshakePacket, outgoing=True)
    async def request_languages(self, server, packet):
        await self.main.write_packet(caseus.serverbound.AvailableLanguagesPacket)

    @pak.packet_listener(caseus.clientbound.AvailableLanguagesPacket)
    async def on_available_languages(self, server, packet):
        self.language_codes = [language.code for language in packet.languages]

        if self.load_shop_packet is not None:
            self.main.close()

    @pak.packet_listener(caseus.clientbound.LoginSuccessPacket)
    async def on_login(self, server, packet):
        await self.main.write_packet(caseus.serverbound.LoadShopPacket)

    @pak.packet_listener(caseus.clientbound.ShopBaseTimestampPacket)
    async def set_base_timestamp(self, server, packet):
        self.base_timestamp = packet.timestamp

    @pak.packet_listener(caseus.clientbound.ShopSpecialOfferPacket)
    async def on_special_offer(self, server, packet):
        if packet.enable:
            self.special_offers[packet.item_id * (1 if packet.is_regular_item else -1)] = packet

        else:
            try:
                del self.special_offers[packet.item_id * (1 if packet.is_regular_item else -1)]

            except KeyError:
                pass

    @pak.packet_listener(caseus.clientbound.LoadShopPacket)
    async def on_load_shop(self, server, packet):
        assert len(packet.owned_items)          == 0
        assert len(packet.owned_outfit_looks)   == 0
        assert len(packet.owned_shaman_objects) == 0
        assert len(packet.owned_emoji_ids)      == 0

        self.load_shop_packet = packet

        if self.language_codes is not None:
            self.main.close()

if __name__ == "__main__":
    import config

    Dumper(
        config.shop_archive,

        secrets    = caseus.Secrets.load_from_leaker_swf(config.leaker_swf),
        start_room = config.start_room,

        **config.account,
    ).run()
