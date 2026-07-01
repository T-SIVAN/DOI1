from __future__ import annotations

import json
import base64
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from io import BytesIO
from typing import Any, Dict, List, Optional

import pandas as pd
import streamlit as st


OPENALEX_WORKS = "https://api.openalex.org/works"
DEFAULT_OPENALEX_EMAIL = "user@example.com"
DEFAULT_OPENALEX_API_KEY = ""
DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_MODEL = "gpt-4o-mini"
DEFAULT_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-lite"
GEMINI_FALLBACK_MODELS = [
    "gemini-2.5-flash-lite",
    "gemini-2.0-flash-lite",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-2.5-flash",
]
PDF_TEXT_MODE = "文本模式（默认，速度快）"
PDF_IMAGE_MODE = "图片模式（适合扫描版/图表多）"
PDF_HYBRID_MODE = "混合模式（先文字，失败或内容太少时转图片）"
PDF_PARSE_FAST = "快速模式"
PDF_PARSE_ENHANCED = "增强模式"
PDF_PARSE_STRUCTURED = "结构化模式"
CITATION_METADATA_ONLY = "仅元数据"
CITATION_CONTEXT_MODE = "尝试开放全文上下文"
PDF_HYBRID_MIN_TEXT_CHARS = 800
PDF_IMAGE_RENDER_SCALE = 1.6
PDF_IMAGE_JPEG_QUALITY = 72
PDF_IMAGE_MAX_BYTES = 1_200_000

OUTPUT_COLUMNS = [
    "文献标题",
    "年份",
    "DOI",
    "摘要",
    "OpenAlex ID",
    "引用数",
    "来源期刊",
    "作者",
    "证据等级",
    "引用上下文",
    "上下文来源",
    "PMID",
    "MeSH",
    "开放全文URL",
    "解析状态",
]

NATURE_SKILLS_SOURCE_URL = "https://github.com/Yuan1z0825/nature-skills"
NATURE_TOOL_CONFIGS = [
    {
        "category": "写作润色",
        "name": "Nature风格润色/翻译",
        "help": "将中文或英文论文段落改写为更接近 Nature / 高影响力期刊的学术表达。",
        "system": "你是熟悉 Nature 系列论文语言风格的资深学术英文编辑。",
        "instruction": """
请对输入文本进行学术润色、重构或中译英。输出：
1. 【润色后文本】：给出可直接粘贴到论文中的版本。
2. 【关键修改说明】：说明逻辑、术语、句式和语气的主要改动。
3. 【风险提示】：指出证据不足、表述过强或需要补充引用的位置。
""",
    },
    {
        "category": "写作润色",
        "name": "论文写作/章节起草",
        "help": "基于研究结果、笔记或要点起草摘要、引言、结果、讨论等章节。",
        "system": "你是擅长 Nature 风格论文论证结构设计的科研写作顾问。",
        "instruction": """
请根据输入材料起草或重建论文段落。输出：
1. 【建议标题/中心论点】。
2. 【章节正文草稿】：结构清晰，避免空泛。
3. 【论证链条】：用要点说明背景、缺口、方法、结果和意义如何连接。
4. 【还需补充的信息】：列出缺失数据或需要引用支撑的地方。
""",
    },
    {
        "category": "投稿审稿",
        "name": "预投稿审稿模拟",
        "help": "从审稿人视角评估创新性、技术可靠性、逻辑漏洞和补实验建议。",
        "system": "你是严格但建设性的高影响力期刊审稿人。",
        "instruction": """
请模拟预投稿审稿。输出：
1. 【总体判断】：接收潜力、主要短板和适合期刊层级。
2. 【Reviewer 1】：聚焦创新性和重要性。
3. 【Reviewer 2】：聚焦方法、统计和实验设计。
4. 【Reviewer 3】：聚焦表述、结构和可重复性。
5. 【优先修改清单】：按重要性排序。
""",
    },
    {
        "category": "文献数据",
        "name": "引用支撑与检索策略",
        "help": "把论文陈述拆成需要引用支撑的句子，并给出检索式、候选文献方向和 DOI 核验提示。",
        "system": "你是熟悉 Nature/CNS 文献引用规范和生物医药检索策略的文献顾问。",
        "instruction": """
请为输入文本规划引用支撑。当前网页不会实时联网检索，因此不要编造 DOI。输出：
1. 【需要引用支撑的陈述】：逐条列出。
2. 【推荐检索式】：给出 PubMed / CrossRef / Google Scholar 可用关键词。
3. 【候选文献类型】：说明应找原创研究、方法学论文还是综述。
4. 【已知候选 DOI】：只有在非常确定时才给出；不确定写“需核验”。
""",
    },
    {
        "category": "文献数据",
        "name": "数据可用性/FAIR声明",
        "help": "生成 Data Availability statement、数据仓储建议和 FAIR 检查清单。",
        "system": "你是熟悉高影响力期刊数据共享规范、FAIR 原则和科研数据仓储的编辑。",
        "instruction": """
请根据输入研究内容生成数据共享方案。输出：
1. 【Data Availability Statement】英文正式版本。
2. 【中文说明】：解释哪些数据需要公开、哪些可受限。
3. 【推荐仓储】：按数据类型推荐 GEO、SRA、PRIDE、Zenodo、Figshare 等。
4. 【FAIR 检查清单】：Findable、Accessible、Interoperable、Reusable。
""",
    },
    {
        "category": "投稿审稿",
        "name": "审稿意见回复",
        "help": "把 reviewer comments 转成逐点回复信，包含礼貌回应、修改动作和证据边界。",
        "system": "你是擅长撰写高质量 response to reviewers 的科研通讯作者。",
        "instruction": """
请为输入审稿意见起草逐点回复。输出：
1. 【总回复开头】。
2. 【逐点回复表】：Reviewer comment / Response / Manuscript change。
3. 【需要补实验或补分析的事项】。
4. 【语气风险】：指出过度承诺或回应不足的位置。
""",
    },
    {
        "category": "文献数据",
        "name": "论文精读/中英对照提纲",
        "help": "把论文片段整理成中文精读笔记、英文关键句和图文对应阅读提纲。",
        "system": "你是擅长论文精读、图文逻辑拆解和中英双语教学的科研导师。",
        "instruction": """
请对输入论文片段做精读。输出：
1. 【一句话结论】。
2. 【中文精读笔记】：背景、问题、方法、结果、意义。
3. 【英文关键句】：提炼 5-8 句关键英文表达。
4. 【图表阅读线索】：如果输入提到图表，请说明每张图应回答什么问题。
""",
    },
    {
        "category": "展示转化",
        "name": "论文汇报PPT大纲",
        "help": "生成组会/文献汇报用中文 PPT 结构、每页要点和讲稿提示。",
        "system": "你是擅长科研论文汇报和中文学术演示设计的导师。",
        "instruction": """
请把输入内容设计成文献汇报 PPT 大纲。输出：
1. 【汇报主线】。
2. 【逐页幻灯片大纲】：页码、标题、核心图/表、页面要点。
3. 【讲稿提示】：每页 1-3 句。
4. 【听众可能提问】：列出可能问题和回答思路。
""",
    },
    {
        "category": "展示转化",
        "name": "论文转专利初筛",
        "help": "从论文或技术方案中提取可专利化创新点、权利要求雏形和证据映射。",
        "system": "你是熟悉中国发明专利撰写和生物医药技术转化的专利工程师。",
        "instruction": """
请进行专利转化初筛。输出：
1. 【可专利化技术点】。
2. 【可能的独立权利要求雏形】。
3. 【从属权利要求方向】。
4. 【说明书证据映射】：每个技术特征对应输入材料中的依据。
5. 【新颖性/创造性风险】。
""",
    },
    {
        "category": "展示转化",
        "name": "科研绘图规划",
        "help": "为论文结果设计多面板 figure 逻辑、统计图类型和 Python/R 绘图建议。",
        "system": "你是擅长高影响力期刊科研图设计和数据可视化的 figure editor。",
        "instruction": """
请为输入结果设计投稿级科研图。输出：
1. 【图的核心结论】。
2. 【多面板设计】：Panel A/B/C... 每个面板展示什么。
3. 【推荐图型和统计标注】。
4. 【配色和版式建议】：保持克制、清晰、可发表。
5. 【需要的数据表结构】。
""",
    },
    {
        "category": "文献数据",
        "name": "多源文献检索方案",
        "help": "为一个研究问题生成 PubMed/CrossRef/arXiv/Scopus 检索词、筛选标准和导出字段。",
        "system": "你是熟悉多数据库文献检索、MeSH 词和引用管理的医学文献检索专家。",
        "instruction": """
请为输入研究问题设计文献检索方案。输出：
1. 【研究问题拆解】：PICO/关键词/同义词。
2. 【PubMed 检索式】：包含 MeSH 和自由词。
3. 【其他数据库检索式】：CrossRef、Google Scholar、Scopus 或 arXiv。
4. 【纳入排除标准】。
5. 【建议导出字段】：题名、摘要、DOI、PMID、年份、期刊等。
""",
    },
]


