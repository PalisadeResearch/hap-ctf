import asyncio

from openai import AsyncOpenAI

client = AsyncOpenAI()


async def amain():
    models = await client.models.list()
    print(models.data[0].id)


def main():
    asyncio.run(amain())


if __name__ == "__main__":
    main()
