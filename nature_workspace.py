from __future__ import annotations

from io import BytesIO
from typing import Any, Callable, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import streamlit as st


NATURE_SKILL_COVERAGE = [
    ("nature-academic-search", "完整", "文献检索", "四源实时检索、去重、筛选与引用格式导出"),
    ("nature-citation", "部分", "引用与数据", "可规划引用支撑；尚未实现严格期刊集合的逐句自动配引"),
    ("nature-data", "部分", "引用与数据", "可生成声明与 FAIR 清单；尚未连接数据仓储提交接口"),
    ("nature-downloader", "未实现", "边界外", "按产品边界不批量下载或代理论文全文"),
    ("nature-experiment-log", "未实现", "待扩展", "尚无实验日志结构化记录与持久化"),
    ("nature-figure", "部分", "科研绘图", "已支持 Python 五类图与投稿格式导出；尚无 R、多面板编排和统计检验"),
    ("nature-literature-pipeline", "部分", "文献检索", "已覆盖检索与导出；尚无跨会话流水线和后台任务"),
    ("nature-paper-to-patent", "部分", "成果转化", "提供证据映射初筛；尚未生成完整分件 DOCX 专利包"),
    ("nature-paper2ppt", "完整", "PPT汇报", "支持论文 PDF 分析、图表提取和 PPTX 生成"),
    ("nature-polishing", "部分", "写作与润色", "支持学术润色与翻译；尚无 LaTeX 版式审校"),
    ("nature-proposal-writer", "未实现", "待扩展", "尚无基金申请书专用工作流"),
    ("nature-reader", "部分", "PDF精读", "支持 PDF 解析与精读报告；尚非逐块锚定的全文双语阅读器"),
    ("nature-ref-verifier", "部分", "文献检索", "可用 DOI/PMID 元数据核验；尚无逐条声明-引文一致性审计"),
    ("nature-response", "部分", "审稿与回复", "支持逐点回复草稿；尚无修订稿行号和附件联动"),
    ("nature-reviewer", "部分", "审稿与回复", "支持三审稿人模拟；仍是单次 LLM 分析而非完整证据审计"),
    ("nature-statistics", "未实现", "待扩展", "尚无统计方法选择、效应量和功效分析工作流"),
    ("nature-writing", "部分", "写作与润色", "支持章节起草与论证链；尚无整稿状态机和跨章节一致性检查"),
]


def read_table(uploaded_file: Any) -> pd.DataFrame:
    name = (getattr(uploaded_file, "name", "") or "").lower()
    uploaded_file.seek(0)
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(uploaded_file)
    return pd.read_csv(uploaded_file)


def demo_figure_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "time": [0, 1, 2, 3, 0, 1, 2, 3],
            "response": [1.0, 1.4, 2.2, 3.1, 1.1, 1.8, 2.9, 4.0],
            "group": ["Control"] * 4 + ["Treatment"] * 4,
            "marker_a": [0.18, 0.24, 0.41, 0.60, 0.20, 0.31, 0.55, 0.78],
        }
    )


def demo_csv_bytes() -> bytes:
    return demo_figure_data().to_csv(index=False).encode("utf-8-sig")


def _numeric(series: pd.Series, label: str) -> pd.Series:
    converted = pd.to_numeric(series, errors="coerce")
    if converted.notna().sum() == 0:
        raise ValueError(f"列“{label}”没有可绘制的数值。")
    return converted


