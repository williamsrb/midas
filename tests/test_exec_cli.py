import textwrap

from click.testing import CliRunner

from midas import kernel
from midas.cli import main


def _install_shell_echo_kernel():
    kernel.install(
        "1.0.0",
        {
            kernel.BUNDLE_NAME: textwrap.dedent(
                """
                import { writeFileSync } from 'node:fs';
                import { join } from 'node:path';
                import { createInterface } from 'node:readline';
                const rl = createInterface({ input: process.stdin, terminal: false });
                rl.once('line', (line) => {
                  const req = JSON.parse(line);
                  console.log(JSON.stringify({ type: 'run_started', seq: 1 }));
                  console.log(JSON.stringify({ type: 'run_finished', seq: 2 }));
                  writeFileSync(
                    join(req.runDir, 'status.json'),
                    JSON.stringify({ state: 'succeeded', runId: req.runId }),
                  );
                  process.exit(0);
                });
                """
            ).encode(),
        },
    )
    kernel.activate("1.0.0")


def _playbook_path(tmp_path):
    playbook = tmp_path / "playbook.yaml"
    playbook.write_text(
        textwrap.dedent(
            """
            apiVersion: morpheus/v1
            kind: Playbook
            metadata:
              id: exec-cli-test
            spec:
              defaults: {}
              runners:
                - id: sh
                  subscription: shell
                  permission: full
              nodes:
                - id: only
                  type: shell
                  runner: sh
                  command: echo hi
              edges: []
            """
        )
    )
    return playbook


def test_dry_run_validates_without_spawning_a_kernel(tmp_path):
    playbook = _playbook_path(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["exec", str(playbook), "--workspace", str(workspace), "--dry-run"])
    assert result.exit_code == 0, result.output
    assert "OK" in result.output
    assert "exec-cli-test" in result.output


def test_dry_run_rejects_a_missing_workspace(tmp_path):
    playbook = _playbook_path(tmp_path)
    runner = CliRunner()
    result = runner.invoke(main, ["exec", str(playbook), "--workspace", str(tmp_path / "nope"), "--dry-run"])
    assert result.exit_code == 2
    assert "workspace does not exist" in result.output


def test_rejects_a_file_that_is_not_a_playbook(tmp_path):
    not_a_playbook = tmp_path / "notes.yaml"
    not_a_playbook.write_text("just: some yaml\n")
    workspace = tmp_path / "ws"
    workspace.mkdir()
    runner = CliRunner()
    result = runner.invoke(main, ["exec", str(not_a_playbook), "--workspace", str(workspace), "--dry-run"])
    assert result.exit_code == 2
    assert "not a playbook" in result.output


def test_runs_a_playbook_through_a_real_kernel_subprocess(tmp_path):
    _install_shell_echo_kernel()
    playbook = _playbook_path(tmp_path)
    workspace = tmp_path / "ws"
    workspace.mkdir()
    run_dir = tmp_path / "run"
    runner = CliRunner()
    result = runner.invoke(
        main, ["exec", str(playbook), "--workspace", str(workspace), "--run-dir", str(run_dir)]
    )
    assert result.exit_code == 0, result.output
    assert "run_started" in result.output
    assert "run_finished" in result.output
    assert "kernel exited: succeeded" in result.output
    assert (run_dir / "events.ndjson").is_file()
    assert (run_dir / "status.json").is_file()
