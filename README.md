# 生物医学文献分析工作台

一个本地 Streamlit 网页工具，面向生物医学科研场景，包含 PDF 精读、四源文献检索、引用追踪、学术写作和 PPT 汇报。

## 功能

- `PDF精读`：上传 PDF，支持快速/增强/结构化解析，以及文本、图片和混合读取，生成单篇文献剖析、标准领域突破表，并直接导出 Word `.docx` 精读报告。
- `文献检索`：并行查询 PubMed、Europe PMC、OpenAlex 和 Crossref，统一字段、跨库去重和综合排序；支持来源/年份/OA/摘要筛选，并导出 Excel、RIS 或 BibTeX。LLM Key 可用于一次性生成分库检索式，无 Key 时直接检索原始关键词。
- `引用追踪`：输入 DOI 或 OpenAlex Paper ID，抓取引用该文献的论文元数据，可尝试开放全文引用上下文，并导出 Excel。
- `写作工具`：提供润色、章节起草、预投稿审稿、审稿回复、数据可用性声明、文献检索方案、PPT 大纲等文本工具。
- `PPT汇报`：上传一篇或多篇论文/专利 PDF，自动读取全文 Fig./Table/Scheme 图例与图注，解析核心内容和关键图表，生成内置蓝色表格版式的 `.pptx`；每篇文献标题栏会尽量显示完整题名、DOI 和期刊 IF，不需要额外 PPT 模板文件。

## 启动

本机使用：

```text
双击 start_web.bat
```

如果是第一次运行，也可以先安装依赖：

```powershell
pip install -r requirements.txt
```

然后打开：

```text
http://localhost:8501/
```

同一 Wi-Fi / 局域网分享给朋友：

```text
双击 start_web_lan.bat
```

脚本会显示可访问地址，通常类似：

```text
http://192.168.x.x:8501/
```

如果 Windows 防火墙提示，请允许专用网络访问。使用期间保持启动窗口打开。

## 配置

侧边栏只需要先填写：

- `LLM 服务商`
- `LLM API Key`

高级设置里可以调整：

- `Base URL`
- `模型名称`
- `OpenAlex API Key（启用 OpenAlex 检索来源时必需）`
- `OpenAlex Email`（同时作为学术 API 联系邮箱）
- `最多文献数`

也可以用环境变量设置默认值：

```powershell
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
$env:GEMINI_MODEL="gemini-2.5-flash-lite"
$env:OPENALEX_API_KEY="your_openalex_key"
$env:OPENALEX_MAILTO="your@email.com"
$env:NCBI_API_KEY="your_ncbi_key"
# 可用统一联系邮箱覆盖 OPENALEX_MAILTO
$env:LITERATURE_CONTACT_EMAIL="your@email.com"
```

`NCBI_API_KEY` 为可选项；未配置时 PubMed 会按 NCBI 匿名速率限制运行。OpenAlex 来源在没有 `OPENALEX_API_KEY` 时会在界面中禁用，其他三个来源仍可正常检索。

`LITERATURE_CONTACT_EMAIL`（或 `OPENALEX_MAILTO`）应填写真实联系邮箱；PubMed 与 Crossref 检索会用它遵循上游 API 的使用规范。

## 可选增强

基础依赖已包含 PyMuPDF4LLM；如需进一步结构化解析，可额外安装 Docling：

```powershell
pip install docling
```

开放全文引用上下文可以连接本地 GROBID 服务：

```powershell
$env:GROBID_BASE_URL="http://localhost:8070"
```

未安装这些增强组件时，网页会自动降级，不影响基础功能。

## 注意

- 不要把自己的 LLM API Key 写死在代码里再分享给别人。
- 文献检索只保存当前 Streamlit 会话中的结果，不建立个人文献库；只展示来源页及上游确认的开放获取链接，不代理或批量下载 PDF。
- PubMed、Europe PMC、OpenAlex 与 Crossref 的记录高度重叠，界面的“唯一文献”是去重结果，不能把各来源数量简单相加理解为全文数量。
- 图片模式需要 Google Gemini，并且比文本模式更耗模型资源。
- 扫描版或图片型专利 PDF 没有文本层，文本解析器会读不到文字；PPT 汇报会在 Google Gemini 下自动转为页面图片识别，使用 OpenAI 兼容文本接口时需先 OCR。
- PDF 精读报告会直接导出 Word `.docx`；领域突破部分会固定渲染为标准表格，不再依赖 Markdown 表格格式。
- 增强 PDF 解析会优先使用 PyMuPDF4LLM；结构化解析会优先使用 Docling。未安装时会自动降级为本地 pypdf/启发式解析。
- 引用上下文只处理开放获取 PDF，不绕过付费墙；无开放全文或无法匹配目标 DOI 时会标注为摘要/元数据证据。
- HTTP 503 通常是模型服务拥堵，不是 PDF 文件问题；可稍后重试或切换模型。
- OpenAlex 不提供具体引用上下文，网页会明确区分全文上下文证据和元数据/摘要推断。
- 期刊 IF 采用本地可维护映射表，未收录期刊会显示“待核验”；正式汇报前建议以 JCR 或期刊官网最新数据复核。
