import html
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import streamlit as st
import streamlit.components.v1 as components

from app.agent import answer
from app.llm import LLMClient
from app.maps import load_geojson, make_map, minutes_color
from app.personas import CATEGORY_LABELS, MINUTES, PERSONAS
from app.store import Store

INTENT_LABELS = {"reach": "동네별 도달 비율", "rank": "불편한 동네 순위", "nearest": "가까운 시설 찾기",
                 "simulate": "새 시설이 생기면", "compare_year": "과거와 비교"}
COLS = {"emd": "읍면동", "reach_pct": "도달 비율(%)", "gap_index": "취약 지수", "grid_n": "격자점 수", "reach_n": "도달 격자점",
        "persona_pop": "유형 인구 지표", "name": "시설명", "address": "주소", "dist_m": "보행거리(m)", "minutes": "걸리는 시간(분)",
        "reach_pct_from": "과거(%)", "reach_pct_to": "현재(%)", "diff": "변화(%p)", "lat": "위도", "lon": "경도", "gain_pct": "늘어나는 비율(%p)"}
SHORT = {"adult": "성인", "senior": "어르신", "senior_aid": "보행보조", "child_guardian": "아이 동반"}
SWITCH = {"adult": "일반 성인 걸음으로 하면?", "senior": "어르신 걸음으로 하면?",
          "senior_aid": "보행보조 걸음으로 하면?", "child_guardian": "아이랑 걸으면?"}

st.set_page_config(page_title="걸어올레 · 걸어 올래?", layout="wide", initial_sidebar_state="collapsed")

CSS = """<style>
#MainMenu,[data-testid="stToolbar"],[data-testid="stDecoration"],[data-testid="stSidebar"],[data-testid="stSidebarCollapsedControl"]{display:none!important}
header[data-testid="stHeader"]{background:transparent}
.block-container{padding-top:1.4rem;padding-bottom:2rem;max-width:1360px}
.brand{display:flex;align-items:center;gap:10px;font-size:18px;font-weight:700;color:#2C2C2A}
.brand .pun{font-size:15px;font-weight:400;color:#5F5E5A}
.hero{text-align:center;margin:7vh 0 6px}
.hero h1{font-size:44px;font-weight:500;letter-spacing:-.02em;margin:0;padding:0;color:#2C2C2A}
.hero p{font-size:16px;color:#5F5E5A;margin:12px 0 0}
.st-key-seg{align-items:center}
.st-key-follow{gap:6px}
.st-key-follow button{border-radius:999px;background:#FFFFFF;border:1px solid #D3D1C7;color:#444441;padding:2px 12px;min-height:34px}
.st-key-follow button p{font-size:13px}
.st-key-follow button:hover{border-color:#0F6E56;color:#085041;background:#FFFFFF}
[data-testid="stChatInput"]{border-radius:999px;background:#FFFFFF!important;border:1px solid #D3D1C7}
[data-testid="stChatInput"] div,[data-testid="stChatInput"] textarea{background:transparent!important}
[data-testid="stChatInputSubmitButton"]{background:#0F6E56!important;color:#FFFFFF!important;border-radius:999px}
[data-testid="stChatInput"] textarea{font-size:16px}
[data-testid="stExpander"] details{border:0;border-top:1px solid #ECEAE3;border-radius:0}
.bubble{margin-left:auto;width:fit-content;max-width:92%;background:#FFFFFF;border:1px solid #D3D1C7;border-radius:18px 18px 4px 18px;padding:10px 16px;font-size:14px;color:#444441}
.msg{background:#FFFFFF;border:1px solid #F2A07C;border-radius:16px;padding:14px 18px;font-size:15px;line-height:1.6;color:#2C2C2A;margin:4px 0}
iframe{border-radius:20px;border:1px solid #E3E1DA!important;background:#FFFFFF}
.ctx{font-size:13px;color:#5F5E5A;margin:14px 0 8px}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px;margin-bottom:14px}
.kpi{background:#FFFFFF;border:1px solid #E3E1DA;border-radius:16px;padding:16px 18px}
.kl{font-size:13px;color:#5F5E5A;line-height:1.4}
.kv{font-size:32px;font-weight:500;letter-spacing:-.02em;color:#04342C;line-height:1.25;margin-top:6px}
.ks{font-size:13px;color:#444441;margin-top:4px}
.side{background:#FFFFFF;border:1px solid #E3E1DA;border-radius:20px;padding:18px 20px;height:560px;box-sizing:border-box;overflow:auto}
.sh{font-size:15px;font-weight:600;color:#2C2C2A;margin-bottom:12px}
.sr{margin:0 0 12px}
.st{display:flex;justify-content:space-between;gap:10px;font-size:14px;color:#444441}
.st b{font-weight:600;color:#2C2C2A;white-space:nowrap}
.sb{height:6px;border-radius:999px;background:#F1EFE8;margin-top:5px;position:relative}
.sb i{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
.ins{display:flex;gap:12px;align-items:flex-start;background:#FFFFFF;border:1px solid #E3E1DA;border-radius:16px;padding:14px 18px;margin:14px 0 4px}
.ai{flex:none;background:#E1F5EE;color:#085041;border-radius:6px;padding:2px 8px;font-size:12px;font-weight:600;margin-top:2px}
.ib{font-size:15px;line-height:1.7;color:#2C2C2A}
.st-key-follow{flex-wrap:wrap;row-gap:8px}
.st-key-follow [data-testid="stElementContainer"]:has(.bubble){width:auto!important;flex:0 0 auto;max-width:100%}
.st-key-follow .bubble{margin:0 6px 0 0;width:auto;max-width:none;white-space:normal}
.foot{text-align:center;font-size:13px;color:#5F5E5A;margin-top:28px}
</style>"""
GLOW = """<style>.stApp{background:#FAFAF7 url("app/static/jeju_dots.svg") no-repeat center calc(100% - 16px) / min(1000px, 92vw) auto}</style>"""
PIN = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0F6E56" stroke-width="1.8" stroke-linecap="round" '
       'stroke-linejoin="round" aria-hidden="true"><path d="M12 21s-7-6.2-7-11.5a7 7 0 0 1 14 0C19 14.8 12 21 12 21z"/>'
       '<circle cx="12" cy="9.5" r="2.5"/></svg>')


