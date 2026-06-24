import asyncio

from apte import ApteSession

session = ApteSession()
session.register_default_plugins()


@session.test()
async def test_parallel_a() -> None:
    await asyncio.sleep(0.1)


@session.test()
async def test_parallel_b() -> None:
    await asyncio.sleep(0.1)


@session.test()
async def test_parallel_c() -> None:
    await asyncio.sleep(0.1)
