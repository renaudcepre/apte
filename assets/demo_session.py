"""Apte demo - deliberately paced so you can watch the runner work.

Fixtures, tests and evals all `await asyncio.sleep(...)` to simulate real I/O:
opening a DB connection, an API handshake, an LLM call. Run with `-n` to watch
parallel execution stagger the results as workers finish.

    apte run  demo_session:tests -n 4
    apte eval demo_session:evals -n 4
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from apte import ApteSession, ApteSuite, ForEach, From, Use, fixture
from apte.evals import EvalCase, ModelLabel
from apte.evals.evaluators import contains_keywords, max_length, not_empty
from apte.evals.suite import EvalSuite

# =============================================================================
# Fixtures - the waits simulate real setup (connection, handshake)
# =============================================================================


@fixture()
async def db() -> AsyncGenerator[dict, None]:
    await asyncio.sleep(0.5)  # connecting to the database...
    yield {"cities": {"paris": "rain", "tokyo": "clear", "cairo": "sun"}}


@fixture()
async def weather_api(
    database: Annotated[dict, Use(db)],
) -> AsyncGenerator[dict, None]:
    await asyncio.sleep(0.3)  # API handshake...
    yield database["cities"]


# =============================================================================
# Tests - the waits simulate I/O work; run with -n to see them stagger
# =============================================================================

tests = ApteSession()
tests.bind(db)  # session-scoped: connect once, share everywhere

api = ApteSuite("WeatherAPI")
tests.add_suite(api)
api.bind(weather_api)


@api.test()
async def test_paris_is_rainy(cities: Annotated[dict, Use(weather_api)]) -> None:
    await asyncio.sleep(0.4)
    assert cities["paris"] == "rain"


@api.test()
async def test_tokyo_is_clear(cities: Annotated[dict, Use(weather_api)]) -> None:
    await asyncio.sleep(0.3)
    assert cities["tokyo"] == "clear"


@api.test()
async def test_known_cities(cities: Annotated[dict, Use(weather_api)]) -> None:
    await asyncio.sleep(0.5)
    assert len(cities) == 3  # noqa: PLR2004 - the weather_api fixture has 3 cities


@api.test()
async def test_unknown_city_missing(
    cities: Annotated[dict, Use(weather_api)],
) -> None:
    await asyncio.sleep(0.25)
    assert "atlantis" not in cities


# Typed parameterization - one case per city, all run concurrently under -n
CITIES = ForEach(["paris", "tokyo", "cairo"])


@api.test()
async def test_city_has_forecast(
    city: Annotated[str, From(CITIES)],
    cities: Annotated[dict, Use(weather_api)],
) -> None:
    await asyncio.sleep(0.35)
    assert cities[city]


# =============================================================================
# Evals - an eval is a test that returns a value, scored not asserted.
# The wait simulates LLM latency (~1s per call), which is honest for evals.
# =============================================================================

evals = ApteSession(metadata={"version": "1.0", "type": "demo"})

bot = EvalSuite(
    "weather_bot",
    model=ModelLabel(name="weather-bot-v1", provider="local"),
)
evals.add_suite(bot)

# Canned "model" answers - some hit the expected keywords, some miss (real evals fail).
ANSWERS = {
    "paris": "Expect rain and clouds over Paris today.",
    "tokyo": "Tokyo will be clear with blue sky all day.",
    "cairo": "Hot and sunny in Cairo, around 35 degrees.",
    "berlin": "I don't have data for that city.",  # misses keywords -> fails
    "advice": "Bring a jacket.",  # too vague -> fails keyword check
}

# Vary the simulated latency so cases finish out of order under -n.
DELAYS = {"paris": 0.7, "tokyo": 0.6, "cairo": 1.0, "berlin": 0.8, "advice": 0.9}

weather_cases = ForEach(
    [
        EvalCase(
            name="paris",
            inputs="Weather in Paris?",
            expected="rain",
            evaluators=[contains_keywords(keywords=["rain", "cloud"])],
        ),
        EvalCase(
            name="tokyo",
            inputs="Weather in Tokyo?",
            expected="clear",
            evaluators=[contains_keywords(keywords=["clear", "blue"])],
        ),
        EvalCase(
            name="cairo",
            inputs="Weather in Cairo?",
            expected="sunny",
            evaluators=[contains_keywords(keywords=["sunny", "hot"])],
        ),
        EvalCase(
            name="berlin",
            inputs="Weather in Berlin?",
            expected="rain or clouds",
            evaluators=[contains_keywords(keywords=["rain", "cloud", "clear"])],
        ),
        EvalCase(
            name="advice",
            inputs="What should I wear in London?",
            expected="rain gear, umbrella",
            evaluators=[contains_keywords(keywords=["umbrella", "rain"])],
        ),
    ]
)


@bot.eval(evaluators=[not_empty(), max_length(max_chars=120)])
async def weather_bot(case: Annotated[EvalCase, From(weather_cases)]) -> str:
    await asyncio.sleep(DELAYS[case.name])  # simulate the LLM call
    return ANSWERS[case.name]
