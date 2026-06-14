from __future__ import annotations

import sys
import tempfile
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from backend.cli import main
from backend.gfa_core import parse_gfa_text


def run_cli(args: list[str]) -> None:
    code = main(args)
    if code != 0:
        raise AssertionError(f"CLI command failed ({code}): {' '.join(args)}")


def main_test() -> None:
    with tempfile.TemporaryDirectory(prefix="gfa-editor-cli-smoke-") as temp_dir:
        root = Path(temp_dir)
        gfa_path = root / "tiny.gfa"
        merged_path = root / "tiny.merged.gfa"
        query_path = root / "query.fa"
        image_path = root / "tiny.png"
        repeat_path = root / "repeat.gfa"
        repeat_all_path = root / "repeat.resolved.gfa"
        repeat_all_again_path = root / "repeat.again.resolved.gfa"
        repeat_merged_path = root / "repeat.merged.gfa"
        repeat_ref_merged_path = root / "repeat.ref.merged.gfa"

        gfa_path.write_text(
            "\n".join(
                [
                    "H\tVN:Z:1.0",
                    "S\tA\tAACCGGTTAACC\tLN:i:12\tDP:f:5",
                    "S\tB\tTTGGCCAATTGG\tLN:i:12\tDP:f:12",
                    "L\tA\t+\tB\t+\t0M\tRC:i:3",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        query_path.write_text(">hitA\nCCGGTT\n>hitB\nGGCCAA\n", encoding="utf-8")
        repeat_path.write_text(
            "\n".join(
                [
                    "H\tVN:Z:1.0",
                    "S\tA\tAAAAAA\tLN:i:6",
                    "S\tB\tCCCCCC\tLN:i:6",
                    "S\tR\tGGGGGG\tLN:i:6",
                    "S\tC\tTTTTTT\tLN:i:6",
                    "S\tD\tACACAC\tLN:i:6",
                    "L\tA\t+\tR\t+\t0M",
                    "L\tB\t+\tR\t+\t0M",
                    "L\tR\t+\tC\t+\t0M",
                    "L\tR\t+\tD\t+\t0M",
                    "L\tC\t+\tB\t+\t0M",
                    "L\tD\t+\tA\t+\t0M",
                    "",
                ]
            ),
            encoding="utf-8",
        )

        run_cli(["stats", str(gfa_path)])
        run_cli(["merge", str(gfa_path), str(merged_path), "--all"])
        merged_graph = parse_gfa_text(merged_path.read_text(encoding="utf-8"), keep_sequences=True)
        assert len(merged_graph.segments) == 1
        assert len(merged_graph.links) == 0
        run_cli(
            [
                "image",
                str(gfa_path),
                str(image_path),
                "--colour",
                "blastsolid",
                "--query",
                str(query_path),
                "--alignment-tool",
                "exact",
                "--width",
                "600",
                "--height",
                "360",
            ]
        )
        assert image_path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n")

        run_cli(
            [
                "auto-repeat",
                str(repeat_path),
                str(repeat_all_path),
                "--candidate",
                "0",
                "--max-states",
                "100",
                "--max-candidates",
                "10",
            ]
        )
        run_cli(
            [
                "auto-repeat",
                str(repeat_path),
                str(repeat_all_again_path),
                "--candidate",
                "0",
                "--max-states",
                "100",
                "--max-candidates",
                "10",
            ]
        )
        first_candidate = root / "repeat.resolved.auto_repeat_001.gfa"
        first_candidate_again = root / "repeat.again.resolved.auto_repeat_001.gfa"
        assert first_candidate.is_file()
        assert first_candidate.read_text(encoding="utf-8") == first_candidate_again.read_text(encoding="utf-8")

        run_cli(
            [
                "auto-merge",
                str(repeat_path),
                str(repeat_merged_path),
                "--max-states",
                "100",
                "--max-candidates",
                "10",
            ]
        )
        run_cli(
            [
                "auto-merge",
                str(repeat_path),
                str(repeat_ref_merged_path),
                "--reference-merged",
                str(repeat_merged_path),
                "--max-states",
                "100",
                "--max-candidates",
                "10",
            ]
        )
        assert repeat_merged_path.read_text(encoding="utf-8") == repeat_ref_merged_path.read_text(encoding="utf-8")

    print("cli smoke ok")


if __name__ == "__main__":
    main_test()
