# scroll.py
import streamlit as st
import streamlit.components.v1 as components
import time


def request_scroll_to_top():
    """다음 rerun 시 페이지를 최상단으로 올리도록 요청"""
    st.session_state["_scroll_to_top"] = True
    st.session_state["_scroll_req_id"] = st.session_state.get("_scroll_req_id", 0) + 1
    st.session_state["_scroll_req_ts"] = time.time()


def apply_scroll_to_top_if_requested():
    """요청이 있으면 프론트에서 스크롤을 최상단으로 이동"""
    if not st.session_state.get("_scroll_to_top"):
        return

    st.session_state["_scroll_to_top"] = False
    req_id = st.session_state.get("_scroll_req_id", 0)

    components.html(
        f"""
        <!-- scroll_to_top_req:{req_id} -->
        <div id="__scroll_top_anchor__{req_id}" style="height:0;"></div>
        <script>
        (function () {{
          const REQ_ID = {req_id};

          function scrollToTop(el) {{
            try {{ el.scrollTop = 0; }} catch(e) {{}}
            try {{ el.scrollTo({{ top: 0, left: 0 }}); }} catch(e) {{}}
          }}

          function run() {{
            let w = window;
            try {{ if (window.parent) w = window.parent; }} catch(e) {{}}
            const d = w.document;

            try {{
              const a = d.getElementById("__scroll_top_anchor__" + REQ_ID);
              if (a) a.scrollIntoView();
            }} catch(e) {{}}

            try {{ w.scrollTo(0, 0); }} catch(e) {{}}
            try {{ d.documentElement.scrollTop = 0; }} catch(e) {{}}
            try {{ d.body.scrollTop = 0; }} catch(e) {{}}

            try {{
              d.querySelectorAll('*').forEach(el => {{
                const s = getComputedStyle(el);
                if ((s.overflowY === 'auto' || s.overflowY === 'scroll')
                    && el.scrollHeight > el.clientHeight) {{
                  scrollToTop(el);
                }}
              }});
            }} catch(e) {{}}

            [
              d.querySelector('[data-testid="stAppViewContainer"]'),
              d.querySelector('.block-container')
            ].filter(Boolean).forEach(scrollToTop);
          }}

          setTimeout(run, 50);
          setTimeout(run, 200);
          setTimeout(run, 500);
        }})();
        </script>
        """,
        height=0,
    )