def _code_version():
    return "".join(str(int((ROOT / "app" / f).stat().st_mtime)) for f in ("store.py", "analysis.py", "agent.py", "query.py"))


@st.cache_resource
def get_store(version: str = ""):
    return Store.load(ROOT)


@st.cache_resource
def get_geo():
    return load_geojson(ROOT)


@st.cache_resource
def get_llm():
    return LLMClient.from_env(ROOT)


store, geo, llm = get_store(_code_version()), get_geo(), get_llm()
ss = st.session_state
for k, v in {"prev": None, "ans": None, "asked": "", "persona": "adult"}.items():
    ss.setdefault(k, v)
if "sync_persona" in ss:
    ss.persona = ss.pop("sync_persona")


def ask(text, overrides=None):
    a = answer(text, store, llm, prev=None if overrides else ss.prev, overrides=overrides,
               default_persona=ss.persona or "adult")
    ss.ans, ss.asked = a, text or "직접 고른 조건"
    if a.table is not None or not a.message:
        ss.prev = a.query
    if a.query.category:
        ss.sync_persona = a.query.persona


def on_persona():
    if ss.ans is not None and ss.prev is not None and ss.persona:
        ask(SWITCH[ss.persona])


def reset():
    ss.prev, ss.ans, ss.asked = None, None, ""


def persona_control():
    st.segmented_control("누구 걸음으로 볼까요", list(PERSONAS), format_func=SHORT.get, key="persona",
                         on_change=on_persona, label_visibility="collapsed")


def direct_panel():
    with st.expander("직접 고르기"):
        c = st.columns(3)
        d_intent = c[0].selectbox("무엇을 볼까요", list(INTENT_LABELS), format_func=INTENT_LABELS.get)
        d_cat = c[1].selectbox("시설", list(CATEGORY_LABELS), format_func=CATEGORY_LABELS.get)
        d_min = c[2].select_slider("기준 시간(분)", MINUTES, value=15)
        d_emds = st.multiselect("읍면동", store.emds)
        d_year = st.selectbox("비교 연도", [2019, 2020, 2021, 2022, 2023, 2024]) if d_intent == "compare_year" else None
        if st.button("이 조건으로 보기", key="direct"):
            if d_intent in ("nearest", "simulate") and not d_emds:
                st.warning("가까운 시설 찾기와 새 시설 효과는 읍면동을 하나 골라야 합니다.")
            else:
                ask("", {"intent": d_intent, "category": d_cat, "persona": ss.persona or "adult", "minutes": d_min,
                         "emds": d_emds, "year_from": d_year, "top": 5})
                st.rerun()


def ctx_line(a) -> str:
    q = a.query
    where = [", ".join(q.emds)] if q.emds and q.intent != "rank" else ([q.sgg] if q.sgg else ["제주 전체"] if q.intent in ("rank", "reach") else [])
    return " · ".join([PERSONAS[q.persona].label, CATEGORY_LABELS[q.category]] + where)


def cards_html(a) -> str:
    items = "".join(
        f'<div class="kpi"><div class="kl">{html.escape(c["label"])}</div><div class="kv">{html.escape(str(c["value"]))}</div>'
        f'<div class="ks">{html.escape(c.get("sub") or "")}</div></div>' for c in a.cards)
    return f'<div class="ctx">{html.escape(ctx_line(a))}</div><div class="kpis">{items}</div>'