def build_scientific_figure(
    data: pd.DataFrame,
    chart_type: str,
    x_column: str,
    y_column: Optional[str] = None,
    group_column: Optional[str] = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    width: float = 7.2,
    height: float = 4.8,
    dpi: int = 300,
) -> Tuple[bytes, bytes, bytes]:
    try:
        import matplotlib as mpl
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError(
            "科研绘图依赖未安装完成。请在 requirements.txt 中保留 matplotlib 并重新部署。"
        ) from exc

    if data.empty:
        raise ValueError("数据表为空。")
    if x_column not in data.columns:
        raise ValueError("请选择有效的 X 轴列。")
    if chart_type != "热图" and (not y_column or y_column not in data.columns):
        raise ValueError("请选择有效的 Y 轴列。")

    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8,
            "axes.spines.right": False,
            "axes.spines.top": False,
            "axes.linewidth": 0.8,
            "xtick.direction": "out",
            "ytick.direction": "out",
            "legend.frameon": False,
        }
    )
    palette = ["#3B6FB6", "#D97A45", "#4F9D7A", "#8B6BB1", "#C5A43D", "#64748B"]
    fig, ax = plt.subplots(figsize=(width, height), constrained_layout=True)
    frame = data.copy()
    groups = [("全部", frame)]
    if group_column and group_column in frame.columns:
        groups = list(frame.groupby(group_column, dropna=False, sort=False))

    if chart_type == "散点图":
        for index, (name, group) in enumerate(groups):
            ax.scatter(
                _numeric(group[x_column], x_column),
                _numeric(group[y_column], y_column),
                label=str(name), alpha=0.82, s=32, color=palette[index % len(palette)],
                edgecolor="white", linewidth=0.4,
            )
    elif chart_type == "折线图":
        for index, (name, group) in enumerate(groups):
            ordered = group.assign(_x=_numeric(group[x_column], x_column)).sort_values("_x")
            ax.plot(ordered["_x"], _numeric(ordered[y_column], y_column), marker="o",
                    linewidth=1.6, markersize=4, label=str(name), color=palette[index % len(palette)])
    elif chart_type == "柱状图":
        summary = frame.groupby([x_column] + ([group_column] if group_column else []), dropna=False)[y_column].mean().reset_index()
        x_values = list(dict.fromkeys(summary[x_column].astype(str)))
        group_values = list(dict.fromkeys(summary[group_column].astype(str))) if group_column else ["全部"]
        positions = np.arange(len(x_values))
        bar_width = 0.76 / max(1, len(group_values))
        for index, group_name in enumerate(group_values):
            subset = summary[summary[group_column].astype(str) == group_name] if group_column else summary
            value_map = dict(zip(subset[x_column].astype(str), pd.to_numeric(subset[y_column], errors="coerce")))
            values = [value_map.get(value, np.nan) for value in x_values]
            ax.bar(positions + (index - (len(group_values) - 1) / 2) * bar_width, values,
                   width=bar_width, label=group_name, color=palette[index % len(palette)])
        ax.set_xticks(positions, x_values, rotation=25, ha="right")
    elif chart_type in {"箱线图", "小提琴图"}:
        categories = list(dict.fromkeys(frame[x_column].astype(str)))
        values = [_numeric(frame.loc[frame[x_column].astype(str) == category, y_column], y_column).dropna() for category in categories]
        if chart_type == "箱线图":
            artists = ax.boxplot(values, labels=categories, patch_artist=True, widths=0.58,
                                 medianprops={"color": "#172033", "linewidth": 1.2})
            for index, box in enumerate(artists["boxes"]):
                box.set_facecolor(palette[index % len(palette)])
                box.set_alpha(0.78)
        else:
            artists = ax.violinplot(values, showmedians=True, showextrema=False)
            for index, body in enumerate(artists["bodies"]):
                body.set_facecolor(palette[index % len(palette)])
                body.set_alpha(0.78)
            ax.set_xticks(range(1, len(categories) + 1), categories, rotation=25, ha="right")
    elif chart_type == "热图":
        numeric = frame.select_dtypes(include="number")
        if numeric.shape[1] < 2:
            raise ValueError("热图至少需要两列数值数据。")
        matrix = numeric.corr()
        image = ax.imshow(matrix, cmap="RdBu_r", vmin=-1, vmax=1, aspect="auto")
        ax.set_xticks(range(len(matrix.columns)), matrix.columns, rotation=35, ha="right")
        ax.set_yticks(range(len(matrix.index)), matrix.index)
        fig.colorbar(image, ax=ax, fraction=0.045, pad=0.04, label="Pearson r")
        x_label = ""
        y_label = ""
    else:
        raise ValueError("不支持的图表类型。")

    if group_column and chart_type in {"散点图", "折线图", "柱状图"}:
        ax.legend(title=group_column, loc="best")
    ax.set_title(title, loc="left", fontweight="bold", pad=10)
    ax.set_xlabel(x_label or (x_column if chart_type != "热图" else ""))
    ax.set_ylabel(y_label or (y_column or ""))
    ax.grid(axis="y", color="#E2E8F0", linewidth=0.6, alpha=0.75)

    outputs: List[bytes] = []
    for file_format in ("png", "svg", "pdf"):
        buffer = BytesIO()
        fig.savefig(buffer, format=file_format, dpi=dpi if file_format == "png" else None,
                    bbox_inches="tight", facecolor="white")
        outputs.append(buffer.getvalue())
    plt.close(fig)
    return outputs[0], outputs[1], outputs[2]


