# SCPI binary-block fuzzing

Atheris runs in Linux on Python 3.12. From the equipment repository root on
Windows, use Docker Desktop with its Linux engine running:

```powershell
docker compose -f tests/fixtures/fuzz/compose.yaml build
docker compose -f tests/fixtures/fuzz/compose.yaml run --rm scpi-fuzz
```

The default run lasts about 60 seconds. Rebuild after changing equipment or the
sibling `../colosseum-core` checkout; both local sources are included in the image.
The image uses Linux AMD64, matching the available Atheris wheel.

Longer run and replay of a failure saved on the host:

```powershell
docker compose -f tests/fixtures/fuzz/compose.yaml run --rm scpi-fuzz -max_total_time=600
docker compose -f tests/fixtures/fuzz/compose.yaml run --rm scpi-fuzz /work/artifacts/crash-REPLACE_WITH_HASH
```

Generated corpus and failure artifacts persist under `.fuzz-work/` on the host,
which is ignored by Git. Tracked seeds are copied there only when absent.
Unexpected exceptions and invariant failures fail the process. Expected parser
rejections do not. Replay and reduce a discovery before fixing it, then add a
named regression to `tests/unit/test_scpi_binary.py`.

On Linux AMD64/Python 3.12, after installing core and `requirements.txt`:

```sh
FUZZ_WORK="$PWD/.fuzz-work" python tests/fixtures/fuzz/run.py -max_total_time=30
```

The Linux CI fuzz job runs this same target separately from pytest. Ordinary
pytest tests need no Atheris installation. No hardware or networking is used by
the harness. Atheris is Apache-2.0: https://github.com/google/atheris/blob/master/LICENSE

## UBX and mask validation

The same image includes separate targets and corpora:

```powershell
docker compose -f tests/fixtures/fuzz/compose.yaml build
docker compose -f tests/fixtures/fuzz/compose.yaml run --rm ubx-fuzz
docker compose -f tests/fixtures/fuzz/compose.yaml run --rm mask-fuzz
```

Both default to 60 seconds; append `-max_total_time=600` for a longer run.
Their host work directories are `.fuzz-work/ubx_stream/` and
`.fuzz-work/mask_validation/`. Replay failures by appending, for example,
`/work/ubx_stream/artifacts/crash-HASH` to the `ubx-fuzz` command.
Native Linux runs select a target with `FUZZ_TARGET=ubx_stream` or
`FUZZ_TARGET=mask_validation`. CI runs all three targets independently.

UBX checks arbitrary-stream chunk equivalence, valid framing, checksum-error
recovery, invalid-sync recovery, and nine payload decoders. Mask checks use
JSON inputs and accept only normalized results or `MaskSchemaError`, checking
normalization stability and preservation of the original input. Existing
nonfinite-number acceptance is preserved; no new numeric policy is imposed.
