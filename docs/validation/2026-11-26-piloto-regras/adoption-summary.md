# Task and business-rule contracts: cross-harness adoption pilot

The pilot tested whether a natural request led to a usable change specification, and whether an editorial request stayed small. It used the bridge together with local agent routing instructions. It is not a benchmark of the CLIs or proof that installing this schema alone reproduces the routing behavior.

## Reproduce the inputs

The [four synthetic project files](adocao/fixture/) contain the [approved decision](adocao/fixture/DECISAO.md), [historical observation](adocao/fixture/HISTORICO.md), [demonstration](adocao/fixture/cartao.py), and [README containing the editorial typo](adocao/fixture/LEIAME.md). The spelling error and the incorrect comparison in the demonstration are intentional. Use the same [Portuguese requests](adocao/prompts.md) for each harness; do not give the model a skill name or a suggested answer.

For each CLI, start with the same four files and an existing OpenSpec project root with empty `changes/` and `specs/`. Select the bridge through the normal agent workflow. Send the production request, then start a new session in the same project and send the consumption request. Run the editorial request separately in a clean fixture. Check the resulting files as well as the model's response.

## Observations

In round one, OpenCode wrote directly to the main spec and changed the README. Its consumer found the behavior discrepancy, but the authoring path and strict validation failed. Codex selected the bridge but did not deliver a spec before timeout. AGY read the decision but did not produce a spec before timeout. The three editorial controls made the intended single-word correction.

Before round two, the local documentation skill was clarified: authoring a behavioral spec in a configured project belongs in a change, even when the design is already approved. More time was also allowed for multi-artifact production. The experiment does not isolate the effects of these two adjustments.

| Round two | Produced change | Fresh-session result | Editorial control |
| --- | --- | --- | --- |
| Codex CLI | `BR-VALIDADE` / `AC-LIMITE` | Found the incorrect last-day result | Spelling only |
| OpenCode CLI | `BR-VIS-01` / `AC-VIS-LIMITE` | Found the incorrect last-day result | Spelling only |
| AGY CLI | `BR-VISIBILIDADE-CARTAO` / `AC-NO-ULTIMO-DIA` | Found the incorrect last-day result | Spelling only |

For all three changes, `openspec validate --strict` and the bridge's `planning` check passed on the final artifacts. Each consumer read its own producer's delta, ran the demonstration, and distinguished the required **visible on the last day** from the observed **hidden on the last day**. No consumer changed project files or inferred an urgency exception. Each producer retained the four seed files and kept the main specs untouched; the CLI also materialized `openspec/config.yaml` and an empty archive directory in the fixture.

The nine stages cover spec production, fresh-session consumption and an editorial control in one synthetic case. They do not cover model-driven implementation through `preflight`, `candidate` and `verify`, or other clients. Source regression tests cover guard behavior separately. Host-specific routing patches, transcripts and installation receipts are not part of the portable fixture.
