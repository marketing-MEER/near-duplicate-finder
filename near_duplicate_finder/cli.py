"""Command line entry point: `near-duplicate-finder SOURCE`."""
from pathlib import Path

import click

from . import __version__, core
from .benchmark import STATS
from .report import Report, write_excel


@click.command()
@click.argument("source")
@click.option("--near", default=0.8, show_default=True, help="Similarity (0-1) from which pages are near duplicates.")
@click.option("--similar", default=0.3, show_default=True, help="Similarity (0-1) from which pages are listed as similar.")
@click.option("--max-pages", default=500, show_default=True, help="Most pages to load.")
@click.option("--delay", default=0.5, show_default=True, help="Seconds between requests (min 0.5).")
@click.option("-o", "--output", default="duplicates_report", show_default=True,
              help="Report name; writes <name>.html and <name>.xlsx")
@click.version_option(__version__)
def main(source, near, similar, max_pages, delay, output):
    """Find duplicate and near-duplicate pages in SOURCE: a domain to crawl, a sitemap (.xml),
    a file with one URL per line, or a folder of saved HTML/text files.

    Built by Meer Hamza - linkedin.com/in/meerhamza-seo
    """
    if not 0 < similar <= near <= 1:
        raise click.BadParameter("need 0 < --similar <= --near <= 1")
    click.echo(f"Loading pages from {source} ...")
    r = core.audit(source, delay=delay, max_pages=max_pages, near=near, similar=similar)
    pages, pairs, clusters = r["pages"], r["pairs"], r["clusters"]
    count = lambda t: int((pairs["type"] == t).sum()) if not pairs.empty else 0
    to_merge = int((pages["verdict"] == "consolidate").sum()) if not pages.empty else 0
    thin = int((pages["thin"] == "yes").sum()) if not pages.empty else 0

    report = Report(title="Duplicate content report", subtitle=f"{source} · {len(pages)} pages",
                    tool="near-duplicate-finder")
    report.add_cards([("Pages compared", int((pages["words"] > 0).sum()) if not pages.empty else 0),
                      ("Exact duplicate pairs", count("exact duplicate"), "bad" if count("exact duplicate") else "good"),
                      ("Near duplicate pairs", count("near duplicate"), "bad" if count("near duplicate") else "good"),
                      ("Similar pairs", count("similar"), "warn" if count("similar") else "good"),
                      ("Pages to consolidate", to_merge, "bad" if to_merge else "good"),
                      (f"Thin pages (<{core.THIN_WORDS} words)", thin, "warn" if thin else "good")])
    report.add_benchmark(STATS[0], how_used="NP Digital found duplicate-keyword overlap grows as sites age, and "
                         "advises merging competing pages into one stronger URL. Each duplicate cluster below "
                         "names the page to keep and the pages to merge or redirect into it.")
    report.add_benchmark(STATS[1], how_used="Original content earns more engagement than recycled content, so "
                         "pages that mostly repeat another page are worth rewriting or merging.")
    report.add_table("Clusters to consolidate", clusters, sheet="Clusters",
                     note=f"Pages that share at least {near:.0%} of their 5-word phrases. Keep = most words "
                          "(then shortest URL); check it is also the page with the most traffic before redirecting.")
    report.add_table("Duplicate and similar pairs", pairs, sheet="Pairs",
                     note="Similarity = share of 5-word phrases the two pages have in common (Jaccard).")
    report.add_table("All pages", pages, sheet="Pages")

    html_path = report.save_html(Path(output).with_suffix(".html"))
    xlsx_path = write_excel(report.sheets, Path(output).with_suffix(".xlsx"))
    click.secho(f"Report: {html_path}\nData:   {xlsx_path}", fg="green", bold=True)
    click.echo(f"{len(pages)} pages, {count('exact duplicate')} exact, {count('near duplicate')} near, "
               f"{count('similar')} similar pairs, {len(clusters)} clusters")


if __name__ == "__main__":
    main()
