from pathlib import Path

from streamlit.testing.v1 import AppTest

UI = str(Path(__file__).resolve().parent.parent / "app" / "ui.py")
Q = "한림읍 어르신 걸어서 약국 갈 수 있는 비율"


def test_ui_question_flow():
    at = AppTest.from_file(UI, default_timeout=120).run()
    assert not at.exception
    at.chat_input(key="ask0").set_value(Q).run()
    assert not at.exception
    assert any("한림읍" in m.value for m in at.markdown)


def test_ui_followup_and_home():
    at = AppTest.from_file(UI, default_timeout=120).run()
    at.chat_input(key="ask0").set_value(Q).run()
    assert at.button(key="fu0")
    at.button(key="fu0").click().run()
    assert not at.exception
    at.button(key="home").click().run()
    assert not at.exception and at.chat_input(key="ask0")