class ApiError(Exception):
    """Readable wrapper for recoverable HTTP/API failures."""


def normalize_identifier(value: str) -> str:
    return (value or "").strip().rstrip(".,;")


def normalize_doi(value: str) -> str:
    cleaned = normalize_identifier(value)
    cleaned = re.sub(r"^https?://(dx\.)?doi\.org/", "", cleaned, flags=re.I)
    return cleaned


def is_openalex_id(value: str) -> bool:
    return bool(re.match(r"^(https://openalex\.org/)?W\d+$", value.strip(), flags=re.I))


def clean_openalex_id(value: str) -> str:
    return value.rstrip("/").split("/")[-1]


def strip_markup(text: Any) -> str:
    if text is None:
        return ""
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(text))).strip()


def compact_text(text: Any, max_chars: int = 7000) -> str:
    cleaned = re.sub(r"\s+", " ", str(text or "")).strip()
    if len(cleaned) <= max_chars:
        return cleaned
    return cleaned[: max_chars - 20].rstrip() + " ... [truncated]"


def load_config_defaults(llm_provider: str) -> Dict[str, Any]:
    return {
        "llm_base_url": os.getenv(
            "OPENAI_BASE_URL" if llm_provider != "Google Gemini" else "GEMINI_BASE_URL",
            DEFAULT_GEMINI_BASE_URL if llm_provider == "Google Gemini" else DEFAULT_LLM_BASE_URL,
        ),
        "llm_model": os.getenv(
            "OPENAI_MODEL" if llm_provider != "Google Gemini" else "GEMINI_MODEL",
            DEFAULT_GEMINI_MODEL if llm_provider == "Google Gemini" else DEFAULT_LLM_MODEL,
        ),
        "openalex_api_key": os.getenv("OPENALEX_API_KEY", DEFAULT_OPENALEX_API_KEY),
        "openalex_email": os.getenv("OPENALEX_MAILTO", DEFAULT_OPENALEX_EMAIL),
    }


def validate_llm_config(llm_api_key: str, llm_base_url: str, llm_model: str) -> bool:
    if not llm_api_key.strip():
        st.warning("请先填写 LLM API Key。")
        return False
    if not llm_base_url.strip():
        st.warning("请填写 LLM Base URL。")
        return False
    if not llm_model.strip():
        st.warning("请填写 LLM 模型名称。")
        return False
    return True


def render_markdown_download(label: str, content: str, file_name: str) -> None:
    st.download_button(
        label=label,
        data=content.encode("utf-8"),
        file_name=file_name,
        mime="text/markdown",
        use_container_width=True,
    )


def render_tool_result(title: str, content: str, file_name: str) -> None:
    st.markdown(f"### {title}")
    st.markdown(content)
    render_markdown_download("下载 Markdown", content, file_name)


def render_quick_start_guide() -> None:
    st.info(
        "使用前先在左侧填写 LLM API Key。"
        "然后选择下方功能：PDF精读把一篇论文变成结构化读书报告；引用追踪用于输入 DOI/OpenAlex ID 并导出 Excel；"
        "写作工具用于润色、审稿回复、数据声明和汇报大纲。"
    )
    with st.expander("快速使用说明", expanded=True):
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(
                "**1. 配置 Key**\n\n"
                "- 左侧选择 `OpenAI 兼容` 或 `Google Gemini`\n"
                "- 填写自己的 `LLM API Key`\n"
                "- 不确定时可点 `测试连接`"
            )
        with col2:
            st.markdown(
                "**2. 选择功能**\n\n"
                "- `PDF精读`：生成结构化读书报告\n"
                "- `引用追踪`：输入 DOI 或 Paper ID\n"
                "- `写作工具`：粘贴文本并选择任务"
            )
        with col3:
            st.markdown(
                "**3. 下载结果**\n\n"
                "- PDF 精读可下载 Markdown\n"
                "- 引用追踪可下载 Excel\n"
                "- 云端不会保存你的上传文件"
            )


