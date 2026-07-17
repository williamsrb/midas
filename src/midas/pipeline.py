"""Per-task pipeline: drives a TaskState through all stages, resumable."""

from __future__ import annotations

from pathlib import Path

from . import agent, config as config_mod, detect, gitops, logging_setup, paths, report
from .config import Config
from .detect import llm as detect_llm
from .state import TaskState

log = logging_setup.get("pipeline")

# Stages whose handler invokes an LLM agent.
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
            "fetched": self._detect_env,
            "env_detected": self._clone,
            "cloned": self._branch,
            "branch_ready": self._plan,
            "planned": self._implement,
            "implemented": self._validate,
            "validated": self._commit,
            "committed": self._report,
            "reported": self._rest,
        }
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
            except Exception as exc:  # any stage failure blocks the task, never crashes the run
                log.exception("task %s failed in stage %s", self.st.key, stage)
                self.st.block(f"{stage}: {exc}")
                break
        return self.st

    def _info(self, msg: str) -> None:
        log.info("[%s] %s", self.st.key, msg)
        self.tlog.info(msg)

    # -- discovered -> fetched ------------------------------------------
    def _fetch(self) -> None:
        if self.st.task_md.is_file():
            self.st.advance("fetched", "task.md already present")
            return
        token = config_mod.jira_api_token()
        if token:
            from .jira_rest import JiraClient, render_task_md
            client = JiraClient(self.cfg.jira.base_url, self.cfg.me.jira_email, token)
            issue = client.issue(self.st.key)
            self.st.summary = issue.get("fields", {}).get("summary", self.st.summary)
            self.st.task_md.write_text(render_task_md(issue, self.cfg.jira.base_url))
            self.st.advance("fetched", "downloaded via REST")
        else:
            from . import jira_agent_fallback
            if not jira_agent_fallback.fetch_task_md(self.st.key, self.st.task_md, self.cfg):
                raise RuntimeError("could not download task (REST token missing, MCP fallback failed)")
            self.st.advance("fetched", "downloaded via agent+MCP fallback")

    # -- fetched -> env_detected ----------------------------------------
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

    # -- branch_ready -> planned (Opus) -----------------------------------
    def _plan(self) -> None:
        env = self.st.env()
        skill = paths.skills_dir() / "midas-task-spec" / "SKILL.md"
        prompt = (
            f"Read and follow the skill at {skill}.\n"
            f"Jira task file: {self.st.task_md}\n"
            f"Environment facts: {self.st.env_json}\n"
            f"You are in the project repository. Produce the implementation plan and write it "
            f"EXACTLY to this absolute path: {self.st.plan_md}\n"
            f"Reply with a one-paragraph summary of the plan when done."
        )
        res = agent.run(
            prompt, cwd=Path(env["repo_path"]), model=self.cfg.agents.planner_model,
            cfg=self.cfg, transcript=self.st.transcripts_dir / "plan.jsonl",
            context=f"{self.st.key}/plan",
        )
        if not res.ok:
            raise RuntimeError(f"planning agent failed: {res.text[:300]}")
        if not self.st.plan_md.is_file():
            # agent answered but did not write the file - persist its answer as the plan
            self.st.plan_md.write_text(res.text)
        self.st.advance("planned", f"plan by {res.agent}/{self.cfg.agents.planner_model}")

    # -- planned -> implemented (Sonnet) -----------------------------------
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
        sha = gitops.commit_all(Path(env["repo_path"]), message)
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
