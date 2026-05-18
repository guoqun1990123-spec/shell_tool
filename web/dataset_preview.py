"""Datasets 结构预览：树形文本、统计摘要、异常检测。"""
from __future__ import annotations


# ── 数据准备 ────────────────────────────────────────────────────────────────

def _build_groups(card_state: list[dict]) -> list[dict]:
    """
    将 card_state 整理为分组列表，每组：
      { parent: row_dict, children: [row_dict, ...] }
    按 Class 排序，组内子行按插入顺序。
    """
    parents = sorted(
        [r for r in card_state if r.get("_parent_id") is None and int(r.get("Order") or 0) == 0],
        key=lambda r: int(r.get("Class") or 0),
    )
    groups = []
    for p in parents:
        children = [r for r in card_state if r.get("_parent_id") == p["_id"]]
        groups.append({"parent": p, "children": children})
    return groups


# ── 树形文本生成 ────────────────────────────────────────────────────────────

def generate_tree_text(card_state: list[dict]) -> str:
    """将 card_state 转为带缩进连接线的树形文本。"""
    groups = _build_groups(card_state)
    if not groups:
        return "（无变量行）"

    lines: list[str] = []
    for g in groups:
        p = g["parent"]
        var_type = p.get("_var_type", "手动输入")
        cls = int(p.get("Class") or 0)
        label = str(p.get("Label") or "（空）")
        lines.append(f"Class {cls}: {label}  [{var_type}]")

        children = g["children"]
        for i, c in enumerate(children):
            is_last = i == len(children) - 1
            prefix = "└── " if is_last else "├── "
            c_label = str(c.get("Label") or "（空）")
            c_aval = str(c.get("Aval") or "")
            c_order = int(c.get("Order") or 1)
            linked = "🔗" if c.get("_linked") else "○"
            lines.append(f"  {prefix}{c_label}  {linked}  Order={c_order}, Aval={c_aval}")

        lines.append("")  # 组间空行

    return "\n".join(lines).rstrip()


# ── 统计摘要 ────────────────────────────────────────────────────────────────

def generate_summary(card_state: list[dict]) -> dict:
    """
    返回统计字典：
      n_vars, n_continuous, n_categorical_sub, n_categorical_nosub,
      n_date, n_manual, n_children, n_unlinked_children
    """
    groups = _build_groups(card_state)

    counts = {
        "连续变量": 0,
        "分类变量-有子分类": 0,
        "分类变量-无子分类": 0,
        "日期变量": 0,
        "手动输入": 0,
    }
    n_children = 0
    n_unlinked = 0

    for g in groups:
        vt = g["parent"].get("_var_type", "手动输入")
        counts[vt] = counts.get(vt, 0) + 1
        for c in g["children"]:
            n_children += 1
            if not c.get("_linked"):
                n_unlinked += 1

    # 断链的 Order=1 独立行（_parent_id=None, Order=1）
    orphan_children = [
        r for r in card_state
        if r.get("_parent_id") is None and int(r.get("Order") or 0) == 1
    ]
    n_unlinked += len(orphan_children)
    n_children += len(orphan_children)

    return {
        "n_vars": len(groups),
        "n_continuous": counts.get("连续变量", 0),
        "n_categorical_sub": counts.get("分类变量-有子分类", 0),
        "n_categorical_nosub": counts.get("分类变量-无子分类", 0),
        "n_date": counts.get("日期变量", 0),
        "n_manual": counts.get("手动输入", 0),
        "n_children": n_children,
        "n_unlinked_children": n_unlinked,
    }


# ── 异常检测 ────────────────────────────────────────────────────────────────

