# 云端部署说明

推荐使用 Streamlit Community Cloud。

## 需要上传到 GitHub 的文件

至少上传这些文件：

- `app.py`
- `literature_search.py`
- `ppt_report.py`
- `nature_workspace.py`
- `requirements.txt`
- `README.md`
- `.streamlit/config.toml`

不要上传：

- `.streamlit/secrets.toml`
- `__pycache__/`
- `.openalex_cache/`
- `.citation_cache/`
- `*.xlsx`
- `.env`

## Streamlit Community Cloud 部署步骤

1. 登录 GitHub，新建一个仓库，例如 `biomed-literature-workbench`。
2. 上传上述文件到仓库。
3. 打开 Streamlit Community Cloud。
4. 选择 `New app`。
5. Repository 选择刚才的 GitHub 仓库。
6. Branch 选择 `main`。
7. Main file path 填：

```text
app.py
```

8. 点击部署。

## Secrets 与 API Key

当前网页设计为让使用者在侧边栏输入自己的 LLM API Key。

如果你想在云端统一配置默认模型和学术 API，可以在 Streamlit Cloud 的 Secrets 中加入下列键，但不要把 API Key 写进 `app.py` 或提交 `.streamlit/secrets.toml`。

可选 Secrets：

```toml
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash-lite"
OPENALEX_MAILTO = "your@email.com"
OPENALEX_API_KEY = "your_openalex_key"
NCBI_API_KEY = "your_ncbi_key"
LITERATURE_CONTACT_EMAIL = "your@email.com"
```

- `OPENALEX_API_KEY`：启用“文献检索”中的 OpenAlex 来源；未配置时该来源会禁用，PubMed、Europe PMC 和 Crossref 仍可使用。
- `NCBI_API_KEY`：可选，用于提高 PubMed E-utilities 的允许请求速率；未配置时使用匿名速率限制。
- `LITERATURE_CONTACT_EMAIL`：PubMed、OpenAlex 和 Crossref 的联系邮箱；未设置时兼容使用 `OPENALEX_MAILTO`。
- LLM API Key 默认仍由使用者在侧边栏输入；它只在启用“智能改写”时额外调用一次模型，失败会回退到原始检索词。

文献检索通过四个官方 API 实时联邦查询并在当前会话中去重，不在服务器保存论文全文。页面只展示来源页和上游明确提供的开放获取链接，不代理或批量下载 PDF。

## 免费平台建议

- 首选：Streamlit Community Cloud。
- 备选：Hugging Face Spaces。
- 不建议首选：Render/Railway，免费额度或休眠策略更不稳定。

## 部署后检查

- 打开网页，确认能看到 `PDF精读`、`文献检索`、`引用追踪`、`科研写作`、`PPT汇报` 五个标签。
- 进入 `科研写作 → 科研绘图`，上传 CSV/XLSX 后确认能预览并下载 PNG、SVG、PDF。
- 不配置 OpenAlex Key 时，确认文献检索仍可选择 PubMed、Europe PMC 和 Crossref，且 OpenAlex 显示为禁用。
- 使用 `CRISPR base editing`、2022–2026、每源 5 条做一次检索；有 OpenAlex Key 时运行四源，否则运行三源。
- 不填 LLM Key 时应提示填写 Key。
- 引用追踪可先用 `最多文献数=5` 测试。
- PDF 图片模式需要 Gemini Key。
