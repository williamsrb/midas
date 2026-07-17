"""Per-task pipeline: drives a TaskState through all stages, resumable.

A per-task flock prevents the same task from being processed twice
concurrently (cron cycle + manual `midas task`, or overlapping cycles).
"""

from __future__ import annotations

import fcntl
import tempfile
from pathlib import Path

from . import agent, config as config_mod, detect, gitops, logging_setup, notify, paths, report, worktime
from .config import Config
from .detect import llm as detect_llm
from .state import TaskState

log = logging_setup.get("pipeline")

# Stages whose handler invokes an LLM agent (dry runs stop before these;
# 'fetched' -> triage handles dry-run internally because it must still advance).
AGENT_STAGES = {"branch_ready", "planned", "implemented"}


class Pipeline:
    def __init__(self, cfg: Config, st: TaskState, dry_run: bool = False):
        self.cfg = cfg
        self.st = st
        self.dry_run = dry_run
        self.tlog = logging_setup.task_logger(st.key, st.dir)

    # ------------------------------------------------------------------
    def run(self) -> TaskState:
        handlers = {
            "discovered": self._fetch,
            "fetched": self._triage,
            "triaged": self._detect_env,
            "env_detected": self._clone,
            "cloned": self._branch,
            "branch_ready": self._plan,
            "planned": self._implement,
            "implemented": self._validate,
            "validated": self._commit,
            "committed": self._report,
            "reported": self._rest,
        }
        self.st.dir.mkdir(parents=True, exist_ok=True)
        lock_file = open(self.st.dir / ".lock", "w")
        try:
            fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            log.info("[%s] already being processed elsewhere - skipping", self.st.key)
            lock_file.close()
            return self.st

        try:
            while not self.st.is_terminal:
                stage = self.st.stage
                if self.dry_run and stage in AGENT_STAGES:
                    self._info(f"dry-run: stopping before agent stage (current: {stage})")
                    break
                handler = handlers.get(stage)
                if handler is None:
                    self.st.block(f"no handler for stage {stage}")
                    break
                self._info(f"stage {stage} -> running handler")
                try:
                    handler()
                except Exception as exc:  # a stage failure blocks the task, never the run
                    log.exception("task %s failed in stage %s", self.st.key, stage)
                    self.st.block(f"{stage}: {exc}")
                    self._notify("blocked", f"{self.st.key} blocked in {stage}: {exc}")
                    break
        finally:
            fcntl.flock(lock_file, fcntl.LOCK_UN)
            lock_file.close()
        return self.st

    def _info(self, msg: str) -> None:
        log.info("[%s] %s", self.st.key, msg)
        self.tlog.info(msg)

    def _notify(self, event: str, message: str) -> None:
        notify.send(self.cfg, event, message)

    def _rework_round(self) -> int:
        return int(self.st.data.get("rework_round", 0))

    # -- discovered -> fetched ------------------------------------------
    def _fetch(self) -> None:
        if not self.st.task_md.is_file():
            token = config_mod.jira_api_token()
            if token:
                from .jira_rest import JiraClient, render_task_md
                client = JiraClient(self.cfg.jira.base_url, self.cfg.me.jira_email, token)
                issue = client.issue(self.st.key)
                fields = issue.get("fields", {})
                self.st.summary = fields.get("summary", self.st.summary)
                self.st.data["last_seen_updated"] = fields.get("updated", "")
                self.st.data["comment_count"] = len(
                    (fields.get("comment") or {}).get("comments", [])
                )
                self.st.task_md.write_text(render_task_md(issue, self.cfg.jira.base_url))
                detail = "downloaded via REST"
            else:
                from . import jira_agent_fallback
                if not jira_agent_fallback.fetch_task_md(self.st.key, self.st.task_md, self.cfg):
                    raise RuntimeError(
                        "could not download task (REST token missing, MCP fallback failed)"
                    )
                detail = "downloaded via agent+MCP fallback"
        else:
            detail = "task.md already present"
        self._maybe_transition_in_progress()
        self.st.advance("fetched", detail)

    def _maybe_transition_in_progress(self) -> None:
        """Optionally move the Jira issue to In Progress when midas starts."""
        if not self.cfg.jira.auto_transition or self.dry_run:
            return
        token = config_mod.jira_api_token()
        if not token:
            self._info("auto_transition enabled but no Jira token - skipped")
            return
        from .jira_rest import JiraClient, JiraError
        try:
            client = JiraClient(self.cfg.jira.base_url, self.cfg.me.jira_email, token)
            if client.transition_to(self.st.key, self.cfg.jira.in_progress_status):
                self._info(f"transitioned to '{self.cfg.jira.in_progress_status}' on Jira")
            else:
                self._info(
                    f"no transition to '{self.cfg.jira.in_progress_status}' available - skipped"
                )
        except JiraError as exc:
            self._info(f"auto-transition failed (non-fatal): {exc}")

    # -- fetched -> triaged | answered | awaiting_spec ---------------------
    def _triage(self) -> None:
        """Classify the task before spending real tokens:

        - question from the analyst  -> answer it on Jira immediately
        - insufficient specification -> post questions on Jira, wait
        - rework round               -> classify feedback (requirements change
                                        vs complementary info) for the planner
        """
        if self.dry_run:
            self.st.advance("triaged", "skipped (dry-run)")
            return

        skill = paths.skills_dir() / "midas-triage" / "SKILL.md"
        rework = self._rework_round()
        prompt = (
            f"Read and follow the skill at {skill} in CLASSIFY mode.\n"
            f"Task file: {self.st.task_md}\n"
            f"spec_check enabled: {self.cfg.jira.spec_check}\n"
        )
        if rework:
            prev_task = self.st.dir / f"task.round{rework}.md"
            prev_plan = self.st.dir / f"plan.round{rework}.md"
            prompt += (
                f"REWORK ROUND {rework}. Previous round task file: {prev_task}\n"
                f"Previous plan: {prev_plan if prev_plan.is_file() else '(none)'}\n"
                f"Previous outcome: {self.st.data.get('prev_stage', '?')}\n"
                f"Diff the comments between the two task files - the NEW comments are "
                f"the analyst's feedback to classify.\n"
            )
        prompt += "Reply with ONLY the JSON object described in the skill."

        with tempfile.TemporaryDirectory(prefix="midas-triage-") as tmp:
            res = agent.run(
                prompt, cwd=Path(tmp), model=self.cfg.agents.utility_model, cfg=self.cfg,
                transcript=self.st.transcripts_dir / f"triage.r{rework}.jsonl",
                timeout_minutes=10, context=f"{self.st.key}/triage",
            )
        if not res.ok:
            raise RuntimeError(f"triage agent failed: {res.text[:300]}")
        verdict = agent.extract_json(res.text)
        self.st.data["triage"] = verdict
        self.st.save()

        if verdict.get("task_type") == "question":
            self._answer_question()
            return

        if self.cfg.jira.spec_check and verdict.get("spec_sufficient") is False:
            questions = [q for q in verdict.get("questions", []) if isinstance(q, str)]
            self._request_spec(questions)
            return

        feedback = verdict.get("feedback_type") or ""
        detail = f"implementation task (feedback: {feedback or 'n/a'})"
        self.st.advance("triaged", detail)

    def _answer_question(self) -> None:
        """The task is a question - answer it now instead of implementing."""
        skill = paths.skills_dir() / "midas-triage" / "SKILL.md"
        prompt = (
            f"Read and follow the skill at {skill} in ANSWER mode.\n"
            f"Task file: {self.st.task_md}\n"
            f"Answer the analyst's question fully, in the language they used. "
            f"You may consult MCP tools (e.g. GitLab) for facts. "
            f"Reply with ONLY the final answer text, ready to post as a Jira comment."
        )
        with tempfile.TemporaryDirectory(prefix="midas-answer-") as tmp:
            res = agent.run(
                prompt, cwd=Path(tmp), model=self.cfg.agents.implementer_model, cfg=self.cfg,
                transcript=self.st.transcripts_dir / "answer.jsonl",
                timeout_minutes=15, context=f"{self.st.key}/answer",
            )
        if not res.ok:
            raise RuntimeError(f"answer agent failed: {res.text[:300]}")
        (self.st.dir / "ANSWER.md").write_text(res.text)
        posted = self._post_comment(res.text)
        detail = "answer posted on Jira" if posted else "answer saved locally (posting unavailable)"
        self.st.advance("answered", detail)
        self._notify("answered", f"{self.st.key}: analyst question answered ({detail})")

    def _request_spec(self, questions: list[str]) -> None:
        body = (
            "Midas reviewed this task and needs clarification before implementing:\n\n"
            + "\n".join(f"* {q}" for q in questions)
            + "\n\nPlease update the description or reply here; the task will be "
              "picked up again automatically."
        )
        (self.st.dir / "SPEC_QUESTIONS.md").write_text(body)
        posted = self._post_comment(body)
        detail = (
            f"{len(questions)} spec questions "
            + ("posted on Jira" if posted else "saved locally (posting unavailable)")
        )
        self.st.advance("awaiting_spec", detail)
        self._notify("spec_questions", f"{self.st.key}: {detail}")

    def _post_comment(self, body: str) -> bool:
        """Post a midas comment on Jira - ALWAYS restricted to the configured group."""
        group = self.cfg.jira.comment_group
        token = config_mod.jira_api_token()
        if not group:
            self._info("jira.comment_group not set - midas never posts unrestricted comments")
            return False
        if not token:
            self._info("no Jira token - cannot post comment")
            return False
        from .jira_rest import JiraClient, JiraError
        try:
            JiraClient(self.cfg.jira.base_url, self.cfg.me.jira_email, token).add_comment(
                self.st.key, body, visibility_group=group
            )
            return True
        except JiraError as exc:
            self._info(f"posting comment failed: {exc}")
            return False

    # -- triaged -> env_detected ----------------------------------------
    def _detect_env(self) -> None:
        text = self.st.task_md.read_text()
        env = self.st.env()
        env.setdefault("sources", {})

        repo_url = detect.detect_repo_url(text, self.cfg.git.host)
        if repo_url:
            env["sources"]["repo_url"] = "task-text"
        else:
            candidate = self.cfg.git.clone_url_template.format(
                project=detect.project_key_from_issue(self.st.key)
            )
            if gitops.ls_remote_ok(candidate):
                repo_url = candidate
                env["sources"]["repo_url"] = "template"
        if not repo_url and not self.dry_run:
            self._info("no repo found deterministically, trying LLM fallback")
            hints = detect_llm.detect_from_task_text(
                self.st.task_md, self.cfg,
                transcript=self.st.transcripts_dir / "env-detect.jsonl",
            )
            candidate = hints.get("repo_url", "")
            if candidate and gitops.ls_remote_ok(candidate):
                repo_url = candidate
                env["sources"]["repo_url"] = "llm"
            if hints.get("review_url"):
                env["review_url"] = hints["review_url"]
                env["sources"]["review_url"] = "llm"
        if not repo_url:
            raise RuntimeError("could not determine the git repository for this task")

        review_url = detect.detect_review_url(text)
        if review_url:
            env["review_url"] = review_url
            env["sources"]["review_url"] = "task-text"

        env["repo_url"] = repo_url
        env["project"] = detect.project_from_url(repo_url)
        self.st.save_env(env)
        self.st.advance("env_detected", f"repo={repo_url}")

    # -- env_detected -> cloned (or skipped_dotnet) ----------------------
    def _clone(self) -> None:
        env = self.st.env()
        dest = self.cfg.workspace_root / env["project"]
        gitops.clone_or_update(env["repo_url"], dest)
        env["repo_path"] = str(dest)
        env.update(detect.detect_repo_traits(dest))
        self.st.save_env(env)
        if env.get("dotnet"):
            self._info(".NET project detected - skipping per policy")
            self.st.advance("skipped_dotnet", ".NET solution detected, out of scope")
            return
        self.st.advance("cloned", f"repo at {dest} (stack={env.get('stack')})")

    # -- cloned -> branch_ready ------------------------------------------
    def _branch(self) -> None:
        env = self.st.env()
        source = gitops.prepare_branch(Path(env["repo_path"]), self.st.key)
        self.st.advance("branch_ready", f"branch {self.st.key} ({source})")

    # -- branch_ready -> planned (planner model) ---------------------------
    def _plan(self) -> None:
        env = self.st.env()
        skill = paths.skills_dir() / "midas-task-spec" / "SKILL.md"
        rework = self._rework_round()
        prompt = (
            f"Read and follow the skill at {skill}.\n"
            f"Jira task file: {self.st.task_md}\n"
            f"Environment facts: {self.st.env_json}\n"
        )
        if rework:
            triage = self.st.data.get("triage", {})
            prompt += (
                f"REWORK ROUND {rework}. The analyst sent the task back.\n"
                f"Feedback type: {triage.get('feedback_type', 'unknown')}\n"
                f"Feedback summary: {triage.get('feedback_summary', '(see new comments)')}\n"
                f"Previous plan: {self.st.dir / f'plan.round{rework}.md'}\n"
                f"The branch already contains the previous implementation - plan the DELTA "
                f"that addresses the feedback, not a rewrite.\n"
            )
        prompt += (
            f"You are in the project repository. Produce the implementation plan and write it "
            f"EXACTLY to this absolute path: {self.st.plan_md}\n"
            f"Reply with a one-paragraph summary of the plan."
        )
        res = agent.run(
            prompt, cwd=Path(env["repo_path"]), model=self.cfg.agents.planner_model,
            cfg=self.cfg, transcript=self.st.transcripts_dir / "plan.jsonl",
            context=f"{self.st.key}/plan",
        )
        if not res.ok:
            raise RuntimeError(f"planning agent failed: {res.text[:300]}")
        if not self.st.plan_md.is_file():
            self.st.plan_md.write_text(res.text)
        self.st.advance("planned", f"plan by {res.agent}/{self.cfg.agents.planner_model}")

    # -- planned -> implemented (implementer model) --------------------------
    def _implement(self) -> None:
        env = self.st.env()
        skill_dirs = [paths.skills_dir() / "midas-implement"]
        if env.get("enonic"):
            skill_dirs.append(paths.skills_dir() / "vendor")
        skill_refs = "\n".join(f"- {d}" for d in skill_dirs)
        prompt = (
            f"Implement the approved plan at {self.st.plan_md} for Jira task {self.st.key}.\n"
            f"Task details: {self.st.task_md}\n"
            f"Environment facts: {self.st.env_json}\n"
            f"Skill/reference folders to read and follow (read the SKILL.md files first):\n{skill_refs}\n"
            f"Work only inside the current repository. Do NOT run git commit, git push or "
            f"create branches - midas handles git. Reply with a summary of the changes."
        )
        res = agent.run(
            prompt, cwd=Path(env["repo_path"]), model=self.cfg.agents.implementer_model,
            cfg=self.cfg, transcript=self.st.transcripts_dir / "implement.jsonl",
            context=f"{self.st.key}/implement",
        )
        if not res.ok:
            raise RuntimeError(f"implementation agent failed: {res.text[:300]}")
        if not gitops.is_dirty(Path(env["repo_path"])):
            raise RuntimeError("implementation agent finished but the repo has no changes")
        self.st.advance("implemented", f"implemented by {res.agent}")

    # -- implemented -> validated -------------------------------------------
    def _validate(self) -> None:
        env = self.st.env()
        variant = "enonic" if env.get("enonic") else "generic"
        qa_skill = paths.skills_dir() / "midas-qa-validation" / "SKILL.md"
        vc_skill = paths.skills_dir() / f"midas-validation-commit-{variant}" / "SKILL.md"
        prompt = (
            f"Validate the current unstaged solution delivery for Jira task {self.st.key}.\n"
            f"1. Read and follow {qa_skill}\n"
            f"2. Then read and follow {vc_skill}\n"
            f"Task details: {self.st.task_md}\n"
            f"Write the final commit message EXACTLY to this absolute path: "
            f"{self.st.commit_msg_file}\n"
            f"Never run git commit/push/add. Reply with the validation verdict."
        )
        res = agent.run(
            prompt, cwd=Path(env["repo_path"]), model=self.cfg.agents.validator_model,
            cfg=self.cfg, transcript=self.st.transcripts_dir / "validate.jsonl",
            context=f"{self.st.key}/validate",
        )
        if not res.ok:
            raise RuntimeError(f"validation agent failed: {res.text[:300]}")
        env["validation_verdict"] = res.text[:2000]
        self.st.save_env(env)
        self._generate_test_plan(env)
        self.st.advance("validated", "validation + commit message done")

    def _generate_test_plan(self, env: dict) -> None:
        """Best-effort Playwright test plan for the review environment."""
        if not env.get("review_url"):
            self._info("no review_url detected - skipping test plan")
            return
        skill = paths.skills_dir() / "midas-test-plan" / "SKILL.md"
        self.st.test_plan_dir.mkdir(parents=True, exist_ok=True)
        prompt = (
            f"Read and follow the skill at {skill}.\n"
            f"Jira task file: {self.st.task_md}\nEnvironment facts: {self.st.env_json}\n"
            f"Review base URL: {env['review_url']}\n"
            f"Write the test plan and Playwright spec files into this directory: "
            f"{self.st.test_plan_dir}\nReply with a summary."
        )
        res = agent.run(
            prompt, cwd=Path(env["repo_path"]), model=self.cfg.agents.implementer_model,
            cfg=self.cfg, transcript=self.st.transcripts_dir / "test-plan.jsonl",
            timeout_minutes=15, context=f"{self.st.key}/test-plan",
        )
        if not res.ok:
            self._info(f"test plan generation failed (non-fatal): {res.text[:200]}")

    # -- validated -> committed ----------------------------------------------
    def _commit(self) -> None:
        env = self.st.env()
        if self.st.commit_msg_file.is_file():
            message = self.st.commit_msg_file.read_text().strip()
        else:
            message = f"{self.st.key}: {self.st.summary}".strip().rstrip(":")
        forced = worktime.clamp_commit_datetime(self.cfg)
        force_date = worktime.git_date(forced) if forced else None
        if force_date:
            self._info(f"commit date clamped into working hours: {force_date}")
            env["commit_date_forced"] = force_date
        sha = gitops.commit_all(Path(env["repo_path"]), message, force_date=force_date)
        if sha is None:
            raise RuntimeError("nothing to commit after validation")
        env["commit_sha"] = sha
        env["branch"] = gitops.current_branch(Path(env["repo_path"]))
        self.st.save_env(env)
        self.st.advance("committed", f"commit {sha[:10]}")

    # -- committed -> reported -> awaiting_human -------------------------------
    def _report(self) -> None:
        path = report.write_completed(self.st, self.cfg)
        report.maybe_post_jira_comment(self.st, self.cfg)
        self.st.advance("reported", f"report at {path}")

    def _rest(self) -> None:
        self.st.advance(
            "awaiting_human",
            "committed on branch, waiting for human validation and merge to review",
        )
        env = self.st.env()
        self._notify(
            "awaiting_human",
            f"{self.st.key} ready for review: branch {env.get('branch', self.st.key)}, "
            f"commit {env.get('commit_sha', '?')[:10]}",
        )
