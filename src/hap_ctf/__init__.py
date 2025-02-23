import asyncio

import seccomp
from openai import AsyncOpenAI

client = AsyncOpenAI()


async def amain():
    models = await client.models.list()
    print(models.data[0].id)


def main():
    f = seccomp.SyscallFilter(seccomp.ALLOW)
    f.load()
    asyncio.run(amain())


if __name__ == "__main__":
    main()
