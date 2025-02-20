import asyncio

from openai import AsyncOpenAI

client = AsyncOpenAI()


async def main():
    models = await client.models.list()
    print(models.data[0].id)


if __name__ == "__main__":
    asyncio.run(main())
