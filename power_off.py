import asyncio
from bleak import BleakClient

address = "BE:16:A3:00:13:A9"
MODEL_NBR_UUID = "00002a24-0000-1000-8000-00805f9b34fb"

async def main(address):
    async with BleakClient(address) as client:
        await client.write_gatt_char("0000fff3-0000-1000-8000-00805f9b34fb", bytearray([0x7e, 0x04, 0x04, 0x00, 0x00, 0x00, 0xff, 0x00, 0xef]))
        await asyncio.sleep(2)
asyncio.run(main(address))

