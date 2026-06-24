from apte import ApteSession

session = ApteSession()
session.register_default_plugins()


@session.test()
def test_with_print() -> None:
    print("VISIBLE_OUTPUT_FROM_TEST")  # noqa: T201 - testing visible output capture
    assert True
