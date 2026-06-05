# Simulated read queries for GFA visualization

These files are generated from `examples/mecat_mito_500K_before_rr.gfa` with perfect synthetic sequence chunks. They are intended for visualization testing, not benchmarking aligner accuracy.

Files:

- `edge8_repeat_long_reads.fasta`: query reads.
- `edge8_repeat_long_reads.paf`: simulated minimap2-style PAF results for importing into the app. Use Import format `PAF` and Map results to `Subject/target contigs`.
- `edge8_repeat_long_reads.tsv`: manifest describing each read and intended graph path.
- `edge33_path_long_reads.fasta`: a second query-read set focused on `edge_33`, `edge_11`, and `edge_25`.
- `edge33_path_long_reads.paf`: minimap2 PAF generated from `edge33_path_long_reads.fasta` against the reference GFA segment FASTA.
- `edge33_path_long_reads.tsv`: manifest for the `edge33_path` read set.

The repeat-focused reads exercise `edge_8`, which connects to `edge_10`, `edge_11`, `edge_9`, and `edge_28` in the reference GFA. The PAF rows are target-contig alignments; the manifest's intended graph path names the GFA endpoint being exercised.

Additional internal-span test:

- `sim_edge8_internal_401_1000` covers only `edge_8` positions 401-1000, for checking partial-contig coloring in Bandage/native view.

The `edge33_path` reads add a separate visualization set:

- `sim_edge33_internal_12001_18000` and `sim_edge33_internal_36001_43000`: two internal partial reads on different regions of `edge_33`.
- `sim_link_edge11_to_edge33`: crosses the `edge_11+ -> edge_33+` link.
- `sim_link_edge25_to_edge33_reverse_side`: crosses the `edge_25- -> edge_33-` link.
- `sim_path_edge8_edge11_edge33`: follows `edge_8+ -> edge_11+ -> edge_33+`.
- `sim_edge33_long_5001_25000`: long internal partial read on `edge_33`.