def detect_anomalies(card_state: list[dict]) -> list[dict]:
    """
    返回异常列表，每项：{ level: "error"|"warning"|"info", message: str }
    """
    groups = _build_groups(card_state)
    anomalies: list[dict] = []

    # 1. 连续变量有子行吗？
    for g in groups:
        p = g["parent"]
        vt = p.get("_var_type", "手动输入")
        label = str(p.get("Label") or "")
        if vt == "连续变量" and len(g["children"]) == 0:
            anomalies.append({
                "level": "error",
                "message": f"连续变量「{label}」(Class={p.get('Class')}) 无子行，应展开统计量子行",
            })

    # 2. Class 不连续
    classes = [int(g["parent"].get("Class") or 0) for g in groups]
    if classes:
        for expected, actual in enumerate(sorted(classes), start=min(classes)):
            if expected != actual:
                missing = sorted(set(range(min(classes), max(classes) + 1)) - set(classes))
                anomalies.append({
                    "level": "warning",
                    "message": f"Class 不连续，缺少：{missing}",
                })
                break

    # 3. 子行 Aval 为空或可疑格式
    for g in groups:
        for c in g["children"]:
            aval = str(c.get("Aval") or "").strip()
            label = str(c.get("Label") or "")
            parent_label = str(g["parent"].get("Label") or "")
            if not aval:
                anomalies.append({
                    "level": "warning",
                    "message": f"子行「{label}」(父行：{parent_label}) Aval 为空",
                })

    return anomalies


# ── Streamlit 渲染 ──────────────────────────────────────────────────────────

def render_preview(ds_name: str, card_state: list[dict]) -> None:
    """渲染结构预览页（在调用方的 tab 容器内）。"""
    import streamlit as st
    from dataset_editor import state_key

    if not card_state:
        st.info("当前数据表为空，请先在「编辑」标签页添加变量行。")
        return

    tree_text = generate_tree_text(card_state)
    summary = generate_summary(card_state)
    anomalies = detect_anomalies(card_state)

    col_tree, col_right = st.columns([2, 1])

    # ── 左：树形结构 ──────────────────────────────────────────────────
    with col_tree:
        st.markdown("**变量树形结构**")
        st.code(tree_text, language=None)
        if st.button("📋 复制树形文本", key=f"copy_tree_{ds_name}"):
            st.session_state[f"_tree_copied_{ds_name}"] = True
        if st.session_state.get(f"_tree_copied_{ds_name}"):
            st.code(tree_text)  # 展示可手动复制的文本框
            if st.button("关闭", key=f"close_copy_{ds_name}"):
                del st.session_state[f"_tree_copied_{ds_name}"]
                st.rerun()

    # ── 右：统计摘要 + 异常 ───────────────────────────────────────────
    with col_right:
        st.markdown("**统计摘要**")

        r1c1, r1c2 = st.columns(2)
        r1c1.metric("变量总数", summary["n_vars"])
        r1c2.metric("子行总数", summary["n_children"])

        r2c1, r2c2 = st.columns(2)
        r2c1.metric("连续变量", summary["n_continuous"])
        r2c2.metric("分类(有子分类)", summary["n_categorical_sub"])

        r3c1, r3c2 = st.columns(2)
        r3c1.metric("分类(无子分类)", summary["n_categorical_nosub"])
        r3c2.metric("断链子行", summary["n_unlinked_children"],
                    delta=None if summary["n_unlinked_children"] == 0 else "⚠️",
                    delta_color="off")

        if summary["n_date"] or summary["n_manual"]:
            r4c1, r4c2 = st.columns(2)
            r4c1.metric("日期变量", summary["n_date"])
            r4c2.metric("手动输入", summary["n_manual"])

        st.divider()

        # ── 异常检测 ──────────────────────────────────────────────────
        if not anomalies:
            st.success("✅ 未发现结构异常")
        else:
            st.markdown("**⚠️ 异常检测**")
            for a in anomalies:
                level = a["level"]
                msg = a["message"]
                if level == "error":
                    st.error(f"🔴 {msg}")
                elif level == "warning":
                    st.warning(f"🟡 {msg}")
                else:
                    st.info(f"🔵 {msg}")
