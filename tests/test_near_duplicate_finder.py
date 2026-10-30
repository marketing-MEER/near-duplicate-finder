import functools
import http.server
import os
import tempfile
import threading
import unittest
from pathlib import Path

from click.testing import CliRunner

from near_duplicate_finder import cli, core, similarity

PAGES = Path(__file__).parent.parent / "examples" / "pages"
TEXT = ("one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen "
        "seventeen eighteen nineteen twenty")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class SimilarityTest(unittest.TestCase):
    def test_shingles_and_jaccard(self):
        a = similarity.shingles(TEXT)
        self.assertEqual(len(a), 16)
        self.assertEqual(similarity.jaccard(a, a), 1.0)
        b = similarity.shingles(TEXT.replace("twenty", "zebra"))
        self.assertAlmostEqual(similarity.jaccard(a, b), 15 / 17)
        self.assertEqual(similarity.shingles("Hi there"), {"hi there"})

    def test_minhash_lsh_matches_exact(self):
        docs = {"a": similarity.shingles(TEXT * 3), "b": similarity.shingles(TEXT * 3 + " extra words here"),
                "c": similarity.shingles("completely different text about something else entirely " * 3)}
        exact = similarity.similar_pairs(docs, 0.5)
        lsh = similarity.similar_pairs(docs, 0.5, exhaustive_up_to=0)
        self.assertEqual([p[:2] for p in exact], [("a", "b")])
        self.assertEqual(exact, lsh)

    def test_minhash_is_deterministic(self):
        s = similarity.shingles(TEXT)
        self.assertEqual(similarity.minhash(s), similarity.minhash(set(s)))

    def test_clusters(self):
        cl = similarity.clusters([("a", "b", 0.9), ("b", "c", 0.85), ("x", "y", 0.95)], ["a", "b", "c", "x", "y", "z"])
        self.assertEqual(cl, {"a": 1, "b": 1, "c": 1, "x": 2, "y": 2})


class AnalyseTest(unittest.TestCase):
    def test_example_folder(self):
        r = core.audit(str(PAGES))
        types = {(p["page_a"], p["page_b"]): p["type"] for p in r["pairs"].to_dict("records")}
        self.assertEqual(types[("crm-for-small-teams-print.html", "crm-for-small-teams.html")], "exact duplicate")
        self.assertEqual(types[("crm-berlin.html", "crm-hamburg.html")], "near duplicate")
        self.assertEqual(types[("blog-pipeline-cleanup.html", "blog-weekly-review.html")], "similar")
        self.assertEqual(sorted(r["clusters"]["keep"]), ["crm-berlin.html", "crm-for-small-teams.html"])
        pages = r["pages"].set_index("url")
        self.assertEqual(pages.loc["about.html", "thin"], "yes")
        self.assertEqual(pages.loc["crm-hamburg.html", "verdict"], "consolidate")
        self.assertEqual(r["requests"], 0)

    def test_main_text_drops_navigation(self):
        title, can, text = core.main_text("<title>T</title><nav>Menu Home</nav><main><p>Body text</p></main>"
                                          "<footer>Foot</footer>")
        self.assertEqual((title, text), ("T", "Body text"))

    def test_empty(self):
        r = core.analyse([])
        self.assertTrue(r["pairs"].empty and r["clusters"].empty and r["pages"].empty)


class HttpTest(unittest.TestCase):
    def test_crawl_and_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for f in PAGES.glob("*.html"):
                (root / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
            links = "".join(f'<a href="/{f.name}">{f.stem}</a>' for f in sorted(PAGES.glob("*.html")))
            (root / "index.html").write_text(f"<html><body><nav>{links}</nav><p>Home</p></body></html>",
                                             encoding="utf-8")
            server = http.server.ThreadingHTTPServer(
                ("127.0.0.1", 0), functools.partial(QuietHandler, directory=str(root)))
            threading.Thread(target=server.serve_forever, daemon=True).start()
            base = f"http://127.0.0.1:{server.server_port}"
            try:
                r = core.audit(base + "/")
                # index + 8 sample pages + /pricing and /blog, which the sample nav links to but do not exist
                self.assertEqual(len(r["pages"]), 11)
                self.assertEqual((r["pages"]["verdict"] == "not checked (404)").sum(), 2)
                self.assertEqual(len(r["clusters"]), 2)
                runner = CliRunner()
                with runner.isolated_filesystem():
                    res = runner.invoke(cli.main, [str(PAGES), "-o", "out"])
                    self.assertEqual(res.exit_code, 0, res.output)
                    self.assertIn("1 exact, 3 near, 1 similar", res.output)
                    self.assertTrue(os.path.exists("out.html") and os.path.exists("out.xlsx"))
            finally:
                server.shutdown()
                server.server_close()


if __name__ == "__main__":
    unittest.main()
