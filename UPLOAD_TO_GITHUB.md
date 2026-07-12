# Upload to T-SIVAN/DOI1

This ZIP is ready to replace the repository root contents.

1. Open https://github.com/T-SIVAN/DOI1 and choose **Add file -> Upload files**.
2. Extract the ZIP locally, then upload the extracted files and folders. Do not upload the ZIP as the only repository file.
3. Keep `.streamlit/config.toml` in its folder and remove the old root-level `config.toml` from GitHub.
4. Commit the upload to the `main` branch.
5. In Streamlit Community Cloud, keep the main file path as `app.py`, then reboot the app.

Recommended Streamlit Secrets:

```toml
OPENALEX_API_KEY = "your_openalex_key"
NCBI_API_KEY = "your_ncbi_key"
LITERATURE_CONTACT_EMAIL = "your@email.com"
```

`OPENALEX_API_KEY` and `NCBI_API_KEY` are optional. A real contact email is required when PubMed or Crossref is selected.