def _render_text_tools(
    tools: List[Dict[str, Any]],
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
    call_llm: Callable[..., str],
    validate_llm_config: Callable[[str, str, str], bool],
    compact_text: Callable[[Any, int], str],
    render_tool_result: Callable[[str, str, str], None],
    key_prefix: str,
) -> None:
    if not tools:
        st.info("这个分区暂无可用工具。")
        return
    st.markdown("#### 选择一个明确任务")
    columns = st.columns(min(3, len(tools)))
    for index, tool in enumerate(tools):
        with columns[index % len(columns)]:
            st.markdown(f"**{tool['name']}**")
            st.caption(tool["help"])
    selected_name = st.selectbox("当前任务", [tool["name"] for tool in tools], key=f"{key_prefix}_tool")
    selected_tool = next(tool for tool in tools if tool["name"] == selected_name)
    user_text = st.text_area("输入材料", height=220, key=f"{key_prefix}_input",
                             placeholder="粘贴论文段落、结果要点、审稿意见或研究需求。")
    with st.expander("输出偏好（可选）", expanded=False):
        extra = st.text_area("目标期刊、语言、篇幅和其他要求", height=90, key=f"{key_prefix}_extra")
    if st.button(f"开始：{selected_name}", type="primary", use_container_width=True, key=f"{key_prefix}_run"):
        if not validate_llm_config(llm_api_key, llm_base_url, llm_model) or not user_text.strip():
            if not user_text.strip():
                st.warning("请先输入需要处理的材料。")
            return
        prompt = f"""你正在执行科研工作流：{selected_tool['name']}。

任务说明：
{selected_tool['instruction'].strip()}

输出偏好：{extra.strip() or '无'}

输入材料：
{compact_text(user_text, 16000)}

请使用中文说明；用户明确要求英文正文时，正文使用英文。不得编造数据、DOI、实验结果或期刊信息。"""
        try:
            with st.spinner(f"正在处理：{selected_name}..."):
                result = call_llm(llm_api_key=llm_api_key.strip(), llm_provider=llm_provider,
                                  llm_base_url=llm_base_url.strip(), llm_model=llm_model.strip(),
                                  system_prompt=selected_tool["system"], user_prompt=prompt, timeout=180)
        except Exception as exc:
            st.error(f"工具运行失败：{exc}")
            return
        render_tool_result("生成结果", result, f"{selected_name}.md")


def render_figure_workspace() -> None:
    st.markdown("#### 用数据直接生成投稿级图表")
    st.caption("Python 绘图 · 白底克制配色 · 可编辑 SVG/PDF · PNG 最高 600 DPI；无需 LLM Key。")
    with st.expander("绘图前先明确", expanded=False):
        st.markdown("1. 这张图要支撑哪一句核心结论？  2. X/Y/分组分别代表什么证据？  3. 样本量、误差和统计检验是否需要在图注中说明？")
    upload_col, sample_col = st.columns([3, 1])
    with upload_col:
        uploaded = st.file_uploader("上传整洁数据表", type=["csv", "xlsx", "xls"], key="figure_data")
    with sample_col:
        st.download_button("下载示例 CSV", demo_csv_bytes(), "figure_example.csv", "text/csv", use_container_width=True)
        use_demo = st.checkbox("直接试用示例数据", key="figure_use_demo")
    if uploaded is None and not use_demo:
        st.info("请上传 CSV 或 Excel，或勾选示例数据。建议每行一个观测、每列一个变量。")
        return
    try:
        data = demo_figure_data() if use_demo and uploaded is None else read_table(uploaded)
    except Exception as exc:
        st.error(f"读取数据失败：{exc}")
        return
    st.dataframe(data.head(30), use_container_width=True, hide_index=True)
    if data.empty or not list(data.columns):
        st.warning("数据表中没有可用列。")
        return
    chart_type = st.segmented_control("图表类型", ["散点图", "折线图", "柱状图", "箱线图", "小提琴图", "热图"], default="散点图")
    columns = list(map(str, data.columns))
    left, middle, right = st.columns(3)
    x_column = left.selectbox("X 轴 / 分类列", columns)
    y_options = ["（热图不需要）"] + columns
    y_selected = middle.selectbox("Y 轴数值列", y_options, index=1 if len(y_options) > 1 else 0)
    group_selected = right.selectbox("分组列（可选）", ["不分组"] + columns)
    y_column = None if y_selected == "（热图不需要）" else y_selected
    group_column = None if group_selected == "不分组" else group_selected
    title = st.text_input("图标题（建议写结论，不只写变量名）")
    label_left, label_right = st.columns(2)
    x_label = label_left.text_input("X 轴标签（可选）")
    y_label = label_right.text_input("Y 轴标签（可选）")
    with st.expander("尺寸与导出质量", expanded=False):
        c1, c2, c3 = st.columns(3)
        width = c1.number_input("宽度（英寸）", 3.0, 16.0, 7.2, 0.2)
        height = c2.number_input("高度（英寸）", 2.5, 12.0, 4.8, 0.2)
        dpi = c3.select_slider("PNG DPI", options=[300, 600], value=300)
    if st.button("生成科研图", type="primary", use_container_width=True):
        try:
            png, svg, pdf = build_scientific_figure(data, chart_type, x_column, y_column, group_column,
                                                     title, x_label, y_label, width, height, int(dpi))
        except Exception as exc:
            st.error(f"无法生成图表：{exc}")
            return
        st.session_state["nature_figure_outputs"] = (png, svg, pdf)
    outputs = st.session_state.get("nature_figure_outputs")
    if outputs:
        png, svg, pdf = outputs
        st.image(png, caption="科研图预览", use_container_width=True)
        d1, d2, d3 = st.columns(3)
        d1.download_button("下载 PNG", png, "scientific_figure.png", "image/png", use_container_width=True)
        d2.download_button("下载 SVG", svg, "scientific_figure.svg", "image/svg+xml", use_container_width=True)
        d3.download_button("下载 PDF", pdf, "scientific_figure.pdf", "application/pdf", use_container_width=True)


