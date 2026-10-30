<div align="center">

# 👯 near-duplicate-finder

### Find exact and near-duplicate pages, group them, and get the page to keep for each group.

[![tests](https://github.com/marketing-MEER/near-duplicate-finder/actions/workflows/ci.yml/badge.svg)](https://github.com/marketing-MEER/near-duplicate-finder/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?logo=python&logoColor=white)
![License: MIT](https://img.shields.io/badge/license-MIT-green)
![No API keys](https://img.shields.io/badge/API%20keys-none%20needed-brightgreen)
[![Part of SEO Toolbox](https://img.shields.io/badge/part%20of-SEO%20Toolbox-orange)](https://github.com/marketing-MEER/seo-toolbox)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Meer%20Hamza-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)

[🚀 Quick start](#quick-start) · [⚙️ How it works](#how-it-works) · [📄 Report](#report) · [❓ FAQ](#faq) · [👤 Author](#author)

</div>

---

## 💡 What it does

Location pages built from one template, print versions, "small business" copies of "small team" pages: near
duplicates pile up quietly and split rankings between URLs. This tool compares the main text of every page
(navigation, header and footer removed), finds exact copies and pages that share most of their wording, groups
them into clusters and suggests which page to keep.

- ✅ Exact duplicates, near duplicates (80%+ shared phrases) and similar pages (30%+) in one table
- ✅ Clusters with a suggested page to keep and the pages to merge or redirect, and whether a canonical already handles it
- ✅ Works on a live site (crawl, sitemap or URL list) or a folder of saved HTML/text files
- ✅ Free, MIT licensed, no API keys. Works with the exports you already have.

## 📊 Why this matters

> **Keyword Cannibalization by Website Age** · NP Digital, March 2025
> - Mature sites older than 10 years average 13.95 percent keyword overlap.
> - Duplicate content compounds over time as more pages compete for similar terms.
>
> Data: [Neil Patel marketing stats](https://neilpatel.com/marketing-stats/keyword-cannibalization/)

**How near-duplicate-finder uses this:** the study shows overlap grows as a site ages, and its actionable insight
is to consolidate competing URLs into one stronger page. That is what the clusters are for: one page to keep,
the rest to merge or redirect. A second NP Digital stat
([original content and engagement](https://neilpatel.com/marketing-stats/content-originality-and-engagement/))
backs rewriting pages that mostly repeat another one.

<a id="quick-start"></a>

## 🚀 Quick start

```bash
git clone https://github.com/marketing-MEER/near-duplicate-finder.git
cd near-duplicate-finder
pip install -e .
near-duplicate-finder https://www.example.com/sitemap.xml
```

This writes **`duplicates_report.html`** (a formatted report you can open, share or print to PDF) and **`duplicates_report.xlsx`** (all the data).

> [!TIP]
> If the `near-duplicate-finder` command isn't found, use `python -m near_duplicate_finder`.

## 📥 Input

| Input | Example | What happens |
|---|---|---|
| Domain or URL | `www.example.com` | Crawls from there, same host only, robots.txt respected |
| Sitemap (`.xml`) | `https://www.example.com/sitemap.xml` | Loads every URL in it (indexes are followed) |
| URL list | `urls.txt` | One URL per line, e.g. a Screaming Frog or GSC export |
| Folder | `examples/pages` | Every `.html`, `.htm`, `.txt` and `.md` file in it, no requests at all |

<a id="how-it-works"></a>

## ⚙️ How it works

1. Loads each page (own user agent, at least 0.5 s between requests) and keeps the main text: `<main>` or
   `<article>` if present, otherwise `<body>`, with `nav`, `header`, `footer`, `aside`, forms and scripts removed.
2. Splits the text into overlapping 5-word phrases ("shingles").
3. Compares pages by the share of phrases they have in common (Jaccard similarity). Up to 300 pages are compared
   pair by pair; for larger sites MinHash with LSH banding picks candidate pairs first, then the exact score is computed.
4. Labels each pair: **exact duplicate** (identical text), **near duplicate** (≥ `--near`, default 80%) or
   **similar** (≥ `--similar`, default 30%). These are this tool's defaults, not official limits; tune them for your site.
5. Groups near duplicates into clusters and suggests the page to keep: the one with the most words, then the
   shortest URL. Pages under 100 words of main text are marked thin.
6. Marks pairs where both pages already canonicalise to the same URL ("canonical handles it").

### Options

| Option | Default | What it does |
|---|---|---|
| `--near` | `0.8` | Similarity from which pages count as near duplicates |
| `--similar` | `0.3` | Similarity from which pages are listed as similar |
| `--max-pages` | `500` | Most pages to load |
| `--delay` | `0.5` | Seconds between requests (never less than 0.5) |
| `-o`, `--output` | `duplicates_report` | File name for the report (`.html` + `.xlsx`) |

<a id="report"></a>

## 📄 The report

- **Cards**: pages compared, exact, near and similar pairs, pages to consolidate, thin pages.
- **Benchmarks**: the two NP Digital stats, with source and link.
- **Clusters to consolidate** (`Clusters` sheet): page to keep, pages to merge or redirect, highest and lowest similarity.
- **Duplicate and similar pairs** (`Pairs` sheet): both pages, similarity %, type, word counts, canonical handles it.
- **All pages** (`Pages` sheet): words, thin, cluster, closest page and its similarity, and a verdict (keep, consolidate, similar review, unique).

<details>
<summary>📄 Example: real output from <code>examples/</code></summary>

Run on the eight fictional pages in `examples/pages` (`near-duplicate-finder examples/pages`):
1 exact, 3 near and 1 similar pair, 2 clusters.

| cluster | pages | keep | merge or redirect | max similarity | min similarity |
|---|---|---|---|---|---|
| 1 | 2 | crm-berlin.html | crm-hamburg.html | 85.4 | 85.4 |
| 2 | 3 | crm-for-small-teams.html | crm-for-small-business.html | crm-for-small-teams-print.html | 100 | 88.7 |

| page a | page b | similarity | type | words a | words b | canonical handles it |
|---|---|---|---|---|---|---|
| crm-for-small-teams-print.html | crm-for-small-teams.html | 100 | exact duplicate | 171 | 171 | yes |
| crm-for-small-business.html | crm-for-small-teams-print.html | 88.7 | near duplicate | 171 | 171 | no |
| crm-for-small-business.html | crm-for-small-teams.html | 88.7 | near duplicate | 171 | 171 | no |
| crm-berlin.html | crm-hamburg.html | 85.4 | near duplicate | 131 | 131 | no |
| blog-pipeline-cleanup.html | blog-weekly-review.html | 36.5 | similar | 186 | 181 | no |

</details>

## 🧰 More free SEO tools

This repo is one tool in the **[SEO Toolbox](https://github.com/marketing-MEER/seo-toolbox)**, a family of free, single-purpose SEO tools. Related:
- [keyword-cannibalization-detector](https://github.com/marketing-MEER/keyword-cannibalization-detector): pages competing for the same queries in GSC
- [keyword-mapper](https://github.com/marketing-MEER/keyword-mapper): one owner URL per keyword
- [internal-link-analyzer](https://github.com/marketing-MEER/internal-link-analyzer): point your links at the page you keep
- [seo-workhorse](https://github.com/marketing-MEER/seo-workhorse): audit, clustering, redirects and GSC quick wins in one CLI

<a id="faq"></a>

## ❓ FAQ

<details><summary><b>Should I always redirect near duplicates?</b></summary>

No. Location or product variant pages can be legitimate. Then make them different (local details, own
photos, real reviews) or set a canonical. Redirect when two pages serve the same intent and one is weaker.
Check which page has the traffic and links before you choose the keeper.
</details>

<details><summary><b>Why is my similarity lower than expected?</b></summary>

5-word phrases are strict: changing one word changes five phrases around it. A template page where only the
city name differs still scores high, but a lightly rewritten article can drop to 30-60%. That is why "similar"
starts at 30% by default.
</details>

<details><summary><b>Is my data sent anywhere?</b></summary>

No. Everything runs on your machine. The only requests are GETs to the site you point it at (user agent
`near-duplicate-finder/1.0`); with a folder it makes no requests.
</details>

## 🧪 Tests

```bash
python -m unittest discover -s tests -t . -v
```

## 📄 License

[MIT](LICENSE). Free for personal and commercial use. Benchmark figures © their original publishers and quoted with a link to the source.

<a id="author"></a>

## 👤 Author

**Meer Hamza** · SEO Team Lead · Berlin 🇩🇪
10+ years in SEO, AEO and GEO. I build small tools that take the spreadsheet work out of SEO.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-0A66C2?logo=linkedin&logoColor=white)](https://www.linkedin.com/in/meerhamza-seo)
[![Email](https://img.shields.io/badge/Email-meerhamza5%40gmail.com-D14836?logo=gmail&logoColor=white)](mailto:meerhamza5@gmail.com)

<div align="center">

**If this saved you time, a ⭐ helps other SEOs find it.**

</div>
