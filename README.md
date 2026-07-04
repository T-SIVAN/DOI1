# 生物医学文献分析工作台

一个本地 Streamlit 网页工具，面向生物医学科研场景，包含 PDF 精读、引用追踪和学术写作辅助。

## 功能

- `PDF精读`：上传 PDF，支持快速/增强/结构化解析，以及文本、图片和混合读取，生成单篇文献剖析与近 10 年领域突破追踪。
- `引用追踪`：输入 DOI 或 OpenAlex Paper ID，抓取引用该文献的论文元数据，可尝试开放全文引用上下文，并导出 Excel。
- `写作工具`：提供润色、章节起草、预投稿审稿、审稿回复、数据可用性声明、文献检索方案、PPT 大纲等文本工具。
- `PPT汇报`：上传一篇或多篇论文/专利 PDF，自动读取全文 Fig./Table/Scheme 图例与图注，解析核心内容和关键图表，生成内置蓝色表格版式的 `.pptx`，不需要额外 PPT 模板文件。

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
- `OpenAlex API Key（可选）`
- `OpenAlex Email`
- `最多文献数`

也可以用环境变量设置默认值：

```powershell
$env:OPENAI_BASE_URL="https://api.openai.com/v1"
$env:OPENAI_MODEL="gpt-4o-mini"
$env:GEMINI_BASE_URL="https://generativelanguage.googleapis.com/v1beta"
$env:GEMINI_MODEL="gemini-2.5-flash-lite"
$env:OPENALEX_API_KEY="your_openalex_key"
$env:OPENALEX_MAILTO="your@email.com"
```

## 可选增强

PDF 增强解析会自动检测可选库：

```powershell
pip install pymupdf4llm
pip install docling
```

开放全文引用上下文可以连接本地 GROBID 服务：

```powershell
$env:GROBID_BASE_URL="http://localhost:8070"
```

未安装这些增强组件时，网页会自动降级，不影响基础功能。

## 注意

- 不要把自己的 LLM API Key 写死在代码里再分享给别人。
- 图片模式需要 Google Gemini，并且比文本模式更耗模型资源。
- 增强 PDF 解析会优先使用 PyMuPDF4LLM；结构化解析会优先使用 Docling。未安装时会自动降级为本地 pypdf/启发式解析。
- 引用上下文只处理开放获取 PDF，不绕过付费墙；无开放全文或无法匹配目标 DOI 时会标注为摘要/元数据证据。
- HTTP 503 通常是模型服务拥堵，不是 PDF 文件问题；可稍后重试或切换模型。
- OpenAlex 不提供具体引用上下文，网页会明确区分全文上下文证据和元数据/摘要推断。