def render_nature_workspace(
    tool_configs: List[Dict[str, Any]],
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
    call_llm: Callable[..., str],
    validate_llm_config: Callable[[str, str, str], bool],
    compact_text: Callable[[Any, int], str],
    render_tool_result: Callable[[str, str, str], None],
) -> None:
    st.subheader("科研写作工作台")
    st.caption("按研究任务拆分工具，先选工作流，再提供材料；绘图功能可独立于 LLM 运行。")
    writing, review, evidence, figure, transform, coverage = st.tabs(
        ["写作与润色", "审稿与回复", "引用与数据", "科研绘图", "成果转化", "能力覆盖"]
    )
    category_map = {
        "writing": ["写作润色"],
        "review": ["投稿审稿"],
        "evidence": ["文献数据"],
        "transform": ["展示转化"],
    }
    with writing:
        _render_text_tools([t for t in tool_configs if t.get("category") in category_map["writing"]],
                           llm_api_key, llm_provider, llm_base_url, llm_model, call_llm,
                           validate_llm_config, compact_text, render_tool_result, "nature_writing")
    with review:
        _render_text_tools([t for t in tool_configs if t.get("category") in category_map["review"]],
                           llm_api_key, llm_provider, llm_base_url, llm_model, call_llm,
                           validate_llm_config, compact_text, render_tool_result, "nature_review")
    with evidence:
        _render_text_tools([t for t in tool_configs if t.get("category") in category_map["evidence"]],
                           llm_api_key, llm_provider, llm_base_url, llm_model, call_llm,
                           validate_llm_config, compact_text, render_tool_result, "nature_evidence")
    with figure:
        render_figure_workspace()
    with transform:
        tools = [t for t in tool_configs if t.get("category") in category_map["transform"] and t.get("name") != "科研绘图规划"]
        _render_text_tools(tools, llm_api_key, llm_provider, llm_base_url, llm_model, call_llm,
                           validate_llm_config, compact_text, render_tool_result, "nature_transform")
    with coverage:
        st.markdown("#### 上游 nature-skills 能力核对")
        st.caption("“部分”表示当前网页提供相关入口，但尚未实现上游 skill 的完整工作流、质量门槛或交付格式。")
        coverage_df = pd.DataFrame(NATURE_SKILL_COVERAGE, columns=["上游 Skill", "状态", "网页位置", "核对说明"])
        st.dataframe(coverage_df, use_container_width=True, hide_index=True)
        counts = coverage_df["状态"].value_counts()
        c1, c2, c3 = st.columns(3)
        c1.metric("完整", int(counts.get("完整", 0)))
        c2.metric("部分", int(counts.get("部分", 0)))
        c3.metric("未实现", int(counts.get("未实现", 0)))
