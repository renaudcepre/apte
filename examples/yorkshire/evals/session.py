"""Yorkshire Chatbot Evals - evaluate the fake Yorkshire expert chatbot.

Run with:
    apte eval examples.yorkshire.evals.session:session
    apte eval examples.yorkshire.evals.session:session -n 4
    apte eval examples.yorkshire.evals.session:session --tag safety
    apte eval examples.yorkshire.evals.session:session --last-failed
"""

from typing import Annotated

from apte import ApteSession, From
from apte.evals import EvalCase, ModelLabel
from apte.evals.suite import EvalSuite
from examples.yorkshire.app.chatbot import yorkshire_chatbot
from examples.yorkshire.evals.cases import (
    suite_evaluators,
    yorkshire_cases,
)

session = ApteSession(
    metadata={"version": "1.0", "type": "keyword-matching"},
)

yorkshire_suite = EvalSuite(
    "yorkshire_eval",
    model=ModelLabel(name="yorkshire-chatbot-v1", provider="local"),
)
session.add_suite(yorkshire_suite)


@yorkshire_suite.eval(evaluators=suite_evaluators)
def yorkshire_eval(case: Annotated[EvalCase, From(yorkshire_cases)]) -> str:
    return yorkshire_chatbot(case.inputs)
