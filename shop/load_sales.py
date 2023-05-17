import pak
import caseus

# This is just a hotfix to fix a longstanding
# bug with the server that it does not tell the
# client to load all shaman object sprites that
# are displayed in the shop.

class LoadShamanObjectSalesProxy(caseus.Proxy):
    @pak.packet_listener(caseus.clientbound.ShopSpecialOfferPacket)
    async def on_special_offer(self, source, packet):
        if packet.is_regular_item:
            return

        await source.destination.write_packet(
            caseus.clientbound.LoadShamanObjectSpritesPacket,

            shaman_object_id_list = [packet.item_id],
        )

if __name__ == "__main__":
    LoadShamanObjectSalesProxy().run()
