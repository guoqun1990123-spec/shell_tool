# web/keys.py
"""跨模块 session_state key 注册表。

所有需要在多个模块间共享的 session_state key 在此统一定义，
各模块从此导入，避免字符串拼写错误和重复定义。
"""

# ── 标签页 ───────────────────────────────────────────────────────────────────
ACTIVE_TAB = "active_tab"           # "config" | "datasets" | "overview" | "templates"
TAB_SWITCH_REQ = "_tab_switch_req"  # int，每次标签切换 +1，触发 widget key 刷新

# ── Config 编辑器 ────────────────────────────────────────────────────────────
CFG_CARD_STATE = "config_card_state"
CFG_SELECTED_ID = "_cfg_selected_id"
CFG_FOCUS_ID = "_cfg_focus_id"

# ── 导航 ─────────────────────────────────────────────────────────────────────
NAV_FILTER = "section_nav_filter"       # {"section": str, "scroll_to": str|None}
NAV_SELECTED_ID = "section_nav_selected_id"

# ── 主选中项（Config / Datasets 标签共享）────────────────────────────────────
MAIN_SELECTED_ID = "selected_id"
