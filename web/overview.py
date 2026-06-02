# web/overview.py
"""项目总览页 —— 纯视图层，不修改数据。"""
from __future__ import annotations
import streamlit as st

from utils import sec_sort_key as _sec_sort_key
from keys import ACTIVE_TAB as _ACTIVE_TAB_KEY, NAV_FILTER as _NAV_FILTER_KEY, TAB_SWITCH_REQ


def compute_section_stats(card_state: list[dict]) -> list[dict]:
    """
    按 Section no 统计表/图/列表数量，返回有序列表：
    [{"section_no": "14.1", "section_title": "...", "表": 3, "图": 0, "列表": 0, "合计": 3}, ...]
    最后追加合计行。
    """
    stats: dict[str, dict] = {}
    for card in card_state:
        sec = str(card.get("Section no") or "").strip()
        cat = str(card.get("cat") or "").strip()
        if not sec:
            sec = "（无章节）"
        if sec not in stats:
            stats[sec] = {
                "section_no": sec,
                "section_title": str(card.get("Section title") or "").strip(),
                "表": 0, "图": 0, "列表": 0,
            }
        if cat in ("表", "图", "列表"):
            stats[sec][cat] += 1
        else:
            stats[sec].setdefault("其他", 0)
            stats[sec]["其他"] = stats[sec].get("其他", 0) + 1

    rows = sorted(
        stats.values(),
        key=lambda r: (1,) if r["section_no"] == "（无章节）" else (0, *_sec_sort_key(r["section_no"])),
    )
    for r in rows:
        r["合计"] = r["表"] + r["图"] + r["列表"] + r.get("其他", 0)

    total = {"section_no": "合计", "section_title": "", "表": 0, "图": 0, "列表": 0, "合计": 0}
    for r in rows:
        for k in ("表", "图", "列表", "合计"):
            total[k] += r[k]
    rows.append(total)
    return rows


def render_overview(
    card_state: list[dict],
    render_status: dict,
    protocol_name: str,
) -> None:
    """渲染项目总览页。"""
    st.subheader("📊 项目总览")

    # ── 基本信息 ──────────────────────────────────────────────────────────────
    total_cards = len(card_state)
    st.caption(f"方案简称：**{protocol_name or '（未填写）'}**　　TFL 总数：**{total_cards}**")

    st.divider()

    # ── 章节统计表 ──────────────────────────────────────────────────────────
    st.markdown("**章节统计**")
    rows = compute_section_stats(card_state)

    if not card_state:
        st.info("暂无 TFL 数据，请先加载或新建配置。")
    else:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["section_no", "section_title", "表", "图", "列表", "合计"])
        df = df.rename(columns={"section_no": "Section", "section_title": "标题"})
        st.dataframe(df, use_container_width=True, hide_index=True)

    st.divider()

    # ── 快速导航 ─────────────────────────────────────────────────────────────
    st.markdown("**快速导航**")
    nav_rows = [r for r in rows if r["section_no"] != "合计" and r["section_no"] != "（无章节）"]
    if nav_rows:
        cols = st.columns(min(len(nav_rows), 4))
        for i, row in enumerate(nav_rows):
            sec = row["section_no"]
            title = row["section_title"]
            count = row["合计"]
            label = f"{sec}"
            if title:
                label += f" {title[:6]}"
            label += f"({count})"
            with cols[i % 4]:
                if st.button(label, key=f"ov_nav_{sec}", use_container_width=True):
                    nav_filt = st.session_state.get(_NAV_FILTER_KEY, {})
                    nav_filt["section"] = sec
                    nav_filt["scroll_to"] = None
                    st.session_state[_NAV_FILTER_KEY] = nav_filt
                    st.session_state["section_nav_view_mode"] = "card"
                    st.session_state[_ACTIVE_TAB_KEY] = "config"
                    st.session_state[TAB_SWITCH_REQ] = st.session_state.get(TAB_SWITCH_REQ, 0) + 1
                    st.rerun()
    else:
        st.caption("无章节数据")

    st.divider()

    # ── 最近渲染状态 ─────────────────────────────────────────────────────────
    st.markdown("**最近渲染**")
    rs = render_status
    status = rs.get("status", "idle")
    if status == "success":
        elapsed = rs.get("elapsed") or 0
        size_kb = len(rs["output_bytes"]) // 1024 if rs.get("output_bytes") else 0
        st.success(f"✅ 上次渲染成功（耗时 {elapsed:.1f}s，{size_kb} KB）")
        if rs.get("output_bytes"):
            st.download_button(
                label="📥 下载 output.docx",
                data=rs["output_bytes"],
                file_name=rs.get("output_name") or "output.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key="ov_download",
            )
    elif status == "error":
        elapsed = rs.get("elapsed") or 0
        summary = rs.get("error_summary") or "未知错误"
        st.error(f"❌ 上次渲染失败（耗时 {elapsed:.1f}s）：{summary}")
    else:
        st.caption("尚未渲染")
