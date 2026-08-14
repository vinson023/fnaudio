# Large library benchmark

`tools/benchmark_large_library.py` creates an isolated synthetic SQLite index and
measures first, middle and final page reads. It never scans or modifies the real
music library.

Run the maintained 100,000-track scenario from the project root:

```powershell
python -B tools\benchmark_large_library.py --tracks 100000 --page-size 120 --output artifacts\large-library-benchmark-100k.json
```

The result records index build time, aggregate page-query time, SQLite size and
peak Python allocations while querying. Timing is evidence, not a CI threshold,
because it depends on the host filesystem and CPU. Automated tests enforce the
stable contract instead: SQLite reports the complete count, each response is
marked as paged and no response contains more than the requested page size.

This benchmark covers indexed pagination and memory behavior. It does not claim
that the current directory-signature scan is incremental; choosing filesystem
notifications or sharded directory signatures remains separate work.
