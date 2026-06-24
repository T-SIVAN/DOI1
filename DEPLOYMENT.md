# 云端部署说明

推荐使用 Streamlit Community Cloud。

## 需要上传到 GitHub 的文件

至少上传这些文件：

- `app.py`
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

如果你想在云端统一配置默认模型，可以在 Streamlit Cloud 的 Secrets 里设置环境变量，但不要把 API Key 写进 `app.py`。

可选环境变量：

```toml
OPENAI_BASE_URL = "https://api.openai.com/v1"
OPENAI_MODEL = "gpt-4o-mini"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_MODEL = "gemini-2.5-flash-lite"
OPENALEX_MAILTO = "your@email.com"
OPENALEX_API_KEY = "your_openalex_key"
```

## 免费平台建议

- 首选：Streamlit Community Cloud。
- 备选：Hugging Face Spaces。
- 不建议首选：Render/Railway，免费额度或休眠策略更不稳定。

## 部署后检查

- 打开网页，确认能看到 `PDF精读`、`引用追踪`、`写作工具` 三个标签。
- 不填 LLM Key 时应提示填写 Key。
- 引用追踪可先用 `最多文献数=5` 测试。
- PDF 图片模式需要 Gemini Key。
