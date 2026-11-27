# Screenshot Captions Checklist

Save every screenshot into `screenshots/` using the exact filename below and verify its one-line caption before final submission.

| # | File | Status | One-line Caption |
|---|---|---|---|
| 1 | `kb_01_card_counts.png` | [ ] | _Card counts per source and total (1,500+ cards across 3+ sources)._ |
| 2 | `kb_02_retrieval_results.png` | [ ] | _Recall@5 comparison showing vector, keyword, and hybrid search on 20 hand-written queries._ |
| 3 | `verdict_01_unit_tests.png` | [ ] | _Passing unit tests for M11 Verdict Engine including gates, sensitivity, and worked example._ |
| 4 | `ft_01_comparison_table.png` | [ ] | _Comparison of base, fine-tuned, and hosted scoring models on hand-checked test examples._ |
| 5 | `ft_02_training_loss.png` | [ ] | _Training and validation loss curves from QLoRA fine-tuning._ |
| 6 | `ft_03_failure_case.png` | [ ] | _Example where fine-tuning did not improve scoring, with explanation._ |
| 7 | `agentops_01_behaviour_tests.png` | [ ] | _Passing recorded-response behaviour tests (invalid JSON, timeout, empty source, poisoned page)._ |
| 8 | `ui_01_profile.png` | [ ] | _Student profile saved in the web UI (Kubernetes deployment)._ |
| 9 | `ui_02_discover_results.png` | [ ] | _Discover workflow ranked idea list with verdicts and reasons._ |
| 10 | `ui_03_verdict_card.png` | [ ] | _Verdict card displaying gates, six dimension scores with evidence links, weights, confidence, and stability._ |
| 11 | `ui_04_challenge.png` | [ ] | _Challenge action where critic re-checks a claim against evidence and defends or removes it._ |
| 12 | `ui_05_whatif_v2.png` | [ ] | _What-if suggestion applied to produce version 2 verdict._ |
| 13 | `ui_06_insufficient_evidence.png` | [ ] | _INSUFFICIENT EVIDENCE card explaining what evidence was missing without guessing._ |
| 14 | `ui_07_live_agents_and_approval.png` | [ ] | _Live agent progress stream with tool calls, spend, and budget approval prompt._ |
| 15 | `ops_01_trace.png` | [ ] | _Full run trace showing agent steps, tools, tokens, latency, and cost._ |
| 16 | `ops_02_dashboard.png` | [ ] | _AgenticOps dashboard tracking cost per verdict, latency, cache hits, fallbacks, approvals, and blocked injections._ |
| 17 | `ops_03_drift_report.png` | [ ] | _Post-ingestion drift report showing data freshness, niche coverage, and verdict distribution._ |
| 18 | `ops_04_budget_stop.png` | [ ] | _Run halting at budget threshold and requesting user approval._ |
| 19 | `tuning_01_before_matrix.png` | [ ] | _Before-tuning verdict confusion matrix on labelled set (with GO-on-NO-GO count)._ |
| 20 | `tuning_02_after_matrix.png` | [ ] | _After-tuning verdict confusion matrix on labelled set (with GO-on-NO-GO count)._ |
| 21 | `git_01_protected_main.png` | [ ] | _GitHub branch protection rules on main requiring PRs, reviews, and status checks._ |
| 22 | `git_02_pr_required_checks.png` | [ ] | _Pull request showing required GitHub Actions checks and partner review approval._ |
| 23 | `git_03_merge_conflict_pr.png` | [ ] | _Intentional merge conflict resolved and merged in a pull request._ |
| 24 | `ci_01_actions_green.png` | [ ] | _Passing GitHub Actions PR workflow across all required jobs._ |
| 25 | `ci_02_actions_failing.png` | [ ] | _Failing GitHub Actions PR run showing caught error before fix._ |
| 26 | `docker_01_images.png` | [ ] | _SHA-tagged module Docker images built locally._ |
| 27 | `docker_02_trivy_scan.png` | [ ] | _Trivy vulnerability scan passing with zero CRITICAL findings._ |
| 28 | `docker_03_compose_ps.png` | [ ] | _All local development services healthy via docker compose ps._ |
| 29 | `k8s_01_pods_running.png` | [ ] | _All pods Running/Completed in namespace idea-validator._ |
| 30 | `k8s_02_top_pods.png` | [ ] | _kubectl top pods resource measurements used to set requests and limits._ |
| 31 | `k8s_03_networkpolicy_test.png` | [ ] | _NetworkPolicy test showing external egress blocked from non-M5 pod and allowed from M5._ |
| 32 | `k8s_04_rollout_rollback.png` | [ ] | _Kubernetes rolling update, bad release stall, and kubectl rollout undo recovery._ |
| 33 | `k8s_05_eval_job_logs.png` | [ ] | _Cluster evaluation Job logs inside namespace idea-validator._ |
| 34 | `ci_03_jenkins_green.png` | [ ] | _Green Jenkins delivery pipeline across build, push, deploy, and smoke test stages._ |
| 35 | `ci_04_jenkins_failing.png` | [ ] | _Failing Jenkins pipeline run blocking deployment on stage failure._ |
