# Publishing results with GitHub Pages

The results site is static HTML plus curated benchmark artifacts. It does not execute SQL, run an MCP server, access local datasets, or call AWS.

## Publish your fork

Enable GitHub Pages in the repository's **Settings → Pages** and select **GitHub Actions** as the build source. Push to `main` or run **Publish results** from the Actions tab. The workflow builds `site/` using `python scripts/build_site.py`, uploads it with the official Pages artifact action, and deploys it with the official Pages deployment action. The site's repository links use `GITHUB_REPOSITORY`, so they follow your fork automatically.

The default public address is `https://OWNER.github.io/REPOSITORY/`. Local preview:

```bash
python3 scripts/build_site.py
python3 -m http.server 8000 --directory site
```

Open `http://localhost:8000`. The script uses only the Python standard library. GitHub stores HTML as source in the repository file viewer; Pages renders it as a website.

## Publish another benchmark deliberately

The builder copies only `examples/quick-led/` and `examples/measured/`. It never exports `workspaces/`, `data/`, private workloads, or connector settings. New local runs do not appear on the public site automatically.

For a result you intend to disclose, create a curated example directory containing its completed report, chart, selected candidate SQL, measurements, source metadata without local paths, and a short provenance record. Review hypotheses, filters, errors, SQL, and schema for sensitive information as well as credentials. Use a source you have permission to publish. Do not copy `state.json`, `worker.log`, source files, or caches wholesale. Add the directory explicitly to the builder and update the narrative to match its measurements. A report can contain business information even when raw rows are absent.

Preserve failed attempts and distinguish scripted recipes from assistant-selected experiments. Do not replace measured numbers with illustrative values. A deployment updates the public evidence; rerun tests and inspect the rendered page before pushing.

The deployment follows [GitHub’s custom Pages workflow guide](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages).