def side_html(side) -> str:
    rows = ""
    for r in side["rows"]:
        m = r.get("minutes")
        bar = ""
        if m is not None:
            w = 100 if m != m or m == float("inf") else max(4, min(m, 60) / 60 * 100)
            col = "#1A8F6B" if m == m and m != float("inf") and m <= 30 else "#E07A50"
            bar = f'<div class="sb"><i style="width:{w:.0f}%;background:{col}"></i></div>'
        rows += (f'<div class="sr"><div class="st"><span>{html.escape(str(r["label"]))}</span>'
                 f'<b>{html.escape(str(r["value"]))}</b></div>{bar}</div>')
    return f'<div class="side"><div class="sh">{html.escape(side["title"])}</div>{rows}</div>'


def insight_html(lines) -> str:
    body = "".join(f"<div>{html.escape(l)}</div>" for l in lines if l)
    return f'<div class="ins"><span class="ai">AI</span><div class="ib">{body}</div></div>'


st.markdown(CSS, unsafe_allow_html=True)
a = ss.ans

if a is None:
    st.markdown(GLOW, unsafe_allow_html=True)
    st.markdown(f'<div class="brand">{PIN}걸어올레<span class="pun">· 걸어 올래?</span></div>', unsafe_allow_html=True)
    _, mid, _ = st.columns([1, 3, 1])
    with mid:
        st.markdown('<div class="hero"><h1>우리 동네, 걸어서 어디까지?</h1>'
                    '<p>제주 43개 읍면동에서 약국·병원·도서관·정류장까지 걸어서 몇 분인지 물어보세요.</p></div>',
                    unsafe_allow_html=True)
        with st.container(key="seg"):
            persona_control()
        q = st.chat_input("예: 한림읍 어르신 걸어서 약국 갈 수 있는 비율", key="ask0")
        if q:
            with st.spinner("계산 중"):
                ask(q)
            st.rerun()
        direct_panel()
        st.markdown('<p class="foot">제주데이터허브 공공데이터 · OpenStreetMap 보행망 · 250m 격자 · '
                    + html.escape(f"LLM {llm.label} {llm.model}" if llm else "규칙 해석") + "</p>", unsafe_allow_html=True)
else:
    with st.container(horizontal=True, vertical_alignment="center", key="top"):
        st.button("← 처음으로", key="home", type="tertiary", on_click=reset)
        st.space("stretch")
        persona_control()
    follow = None
    with st.container(key="follow", horizontal=True, vertical_alignment="center"):
        st.markdown(f'<div class="bubble">{html.escape(ss.asked)}</div>', unsafe_allow_html=True)
        for i, f in enumerate(a.followups):
            if st.button(f, key=f"fu{i}"):
                follow = f
    if follow:
        with st.spinner("계산 중"):
            ask(follow)
        st.rerun()
    if a.message:
        st.markdown(f'<div class="msg">{html.escape(a.message)}</div>', unsafe_allow_html=True)
    if a.query.category and a.cards:
        st.markdown(cards_html(a), unsafe_allow_html=True)
    left, right = st.columns([8, 4], gap="medium")
    with left:
        if a.map_spec:
            components.html(make_map(geo, a, store.facilities).get_root().render(), height=560)
    with right:
        if a.side and a.side.get("rows"):
            st.markdown(side_html(a.side), unsafe_allow_html=True)
    if a.summary:
        lines = [ss.explain] if ss.get("explain_for") is a and ss.get("explain") else a.summary
        st.markdown(insight_html(lines), unsafe_allow_html=True)
        if llm and st.button("Qwen으로 풀어 쓰기", key="explain", type="tertiary"):
            with st.spinner("Qwen이 해설을 쓰는 중"):
                ss.explain = llm.explain({"질문": a.trace[0], "결과": a.summary}) or ""
                ss.explain_for = a
            st.rerun()
    if a.table is not None and len(a.table):
        st.dataframe(a.table, hide_index=True, use_container_width=True)
        st.download_button("표 내려받기 (CSV)", a.table.to_csv(index=False).encode("utf-8-sig"), "생활권진단.csv", "text/csv",
                           type="tertiary")
    if a.trace:
        with st.expander("이렇게 계산했어요"):
            st.markdown("\n".join(f"{i}. {t}" for i, t in enumerate(a.trace, 1)))
    if a.sources:
        with st.expander("데이터 출처와 한계"):
            st.markdown("\n".join(f"- {s}" for s in a.sources))
            st.caption("한계")
            st.markdown("\n".join(f"- {s}" for s in a.limits))
    if a.related:
        with st.expander("이어서 볼 만한 제주데이터허브 데이터"):
            st.markdown("\n".join(f"- {r['title']}: {r['why']}" for r in a.related))
    direct_panel()
    q = st.chat_input("이어서 물어보세요", key="ask1")
    if q:
        with st.spinner("계산 중"):
            ask(q)
        st.rerun()