def apply_page_style() -> None:
    st.markdown(
        """
        <style>
        .block-container {
            max-width: 1180px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }
        h1 {
            letter-spacing: 0;
            margin-bottom: 0.15rem;
        }
        h2, h3 {
            letter-spacing: 0;
        }
        div[data-testid="stCaptionContainer"] {
            color: #64748b;
        }
        div[data-testid="stTabs"] button {
            font-weight: 600;
        }
        div[data-testid="stAlert"] {
            border-radius: 6px;
        }
        .stDownloadButton button,
        .stButton button {
            border-radius: 6px;
        }
        section[data-testid="stSidebar"] .block-container {
            padding-top: 1.25rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def request_json(
    url: str,
    *,
    params: Optional[Dict[str, Any]] = None,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 40,
    retries: int = 2,
) -> Dict[str, Any]:
    if params:
        query = urllib.parse.urlencode(params, doseq=True)
        url = f"{url}{'&' if '?' in url else '?'}{query}"

    request_headers = {
        "Accept": "application/json",
        "User-Agent": "streamlit-openalex-citation-analyzer/1.0",
    }
    if headers:
        request_headers.update(headers)

    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    for attempt in range(retries + 1):
        request = urllib.request.Request(url, data=body, headers=request_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8", errors="replace")
                return json.loads(raw) if raw.strip() else {}
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise ApiError(readable_http_error(exc.code, raw)) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            if attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise ApiError(str(exc)) from exc
    raise ApiError(f"请求失败：{url}")


def readable_http_error(status_code: int, raw_body: str) -> str:
    if status_code == 401:
        return (
            "LLM 服务认证失败（HTTP 401）。这通常表示 API Key 和 Base URL 不匹配，"
            "或 Key 已失效。请确认：OpenAI 官方 Key 使用 https://api.openai.com/v1；"
            "第三方/中转/学校平台 Key 必须填写对应平台提供的 Base URL；"
            "Gemini Key 请在侧边栏选择 Google Gemini 服务商。"
        )
    if status_code == 503:
        return (
            "LLM 服务暂不可用（HTTP 503）。这通常是模型当前高需求或服务临时拥堵，"
            "不是 PDF 或 Key 的问题。系统会自动重试并尝试备用模型；如果仍失败，"
            "请稍后再试或手动切换为 gemini-2.5-flash-lite / gemini-2.0-flash。"
        )
    if status_code == 429:
        return "LLM 服务限流（HTTP 429）。系统会自动重试；如果仍失败，请降低频率或稍后再试。"
    return f"HTTP {status_code}: {raw_body[:800]}"


def openalex_params(email: str, api_key: str, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    params: Dict[str, Any] = {}
    if email:
        params["mailto"] = email
    if api_key:
        params["api_key"] = api_key
    if extra:
        params.update(extra)
    return params


def restore_abstract(inverted_index: Any) -> str:
    if not isinstance(inverted_index, dict):
        return ""
    positioned: List[tuple[int, str]] = []
    for word, positions in inverted_index.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            try:
                positioned.append((int(pos), str(word)))
            except (TypeError, ValueError):
                continue
    positioned.sort(key=lambda item: item[0])
    return strip_markup(" ".join(word for _, word in positioned))


def clean_doi(value: Any) -> str:
    if not value:
        return ""
    return normalize_doi(str(value))


def source_name(work: Dict[str, Any]) -> str:
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    return source.get("display_name") or ""


def open_access_pdf_url(work: Dict[str, Any]) -> str:
    locations = []
    primary = work.get("primary_location")
    if isinstance(primary, dict):
        locations.append(primary)
    locations.extend(work.get("locations") or [])
    best = work.get("best_oa_location")
    if isinstance(best, dict):
        locations.insert(0, best)

    for location in locations:
        if not isinstance(location, dict):
            continue
        pdf_url = location.get("pdf_url")
        if pdf_url:
            return str(pdf_url)
        landing = location.get("landing_page_url")
        if landing and str(landing).lower().endswith(".pdf"):
            return str(landing)
    return ""


def authors_text(work: Dict[str, Any], max_authors: int = 8) -> str:
    names = []
    for authorship in work.get("authorships") or []:
        author = authorship.get("author") or {}
        name = author.get("display_name")
        if name:
            names.append(str(name))
    suffix = " et al." if len(names) > max_authors else ""
    return "; ".join(names[:max_authors]) + suffix


def resolve_target_work(identifier: str, email: str, openalex_api_key: str) -> Dict[str, Any]:
    identifier = normalize_identifier(identifier)
    if is_openalex_id(identifier):
        path_id = clean_openalex_id(identifier)
        url = f"{OPENALEX_WORKS}/{path_id}"
    else:
        doi = normalize_doi(identifier)
        url = f"{OPENALEX_WORKS}/{urllib.parse.quote(f'https://doi.org/{doi}', safe=':/')}"
    return request_json(url, params=openalex_params(email, openalex_api_key), retries=2)


def fetch_citing_works(
    openalex_id: str,
    email: str,
    openalex_api_key: str,
    limit: int,
    per_page: int,
    progress,
    status_box,
) -> List[Dict[str, Any]]:
    works: List[Dict[str, Any]] = []
    cursor = "*"
    per_page = min(max(per_page, 1), 200)
    total_hint = None

    while len(works) < limit:
        page_size = min(per_page, limit - len(works))
        params = openalex_params(
            email,
            openalex_api_key,
            {
                "filter": f"cites:{openalex_id}",
                "per-page": page_size,
                "cursor": cursor,
            },
        )
        page = request_json(OPENALEX_WORKS, params=params, retries=2)
        results = page.get("results") or []
        meta = page.get("meta") or {}
        total_hint = total_hint or meta.get("count")
        works.extend(results)

        progress.progress(min(len(works) / max(limit, 1), 0.35), text=f"正在拉取文献网络... 已获取 {len(works)} 篇")
        status_box.write(f"已获取 {len(works)} 篇引用文献，OpenAlex 估计总数：{total_hint or '未知'}")

        next_cursor = meta.get("next_cursor")
        if not results or not next_cursor:
            break
        cursor = next_cursor
        time.sleep(0.1)
    return works


def work_to_record(work: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "title": strip_markup(work.get("title") or work.get("display_name") or ""),
        "year": work.get("publication_year") or "",
        "doi": clean_doi(work.get("doi")),
        "abstract": restore_abstract(work.get("abstract_inverted_index")),
        "openalex_id": clean_openalex_id(str(work.get("id") or "")),
        "cited_by_count": work.get("cited_by_count") or 0,
        "source": source_name(work),
        "authors": authors_text(work),
        "oa_pdf_url": open_access_pdf_url(work),
        "pmid": "",
        "mesh": "",
        "evidence_level": "元数据",
        "citation_context": "",
        "context_source": "",
        "parse_status": "OpenAlex 元数据",
    }


def build_output_row(record: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "文献标题": record.get("title", ""),
        "年份": record.get("year", ""),
        "DOI": record.get("doi", ""),
        "摘要": record.get("abstract", ""),
        "OpenAlex ID": record.get("openalex_id", ""),
        "引用数": record.get("cited_by_count", 0),
        "来源期刊": record.get("source", ""),
        "作者": record.get("authors", ""),
        "证据等级": record.get("evidence_level", ""),
        "引用上下文": record.get("citation_context", ""),
        "上下文来源": record.get("context_source", ""),
        "PMID": record.get("pmid", ""),
        "MeSH": record.get("mesh", ""),
        "开放全文URL": record.get("oa_pdf_url", ""),
        "解析状态": record.get("parse_status", ""),
    }


def dataframe_to_excel_bytes(df: pd.DataFrame) -> bytes:
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Citation_Analysis")
        doi_columns = [column for column in ["文献标题", "年份", "DOI", "PMID", "OpenAlex ID", "证据等级"] if column in df.columns]
        df[doi_columns].to_excel(writer, index=False, sheet_name="DOI_List")
    buffer.seek(0)
    return buffer.getvalue()


def fetch_crossref_metadata(record: Dict[str, Any], email: str = "") -> Dict[str, str]:
    doi = record.get("doi") or ""
    title = record.get("title") or ""
    if not doi and not title:
        return {}

    try:
        if doi:
            url = f"https://api.crossref.org/works/{urllib.parse.quote(doi, safe='')}"
            response = request_json(url, params={"mailto": email} if email else None, retries=1)
            item = response.get("message") or {}
        else:
            response = request_json(
                "https://api.crossref.org/works",
                params={"query.title": title, "rows": 1, **({"mailto": email} if email else {})},
                retries=1,
            )
            items = ((response.get("message") or {}).get("items") or [])
            item = items[0] if items else {}
    except Exception:
        return {}

    if not item:
        return {}
    container = item.get("container-title") or []
    return {
        "doi": clean_doi(item.get("DOI")),
        "source": container[0] if container else "",
        "year": (((item.get("published-print") or item.get("published-online") or {}).get("date-parts") or [[None]])[0][0] or ""),
    }


def fetch_pubmed_metadata_by_doi(doi: str, email: str = "") -> Dict[str, str]:
    if not doi:
        return {}
    params = {
        "db": "pubmed",
        "term": f"{doi}[DOI]",
        "retmode": "json",
        "tool": "biomed-literature-workbench",
    }
    if email:
        params["email"] = email
    try:
        search = request_json("https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi", params=params, retries=1)
        ids = (((search.get("esearchresult") or {}).get("idlist")) or [])
        if not ids:
            return {}
        pmid = str(ids[0])
        summary = request_json(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi",
            params={"db": "pubmed", "id": pmid, "retmode": "json", "tool": "biomed-literature-workbench", **({"email": email} if email else {})},
            retries=1,
        )
        item = ((summary.get("result") or {}).get(pmid) or {})
        mesh_terms = []
        for term in item.get("meshheadinglist") or []:
            if isinstance(term, str):
                mesh_terms.append(term)
            elif isinstance(term, dict):
                mesh_terms.append(str(term.get("name") or term.get("term") or ""))
        return {"pmid": pmid, "mesh": "; ".join(term for term in mesh_terms if term)}
    except Exception:
        return {}


def post_pdf_to_grobid(pdf_bytes: bytes) -> str:
    base_url = os.getenv("GROBID_BASE_URL", "").rstrip("/")
    if not base_url:
        raise ApiError("未配置 GROBID_BASE_URL。")

    boundary = f"----biomed-workbench-{int(time.time() * 1000)}"
    body = b"".join(
        [
            f"--{boundary}\r\n".encode("utf-8"),
            b'Content-Disposition: form-data; name="input"; filename="paper.pdf"\r\n',
            b"Content-Type: application/pdf\r\n\r\n",
            pdf_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode("utf-8"),
        ]
    )
    request = urllib.request.Request(
        f"{base_url}/api/processFulltextDocument",
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Accept": "application/xml",
            "User-Agent": "biomed-literature-workbench/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception as exc:
        raise ApiError(f"GROBID 解析失败：{exc}") from exc


def tei_to_plain_text(tei_xml: str) -> str:
    text = re.sub(r"<ref\b[^>]*>", " ", tei_xml or "", flags=re.I)
    text = re.sub(r"</ref>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def enrich_citing_work(record: Dict[str, Any], email: str = "") -> Dict[str, Any]:
    enriched = dict(record)
    status = [enriched.get("parse_status") or "OpenAlex 元数据"]

    crossref = {}
    if not enriched.get("doi") or not enriched.get("source") or not enriched.get("year"):
        crossref = fetch_crossref_metadata(enriched, email)
    if crossref:
        if not enriched.get("doi") and crossref.get("doi"):
            enriched["doi"] = crossref["doi"]
        if not enriched.get("source") and crossref.get("source"):
            enriched["source"] = crossref["source"]
        if not enriched.get("year") and crossref.get("year"):
            enriched["year"] = crossref["year"]
        status.append("Crossref 补全")

    pubmed = fetch_pubmed_metadata_by_doi(enriched.get("doi") or "", email) if enriched.get("doi") else {}
    if pubmed:
        enriched["pmid"] = pubmed.get("pmid", "")
        enriched["mesh"] = pubmed.get("mesh", "")
        status.append("PubMed 补全")

    enriched["parse_status"] = "；".join(status)
    return enriched


def download_open_pdf_bytes(pdf_url: str, max_bytes: int = 8_000_000) -> bytes:
    if not pdf_url:
        raise ApiError("无开放全文 PDF URL。")
    request = urllib.request.Request(pdf_url, headers={"User-Agent": "biomed-literature-workbench/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            content_type = response.headers.get("Content-Type", "")
            raw = response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ApiError("开放全文 PDF 过大，已跳过。")
        if "pdf" not in content_type.lower() and not pdf_url.lower().endswith(".pdf"):
            raise ApiError("开放全文链接不是 PDF，已跳过。")
    except Exception as exc:
        if isinstance(exc, ApiError):
            raise
        raise ApiError(f"开放全文下载失败：{exc}") from exc
    return raw


def download_open_pdf_text(pdf_url: str, max_bytes: int = 8_000_000) -> str:
    raw = download_open_pdf_bytes(pdf_url, max_bytes)

    try:
        return pypdf_extract_full_text(raw, max_pages=40)
    except Exception as exc:
        raise ApiError(f"开放全文文本解析失败：{exc}") from exc


def extract_context_window(text: str, needle: str, window: int = 900) -> str:
    if not text or not needle:
        return ""
    index = text.lower().find(needle.lower())
    if index < 0:
        return ""
    start = max(0, index - window)
    end = min(len(text), index + len(needle) + window)
    return normalize_pdf_text(text[start:end], 2200)


def extract_citation_context(target_doi: str, citing_record: Dict[str, Any]) -> Dict[str, str]:
    pdf_url = citing_record.get("oa_pdf_url") or ""
    if not pdf_url:
        return {
            "evidence_level": "摘要/元数据",
            "citation_context": "",
            "context_source": "无开放全文",
            "parse_status": "无开放全文 PDF URL",
        }

    try:
        pdf_bytes = download_open_pdf_bytes(pdf_url)
        parser_source = "pypdf"
        try:
            tei_xml = post_pdf_to_grobid(pdf_bytes)
            full_text = tei_to_plain_text(tei_xml)
            parser_source = "GROBID TEI"
            if not full_text:
                raise ApiError("GROBID 未返回可读文本。")
        except Exception:
            full_text = pypdf_extract_full_text(pdf_bytes, max_pages=40)
    except Exception as exc:
        return {
            "evidence_level": "摘要/元数据",
            "citation_context": "",
            "context_source": "开放全文解析失败",
            "parse_status": str(exc),
        }

    context = extract_context_window(full_text, normalize_doi(target_doi))
    source = "开放全文 DOI 匹配"
    if not context:
        context = extract_context_window(full_text, target_doi)
    if not context:
        source = f"开放全文可读但未定位目标 DOI（{parser_source}）"
    else:
        source = f"{source}（{parser_source}）"

    return {
        "evidence_level": "全文上下文" if context else "开放全文未定位",
        "citation_context": context,
        "context_source": source,
        "parse_status": "开放全文 PDF 解析成功" if context else "开放全文解析成功，但未匹配目标 DOI",
    }


def selected_pdf_page_indexes(page_count: int) -> List[int]:
    """Use the same high-signal page window for text and image reading."""
    if page_count <= 0:
        raise ApiError("PDF 中没有可读取页面。")
    selected = list(range(min(3, page_count)))
    tail_start = max(0, page_count - 2)
    selected.extend(range(tail_start, page_count))
    return sorted(set(selected))


def normalize_pdf_text(text: str, max_chars: int = 24000) -> str:
    return compact_text(re.sub(r"\s+", " ", text or "").strip(), max_chars)


def extract_sections_from_text(text: str) -> Dict[str, str]:
    section_patterns = {
        "title_abstract": r"(?is)^(.{0,5000}?)(?=\bintroduction\b|\bbackground\b|\bmaterials and methods\b|\bmethods\b|\bresults\b)",
        "introduction": r"(?is)\b(?:introduction|background)\b(.{0,6000}?)(?=\bmaterials and methods\b|\bmethods\b|\bresults\b|\bdiscussion\b)",
        "methods": r"(?is)\b(?:materials and methods|methods|methodology|experimental procedures)\b(.{0,7000}?)(?=\bresults\b|\bdiscussion\b|\bconclusion\b|\breferences\b)",
        "results": r"(?is)\bresults\b(.{0,8000}?)(?=\bdiscussion\b|\bconclusion\b|\bmaterials and methods\b|\bmethods\b|\breferences\b)",
        "discussion_conclusion": r"(?is)\b(?:discussion|conclusion|conclusions)\b(.{0,7000}?)(?=\breferences\b|\backnowledg)",
        "references": r"(?is)\breferences\b(.{0,5000})$",
    }
    sections: Dict[str, str] = {}
    for name, pattern in section_patterns.items():
        match = re.search(pattern, text or "")
        if match:
            sections[name] = normalize_pdf_text(match.group(0), 5000)
    return sections


def extract_figure_table_clues(text: str, max_items: int = 18) -> List[str]:
    clues: List[str] = []
    for match in re.finditer(r"(?is)\b(?:fig(?:ure)?\.?\s*\d+[a-z]?|table\s*\d+[a-z]?)\b.{0,700}", text or ""):
        clue = normalize_pdf_text(match.group(0), 900)
        if clue and clue not in clues:
            clues.append(clue)
        if len(clues) >= max_items:
            break
    return clues


def pypdf_extract_full_text(pdf_bytes: bytes, max_pages: int = 40) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ApiError("当前环境缺少 pypdf，请先安装：pip install pypdf") from exc

    try:
        reader = PdfReader(BytesIO(pdf_bytes))
        page_texts: List[str] = []
        for page_index, page in enumerate(reader.pages[:max_pages], start=1):
            text = page.extract_text() or ""
            if text.strip():
                page_texts.append(f"[Page {page_index}]\n{text}")
        cleaned = "\n\n".join(page_texts).strip()
    except Exception as exc:
        raise ApiError(f"pypdf 全文解析失败：{exc}") from exc

    if not cleaned:
        raise ApiError("pypdf 未能从 PDF 中提取到文本。")
    return cleaned


def extract_pdf_with_pymupdf4llm(pdf_bytes: bytes) -> Dict[str, Any]:
    try:
        import pymupdf4llm
    except ImportError as exc:
        raise ApiError("PyMuPDF4LLM 未安装，已降级为 pypdf 结构抽取。") from exc

    temp_path = None
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = temp_file.name
        markdown = pymupdf4llm.to_markdown(temp_path)
        if isinstance(markdown, list):
            markdown = "\n\n".join(str(item) for item in markdown)
        markdown = str(markdown or "").strip()
        if not markdown:
            raise ApiError("PyMuPDF4LLM 未返回有效 Markdown。")
        sections = extract_sections_from_text(markdown)
        return {
            "mode": PDF_PARSE_ENHANCED,
            "parser": "PyMuPDF4LLM",
            "markdown": compact_text(markdown, 28000),
            "sections": sections,
            "figure_table_clues": extract_figure_table_clues(markdown),
            "evidence_level": "增强解析",
            "status": "PyMuPDF4LLM Markdown 解析成功",
        }
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def extract_pdf_with_docling(pdf_bytes: bytes) -> Dict[str, Any]:
    try:
        from docling.document_converter import DocumentConverter
    except ImportError as exc:
        raise ApiError("Docling 未安装，已降级为启发式结构抽取。") from exc

    temp_path = None
    try:
        import tempfile

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            temp_file.write(pdf_bytes)
            temp_path = temp_file.name
        result = DocumentConverter().convert(temp_path)
        document = result.document
        markdown = document.export_to_markdown()
        sections = extract_sections_from_text(markdown)
        return {
            "mode": PDF_PARSE_STRUCTURED,
            "parser": "Docling",
            "markdown": compact_text(markdown, 32000),
            "sections": sections,
            "figure_table_clues": extract_figure_table_clues(markdown),
            "evidence_level": "结构化解析",
            "status": "Docling 结构化解析成功",
        }
    finally:
        if temp_path:
            try:
                os.unlink(temp_path)
            except OSError:
                pass


def build_pdf_content_from_text(text: str, mode: str, parser: str, status: str) -> Dict[str, Any]:
    sections = extract_sections_from_text(text)
    return {
        "mode": mode,
        "parser": parser,
        "markdown": compact_text(text, 28000),
        "sections": sections,
        "figure_table_clues": extract_figure_table_clues(text),
        "evidence_level": "全文结构推断" if sections else "核心页文本",
        "status": status,
    }


def extract_pdf_content(pdf_bytes: bytes, mode: str) -> Dict[str, Any]:
    if mode == PDF_PARSE_FAST:
        text = extract_core_pdf_text(pdf_bytes)
        return build_pdf_content_from_text(text, mode, "pdfplumber", "快速模式：核心页文本解析成功")

    if mode == PDF_PARSE_ENHANCED:
        try:
            return extract_pdf_with_pymupdf4llm(pdf_bytes)
        except ApiError as exc:
            fallback_text = pypdf_extract_full_text(pdf_bytes)
            content = build_pdf_content_from_text(
                fallback_text,
                mode,
                "pypdf fallback",
                f"增强模式降级：{exc}",
            )
            content["evidence_level"] = "增强降级"
            return content

    if mode == PDF_PARSE_STRUCTURED:
        try:
            return extract_pdf_with_docling(pdf_bytes)
        except ApiError as exc:
            fallback_text = pypdf_extract_full_text(pdf_bytes)
            content = build_pdf_content_from_text(
                fallback_text,
                mode,
                "heuristic sections",
                f"结构化模式降级：{exc}",
            )
            content["evidence_level"] = "结构化降级"
            return content

    raise ApiError(f"未知 PDF 解析模式：{mode}")


def pdf_content_to_prompt_text(content: Dict[str, Any], max_chars: int = 18000) -> str:
    sections = content.get("sections") or {}
    parts = [
        f"解析器：{content.get('parser', '')}",
        f"证据等级：{content.get('evidence_level', '')}",
        f"解析状态：{content.get('status', '')}",
    ]
    if sections:
        parts.append("结构化片段：")
        for name, section_text in sections.items():
            parts.append(f"\n## {name}\n{section_text}")
    else:
        parts.append("正文片段：")
        parts.append(str(content.get("markdown") or ""))

    clues = content.get("figure_table_clues") or []
    if clues:
        parts.append("\n图表/表格线索：")
        for clue in clues[:12]:
            parts.append(f"- {clue}")
    return compact_text("\n".join(parts), max_chars)


def run_analysis(
    identifier: str,
    openalex_api_key: str,
    email: str,
    max_papers: int,
    citation_mode: str,
    progress,
    title_log,
) -> pd.DataFrame:
    progress.progress(0.03, text="正在解析目标文献...")
    target = resolve_target_work(identifier, email, openalex_api_key)
    openalex_id = clean_openalex_id(target.get("id") or "")
    target_doi = clean_doi(target.get("doi")) or normalize_doi(identifier)
    if not openalex_id:
        raise ApiError("OpenAlex 未能解析目标文献 ID。")

    progress.progress(0.1, text="正在拉取文献网络...")
    citing_works = fetch_citing_works(openalex_id, email, openalex_api_key, max_papers, 200, progress, title_log)

    rows: List[Dict[str, Any]] = []
    total = len(citing_works)
    for idx, work in enumerate(citing_works, start=1):
        record = work_to_record(work)
        title_log.write(f"正在整理第 {idx}/{total} 篇文献：{record['title']}")
        progress.progress(0.35 + 0.6 * idx / max(total, 1), text=f"正在整理第 {idx}/{total} 篇文献...")
        record = enrich_citing_work(record, email)
        if citation_mode == CITATION_CONTEXT_MODE:
            title_log.write(f"正在尝试开放全文上下文：{record['title']}")
            context = extract_citation_context(target_doi, record)
            record.update(context)
        rows.append(build_output_row(record))

    df = pd.DataFrame(rows, columns=OUTPUT_COLUMNS)
    if not df.empty:
        df = df.sort_values(["年份", "引用数"], ascending=[False, False]).reset_index(drop=True)
    progress.progress(1.0, text="分析完成")
    return df


def extract_core_pdf_text(pdf_bytes: bytes) -> str:
    """Extract only the high-signal pages: first 3 pages and last 2 pages."""
    try:
        import pdfplumber
    except ImportError as exc:
        raise ApiError("当前环境缺少 pdfplumber，请先安装：pip install pdfplumber") from exc

    try:
        with pdfplumber.open(BytesIO(pdf_bytes)) as pdf:
            page_count = len(pdf.pages)
            selected = selected_pdf_page_indexes(page_count)

            page_texts: List[str] = []
            for page_index in selected:
                text = pdf.pages[page_index].extract_text() or ""
                if text.strip():
                    page_texts.append(f"[Page {page_index + 1}]\n{text}")
    except Exception as exc:
        if isinstance(exc, ApiError):
            raise
        raise ApiError(f"PDF 解析失败，请确认文件未损坏且不是纯扫描图片：{exc}") from exc

    cleaned = re.sub(r"\s+", " ", "\n".join(page_texts)).strip()
    if not cleaned:
        raise ApiError("未能从 PDF 中提取到文本。若这是扫描版 PDF，请先 OCR。")
    return compact_text(cleaned, 12000)


def compress_pil_image_to_jpeg(image: Any) -> bytes:
    """Compress a rendered page while keeping it readable for vision models."""
    try:
        from PIL import Image
    except ImportError as exc:
        raise ApiError("当前环境缺少 Pillow，请先安装：pip install pillow") from exc

    if image.mode not in {"RGB", "L"}:
        image = image.convert("RGB")
    elif image.mode == "L":
        image = image.convert("RGB")

    quality = PDF_IMAGE_JPEG_QUALITY
    while True:
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=quality, optimize=True)
        data = buffer.getvalue()
        if len(data) <= PDF_IMAGE_MAX_BYTES or quality <= 45:
            return data
        quality -= 8


def render_core_pdf_pages_as_images(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """Render first 3 and last 2 PDF pages into compact JPEG images."""
    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise ApiError("当前环境缺少 pypdfium2，请先安装：pip install pypdfium2 pillow") from exc

    try:
        pdf = pdfium.PdfDocument(pdf_bytes)
        selected = selected_pdf_page_indexes(len(pdf))
        images: List[Dict[str, Any]] = []

        for page_index in selected:
            page = pdf[page_index]
            bitmap = page.render(scale=PDF_IMAGE_RENDER_SCALE)
            pil_image = bitmap.to_pil()
            image_bytes = compress_pil_image_to_jpeg(pil_image)
            images.append(
                {
                    "page": page_index + 1,
                    "mime_type": "image/jpeg",
                    "data": image_bytes,
                }
            )
        return images
    except Exception as exc:
        if isinstance(exc, ApiError):
            raise
        raise ApiError(f"PDF 图片渲染失败，请确认文件未损坏：{exc}") from exc


def call_llm(
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 120,
) -> str:
    if llm_provider == "Google Gemini":
        return call_gemini_llm(
            llm_api_key=llm_api_key,
            llm_base_url=llm_base_url,
            llm_model=llm_model,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            timeout=timeout,
        )
    return call_openai_compatible_llm(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        timeout=timeout,
    )


def call_openai_compatible_llm(
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 120,
) -> str:
    payload = {
        "model": llm_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.2,
    }
    base_url = llm_base_url.rstrip("/")
    response = request_json(
        f"{base_url}/chat/completions",
        method="POST",
        payload=payload,
        headers={"Authorization": f"Bearer {llm_api_key}"},
        timeout=timeout,
        retries=1,
    )
    return (((response.get("choices") or [{}])[0].get("message") or {}).get("content") or "").strip()


def call_gemini_llm(
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    system_prompt: str,
    user_prompt: str,
    timeout: int = 120,
) -> str:
    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": [{"text": user_prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }
    return execute_gemini_payload(llm_api_key, llm_base_url, llm_model, payload, timeout)


def call_gemini_llm_with_images(
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    system_prompt: str,
    user_prompt: str,
    images: List[Dict[str, Any]],
    timeout: int = 180,
) -> str:
    if not images:
        raise ApiError("图片模式未生成可发送给 Gemini 的页面图片。")

    parts: List[Dict[str, Any]] = [{"text": user_prompt}]
    for image in images:
        parts.append({"text": f"下面是 PDF 第 {image['page']} 页的页面截图："})
        parts.append(
            {
                "inline_data": {
                    "mime_type": image["mime_type"],
                    "data": base64.b64encode(image["data"]).decode("ascii"),
                }
            }
        )

    payload = {
        "systemInstruction": {
            "parts": [{"text": system_prompt}],
        },
        "contents": [
            {
                "role": "user",
                "parts": parts,
            }
        ],
        "generationConfig": {
            "temperature": 0.2,
        },
    }
    return execute_gemini_payload(llm_api_key, llm_base_url, llm_model, payload, timeout)


def execute_gemini_payload(
    llm_api_key: str,
    llm_base_url: str,
    llm_model: str,
    payload: Dict[str, Any],
    timeout: int,
) -> str:
    base_url = llm_base_url.rstrip("/")
    model_candidates = gemini_model_candidates(llm_model)
    last_error = ""
    for model in model_candidates:
        endpoint = f"{base_url}/models/{urllib.parse.quote(model, safe='')}:generateContent"
        for attempt in range(4):
            try:
                response = request_json(
                    endpoint,
                    params={"key": llm_api_key},
                    method="POST",
                    payload=payload,
                    timeout=timeout,
                    retries=0,
                )
                candidates = response.get("candidates") or []
                if not candidates:
                    raise ApiError(f"Gemini 未返回候选结果：{str(response)[:500]}")
                parts = (((candidates[0].get("content") or {}).get("parts")) or [])
                text = "\n".join(str(part.get("text", "")) for part in parts if isinstance(part, dict))
                if text.strip():
                    return text.strip()
                raise ApiError(f"Gemini 返回了空文本：{str(response)[:500]}")
            except ApiError as exc:
                last_error = str(exc)
                if should_retry_llm_error(last_error) and attempt < 3:
                    time.sleep(min(20, 2 ** attempt * 2))
                    continue
                break
    raise ApiError(f"Gemini 多次重试和备用模型切换后仍失败：{last_error}")


def gemini_model_candidates(selected_model: str) -> List[str]:
    models = [selected_model.strip()] if selected_model.strip() else []
    for model in GEMINI_FALLBACK_MODELS:
        if model not in models:
            models.append(model)
    return models


def should_retry_llm_error(message: str) -> bool:
    retry_markers = ["HTTP 503", "HTTP 429", "暂不可用", "限流", "UNAVAILABLE", "high demand"]
    return any(marker in message for marker in retry_markers)


def analyze_pdf_deep_reading(
    pdf_text: str,
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
) -> str:
    prompt = f"""
你是一个资深的生物医药方向研究员。请阅读以下提供的学术论文文本片段，并严格按照以下结构输出中文报告：

【主要内容】：用一段话总结文章做了什么。

【核心创新点】：列出 1-3 条该文献区别于过往研究的创新（如新的组装技术、新的酶突变位点等）。

【核心数据与实验结果】：提取支撑其结论的最重要的数据。

【期刊评估 (IF)】：请根据文本中出现的期刊名称，评估并给出该期刊近期的近似影响因子 (Impact Factor)。如果文本中找不到期刊名，请根据文章水平给出一个合理的期刊等级预测（如一区/二区）。

论文文本片段如下：
{pdf_text}
""".strip()
    return call_llm(
        llm_api_key=llm_api_key,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt="你是一个严谨、克制、重视证据边界的生物医药方向研究员。",
        user_prompt=prompt,
    )


def analyze_pdf_content_deep_reading(
    content: Dict[str, Any],
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
) -> str:
    prompt_text = pdf_content_to_prompt_text(content)
    prompt = f"""
你是一个资深的生物医药方向研究员。请阅读以下结构化论文内容，并严格按照以下结构输出中文报告：

【主要内容】：用一段话总结文章做了什么。

【核心创新点】：列出 1-3 条该文献区别于过往研究的创新（如新的组装技术、新的酶突变位点等）。

【核心数据与实验结果】：提取支撑其结论的最重要数据；请优先使用 results、figure/table clues 和 methods 中的证据。

【实验方法与技术路线】：尽量提取关键实验方法、测序/富集/扩增/酶工程/组装策略、样本和分析流程。

【期刊评估 (IF)】：根据文本中的期刊名称给出近期近似影响因子；找不到期刊名时给出合理等级预测并说明不确定性。

论文结构化内容如下：
{prompt_text}
""".strip()
    return call_llm(
        llm_api_key=llm_api_key,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt="你是一个严谨、克制、重视证据边界的生物医药方向研究员。",
        user_prompt=prompt,
    )


def analyze_pdf_deep_reading_with_images(
    images: List[Dict[str, Any]],
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
) -> str:
    if llm_provider != "Google Gemini":
        raise ApiError("当前图片识别模式请切换到 Google Gemini。")

    page_list = "、".join(str(image["page"]) for image in images)
    prompt = f"""
你是一个资深的生物医药方向研究员。请直接阅读下面提供的 PDF 页面截图，页面范围为第 {page_list} 页。

这些截图来自论文的高信号页面（前 3 页和最后 2 页）。请尽量从标题、摘要、图表、结论、方法和参考信息中提取证据，并严格按照以下结构输出中文报告：

【主要内容】：用一段话总结文章做了什么。

【核心创新点】：列出 1-3 条该文献区别于过往研究的创新（如新的组装技术、新的酶突变位点等）。

【核心数据与实验结果】：提取支撑其结论的最重要的数据；如果图表中有关键数值、样本量、效率、准确率或酶学指标，请优先列出。

【期刊评估 (IF)】：请根据截图中出现的期刊名称，评估并给出该期刊近期的近似影响因子 (Impact Factor)。如果截图中找不到期刊名，请根据文章水平给出一个合理的期刊等级预测（如一区/二区）。

请忽略页眉页脚、水印、版权声明等非生物学相关冗余信息。
""".strip()
    return call_gemini_llm_with_images(
        llm_api_key=llm_api_key,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt="你是一个严谨、克制、重视证据边界的生物医药方向研究员，并擅长从论文页面截图中读取图表和方法信息。",
        user_prompt=prompt,
        images=images,
    )


def simplify_markdown_response(markdown: str, max_chars: int = 9000) -> str:
    lines = []
    skip_prefixes = (
        "好的",
        "当然",
        "作为",
        "我将",
        "下面",
        "以下",
        "请注意",
    )
    for raw_line in str(markdown or "").splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            if lines and lines[-1] != "":
                lines.append("")
            continue
        stripped = line.strip()
        if not lines and any(stripped.startswith(prefix) for prefix in skip_prefixes):
            continue
        lines.append(line)
    cleaned = "\n".join(lines).strip()
    return compact_text(cleaned, max_chars)


def repair_markdown_tables(markdown: str) -> str:
    lines = str(markdown or "").splitlines()
    repaired: List[str] = []
    table_header_pattern = re.compile(r"^\s*\|\s*年份\s*\|.+\|\s*$")
    separator_pattern = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?\s*$")

    for index, line in enumerate(lines):
        repaired.append(line)
        if table_header_pattern.match(line):
            next_line = lines[index + 1] if index + 1 < len(lines) else ""
            if not separator_pattern.match(next_line):
                column_count = max(2, line.count("|") - 1)
                repaired.append("|" + "|".join(["---"] * column_count) + "|")
    return "\n".join(repaired)


def polish_breakthrough_report(markdown: str) -> str:
    cleaned = simplify_markdown_response(markdown, 12000)
    cleaned = repair_markdown_tables(cleaned)
    if "｜" in cleaned:
        cleaned = cleaned.replace("｜", "|")
    return cleaned.strip()


def analyze_field_breakthroughs(
    step1_report: str,
    pdf_text: str,
    llm_api_key: str,
    llm_provider: str,
    llm_base_url: str,
    llm_model: str,
) -> str:
    prompt = f"""
请基于下面的文献剖析报告和论文片段，生成一份“近 10 年领域突破追踪”。

输出必须简洁、专业、无寒暄。不要写“好的”“作为专家”等开场白。

请严格按以下 Markdown 结构输出：

# <用 8-18 个字概括细分方向>突破脉络

**方向概述：** <用不超过 60 字说明该领域过去 10 年的主要演进主线。>

**核心关键词：** 关键词1；关键词2；关键词3；关键词4；关键词5

## 关键里程碑文献

必须输出标准 Markdown 表格，并且第二行必须是分隔行：

| 年份 | 里程碑/技术突破 | 代表文献 | DOI | 关键意义 |
|---|---|---|---|---|
| 2016 | 示例 | 示例 | 未检出 | 示例 |

表格要求：
- 按年份升序。
- 优先列 6-12 条最关键文献，不要堆砌过多条目。
- 每格内容控制在 60 字以内。
- DOI 无法确定时写“未检出”，严禁编造 DOI。
- 代表文献尽量写“第一作者 et al., 年份, 期刊”。

## 使用提醒
- DOI 需用 CrossRef/PubMed/出版社页面二次核验。

文献剖析报告：
{step1_report}

论文片段：
{compact_text(pdf_text, 6000)}
""".strip()
    result = call_llm(
        llm_api_key=llm_api_key,
        llm_provider=llm_provider,
        llm_base_url=llm_base_url,
        llm_model=llm_model,
        system_prompt="你是一个熟悉生物医药技术史、酶工程、分子检测和基因组技术的专家。",
        user_prompt=prompt,
    )
    return polish_breakthrough_report(result)


def render_pdf_deep_reading_tab(llm_api_key: str, llm_provider: str, llm_base_url: str, llm_model: str) -> None:
    st.subheader("PDF精读")
    st.caption("上传一篇论文，自动提炼研究亮点、实验路线与领域突破脉络。")

    with st.expander("使用说明", expanded=False):
        st.markdown(
            "- 快速模式读取核心页；增强模式优先使用 PyMuPDF4LLM，缺失时降级为 pypdf 全文抽取。\n"
            "- 结构化模式优先使用 Docling，缺失时降级为章节启发式抽取。\n"
            "- 图片读取适合扫描版或图表较多的 PDF，需要选择 Google Gemini。"
        )

    parse_mode = st.segmented_control(
        "解析模式",
        [PDF_PARSE_FAST, PDF_PARSE_ENHANCED, PDF_PARSE_STRUCTURED],
        default=PDF_PARSE_ENHANCED,
    )
    read_mode = st.radio(
        "PDF 读取方式",
        [PDF_TEXT_MODE, PDF_IMAGE_MODE, PDF_HYBRID_MODE],
        horizontal=True,
        help="图片模式适合扫描版、图表较多或文字提取乱码的 PDF；503 仍属于模型服务拥堵，需要重试或切换模型。",
    )
    if read_mode == PDF_IMAGE_MODE:
        st.caption("图片模式会把核心页面截图发送给 Gemini，能读取扫描版和图表，但更耗模型资源。")
    elif read_mode == PDF_HYBRID_MODE:
        st.caption("混合模式会先尝试文本提取；若文本为空、过短或解析失败，会自动转为 Gemini 图片识别。")

    uploaded_pdf = st.file_uploader("上传 PDF 文献", type=["pdf"])
    start_pdf = st.button("开始智能分析", type="primary", use_container_width=True)

    if start_pdf:
        if not validate_llm_config(llm_api_key, llm_base_url, llm_model):
            return
        if uploaded_pdf is None:
            st.warning("请先上传一个 PDF 文件。")
            return
        if read_mode in {PDF_IMAGE_MODE, PDF_HYBRID_MODE} and llm_provider != "Google Gemini":
            st.warning("当前图片识别模式请切换到 Google Gemini。OpenAI 兼容接口的视觉输入格式不统一，首版暂不启用。")
            return

        try:
            pdf_bytes = uploaded_pdf.getvalue()
            pdf_text = ""
            pdf_content: Dict[str, Any] = {}
            page_images: List[Dict[str, Any]] = []
            analysis_source = f"{parse_mode} / 文本读取"

            if read_mode == PDF_TEXT_MODE:
                with st.spinner("正在解析 PDF 内容..."):
                    pdf_content = extract_pdf_content(pdf_bytes, parse_mode)
                    pdf_text = str(pdf_content.get("markdown") or "")
                st.caption(f"解析器：{pdf_content.get('parser')}；证据等级：{pdf_content.get('evidence_level')}；状态：{pdf_content.get('status')}")
                with st.expander("已提取内容预览", expanded=False):
                    st.text_area("内容预览", pdf_content_to_prompt_text(pdf_content, 9000), height=260)
            elif read_mode == PDF_IMAGE_MODE:
                analysis_source = "图片模式"
                with st.spinner("正在将 PDF 核心页面渲染为图片..."):
                    page_images = render_core_pdf_pages_as_images(pdf_bytes)
                st.caption(f"已渲染 {len(page_images)} 张核心页面图片，准备交给 Gemini 识别。")
            else:
                with st.spinner("正在优先尝试解析 PDF 内容..."):
                    try:
                        pdf_content = extract_pdf_content(pdf_bytes, parse_mode)
                        pdf_text = str(pdf_content.get("markdown") or "")
                    except Exception as exc:
                        st.info(f"文本解析不可用，自动切换图片模式：{exc}")
                        pdf_text = ""
                if len(pdf_text) >= PDF_HYBRID_MIN_TEXT_CHARS:
                    analysis_source = f"混合模式：已使用 {parse_mode}"
                    st.caption(f"解析器：{pdf_content.get('parser')}；证据等级：{pdf_content.get('evidence_level')}；状态：{pdf_content.get('status')}")
                    with st.expander("已提取内容预览", expanded=False):
                        st.text_area("内容预览", pdf_content_to_prompt_text(pdf_content, 9000), height=260)
                else:
                    analysis_source = "混合模式：已自动转为图片识别"
                    if pdf_text:
                        st.info(f"文本内容较少（{len(pdf_text)} 字符），自动切换图片模式。")
                    with st.spinner("正在将 PDF 核心页面渲染为图片..."):
                        page_images = render_core_pdf_pages_as_images(pdf_bytes)
                    st.caption(f"已渲染 {len(page_images)} 张核心页面图片，准备交给 Gemini 识别。")

            with st.spinner("正在生成文献剖析..."):
                if page_images:
                    step1_report = analyze_pdf_deep_reading_with_images(
                        page_images,
                        llm_api_key.strip(),
                        llm_provider,
                        llm_base_url.strip(),
                        llm_model.strip(),
                    )
                elif pdf_content:
                    step1_report = analyze_pdf_content_deep_reading(
                        pdf_content,
                        llm_api_key.strip(),
                        llm_provider,
                        llm_base_url.strip(),
                        llm_model.strip(),
                    )
                else:
                    step1_report = analyze_pdf_deep_reading(
                        pdf_text,
                        llm_api_key.strip(),
                        llm_provider,
                        llm_base_url.strip(),
                        llm_model.strip(),
                    )

            with st.spinner("正在深挖近10年领域背景..."):
                step2_report = analyze_field_breakthroughs(
                    step1_report,
                    pdf_text,
                    llm_api_key.strip(),
                    llm_provider,
                    llm_base_url.strip(),
                    llm_model.strip(),
                )
        except Exception as exc:
            st.error(f"智能分析失败：{exc}")
            return

        st.success(f"智能分析完成。实际读取方式：{analysis_source}")
        full_report = f"# 单篇文献深度剖析\n\n{step1_report}\n\n# 领域突破表\n\n{step2_report}\n"
        render_markdown_download("下载完整精读报告", full_report, "pdf_deep_reading_report.md")

        analysis_tab, breakthrough_tab = st.tabs(["单篇剖析", "领域突破"])
        with analysis_tab:
            render_tool_result("单篇文献深度剖析", step1_report, "single_paper_analysis.md")
        with breakthrough_tab:
            render_tool_result("领域突破表", step2_report, "field_breakthroughs.md")


def render_citation_tracking_tab(openalex_api_key: str, email: str, max_papers: int) -> None:
    st.subheader("引用追踪")
    st.caption("输入 DOI 或 OpenAlex Paper ID，抓取引用该文献的论文并导出 Excel。")
    with st.expander("使用说明", expanded=False):
        st.markdown(
            "- 数据源为 OpenAlex，不需要 Semantic Scholar API Key。\n"
            "- 结果为客观元数据：标题、年份、DOI、摘要、引用数、期刊和作者。\n"
            "- 开放全文上下文模式只处理 OA PDF，不绕过付费墙；没有全文时会降级为元数据证据。"
        )
    identifier = st.text_input("请输入目标文献 DOI 或 OpenAlex Paper ID", placeholder="例如：10.1038/s41586-020-2649-2 或 W3035965352")
    citation_mode = st.segmented_control(
        "分析模式",
        [CITATION_METADATA_ONLY, CITATION_CONTEXT_MODE],
        default=CITATION_METADATA_ONLY,
    )
    if citation_mode == CITATION_CONTEXT_MODE:
        st.caption("实验功能：会尝试下载开放获取 PDF 并定位目标 DOI 附近上下文，速度较慢且覆盖率有限。")
    start = st.button("开始分析", type="primary", use_container_width=True)

    if start:
        if not identifier.strip():
            st.warning("请输入目标文献的 DOI 或 Paper ID。")
            return

        progress = st.progress(0, text="准备开始...")
        with st.expander("实时分析日志", expanded=True):
            title_log = st.empty()

        try:
            with st.spinner("系统正在分析，请稍候..."):
                df = run_analysis(
                    identifier=identifier.strip(),
                    openalex_api_key=openalex_api_key.strip(),
                    email=email.strip(),
                    max_papers=int(max_papers),
                    citation_mode=citation_mode,
                    progress=progress,
                    title_log=title_log,
                )
        except Exception as exc:
            st.error(f"分析失败：{exc}")
            return

        st.subheader("结果概览")
        doi_count = int(df["DOI"].astype(bool).sum()) if not df.empty and "DOI" in df else 0
        years = pd.to_numeric(df["年份"], errors="coerce").dropna() if not df.empty and "年份" in df else pd.Series(dtype=float)
        year_range = "无" if years.empty else f"{int(years.min())}-{int(years.max())}"
        metric_cols = st.columns(3)
        metric_cols[0].metric("文献数", len(df))
        metric_cols[1].metric("含 DOI", doi_count)
        metric_cols[2].metric("年份范围", year_range)

        st.subheader("文献列表")
        st.dataframe(df, use_container_width=True, hide_index=True)

        excel_bytes = dataframe_to_excel_bytes(df)
        st.download_button(
            label="下载 Excel 分析报告",
            data=excel_bytes,
            file_name="citation_analysis_report.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )


def render_nature_toolbox_tab(llm_api_key: str, llm_provider: str, llm_base_url: str, llm_model: str) -> None:
    st.subheader("写作工具")
    st.caption("面向论文写作、投稿审稿、文献数据和成果转化的 LLM 工具箱。")
    with st.expander("使用说明", expanded=False):
        st.markdown(
            f"- 能力设计参考开源项目 [{NATURE_SKILLS_SOURCE_URL}]({NATURE_SKILLS_SOURCE_URL})。\n"
            "- 当前版本聚焦文本生成和分析，不会自动联网核验 DOI。\n"
            "- 涉及 DOI、影响因子、期刊分区等信息时，请以数据库核验结果为准。"
        )

    categories = ["写作润色", "投稿审稿", "文献数据", "展示转化"]
    selected_category = st.segmented_control("工具类别", categories, default=categories[0])
    filtered_tools = [tool for tool in NATURE_TOOL_CONFIGS if tool.get("category") == selected_category]
    tool_names = [tool["name"] for tool in filtered_tools]
    selected_name = st.selectbox("选择功能", tool_names)
    selected_tool = next(tool for tool in filtered_tools if tool["name"] == selected_name)
    st.caption(selected_tool["help"])

    user_text = st.text_area(
        "粘贴论文文本、实验结果、审稿意见或你的需求",
        height=260,
        placeholder="例如：粘贴摘要/引言段落、结果要点、reviewer comments、数据类型说明、研究问题等。",
    )
    extra_requirements = st.text_area(
        "补充要求（可选）",
        height=110,
        placeholder="例如：目标期刊、字数、中文/英文、领域背景、希望强调的创新点、需要避免的表述等。",
    )

    if st.button("运行 Nature 工具", type="primary", use_container_width=True):
        if not validate_llm_config(llm_api_key, llm_base_url, llm_model):
            return
        if not user_text.strip():
            st.warning("请先粘贴需要处理的文本或需求。")
            return

        prompt = f"""
你正在执行一个科研写作/文献处理工具：{selected_tool["name"]}。

任务说明：
{selected_tool["instruction"].strip()}

用户补充要求：
{extra_requirements.strip() or "无"}

输入材料：
{compact_text(user_text, 16000)}

请使用中文输出；如果用户明确要求英文正文，则正文部分用英文，解释部分仍可用中文。
请保持专业、克制，不要编造不存在的数据、DOI、实验结果或期刊信息。
""".strip()

        try:
            with st.spinner(f"正在运行：{selected_tool['name']}..."):
                result = call_llm(
                    llm_api_key=llm_api_key.strip(),
                    llm_provider=llm_provider,
                    llm_base_url=llm_base_url.strip(),
                    llm_model=llm_model.strip(),
                    system_prompt=selected_tool["system"],
                    user_prompt=prompt,
                    timeout=180,
                )
        except Exception as exc:
            st.error(f"工具运行失败：{exc}")
            return

        render_tool_result("生成结果", result, f"{selected_tool['name']}.md")


def render_app() -> None:
    st.set_page_config(page_title="生物医学文献分析工作台", layout="wide")
    apply_page_style()
    st.title("生物医学文献分析工作台")
    st.caption("PDF精读 · 引用追踪 · 学术写作")
    render_quick_start_guide()

    with st.sidebar:
        st.header("配置")
        llm_provider = st.selectbox("LLM 服务商", ["OpenAI 兼容", "Google Gemini"])
        defaults = load_config_defaults(llm_provider)
        llm_api_key = st.text_input("LLM API Key", type="password")

        with st.expander("高级设置", expanded=False):
            llm_base_url = st.text_input("Base URL", value=defaults["llm_base_url"])
            llm_model = st.text_input("模型名称", value=defaults["llm_model"])
            openalex_api_key = st.text_input("OpenAlex API Key（可选）", value=defaults["openalex_api_key"], type="password")
            email = st.text_input("OpenAlex Email", value=defaults["openalex_email"])
            max_papers = st.number_input("最多文献数", min_value=1, max_value=1000, value=20, step=1)

        if llm_provider == "Google Gemini":
            st.caption("Gemini 使用 Google 原生接口。")
        else:
            st.caption("兼容 /chat/completions 的平台均可使用。")

        if st.button("测试连接", use_container_width=True):
            if validate_llm_config(llm_api_key, llm_base_url, llm_model):
                try:
                    with st.spinner("正在测试..."):
                        reply = call_llm(
                            llm_api_key=llm_api_key.strip(),
                            llm_provider=llm_provider,
                            llm_base_url=llm_base_url.strip(),
                            llm_model=llm_model.strip(),
                            system_prompt="你只需要回答连接正常。",
                            user_prompt="请回复：连接正常",
                            timeout=30,
                        )
                    st.success(f"连接成功：{reply[:60]}")
                except Exception as exc:
                    st.error(f"连接失败：{exc}")

    pdf_tab, citation_tab, nature_tab = st.tabs(["PDF精读", "引用追踪", "写作工具"])
    with pdf_tab:
        render_pdf_deep_reading_tab(llm_api_key, llm_provider, llm_base_url, llm_model)
    with citation_tab:
        render_citation_tracking_tab(openalex_api_key, email, int(max_papers))
    with nature_tab:
        render_nature_toolbox_tab(llm_api_key, llm_provider, llm_base_url, llm_model)


if __name__ == "__main__":
    render_app()
