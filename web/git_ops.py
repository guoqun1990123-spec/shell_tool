"""GitPython 封装：写文件 → git add → commit → push。"""
from datetime import datetime
from pathlib import Path

import git


class GitOps:
    def __init__(self, repo_path: str, remote: str = "origin",
                 branch: str = "main", author_name: str = "TFL Web",
                 author_email: str = "tfl@local"):
        self.repo = git.Repo(repo_path)
        self.remote_name = remote
        self.branch = branch
        self.actor = git.Actor(author_name, author_email)

    def write_and_commit(self, rel_path: str, content: str, commit_msg: str) -> str:
        """
        写文件到仓库工作目录，commit 并 push。
        返回生成文件的绝对路径。
        推送失败时抛出异常（调用方显示错误，本地文件已写入可手动处理）。
        """
        full_path = Path(self.repo.working_dir) / rel_path
        full_path.parent.mkdir(parents=True, exist_ok=True)
        full_path.write_text(content, encoding="utf-8")

        self.repo.index.add([str(full_path)])
        self.repo.index.commit(
            commit_msg,
            author=self.actor,
            committer=self.actor,
        )

        try:
            remote = self.repo.remote(self.remote_name)
            remote.push(self.branch)
        except git.exc.InvalidGitRepositoryError:
            pass  # no remote configured — local commit only
        except ValueError:
            pass  # remote name doesn't exist — local commit only
        except git.exc.GitCommandError as e:
            raise RuntimeError(
                f"Git push 失败，文件已写入本地（{full_path}），请手动 push。\n详情：{e}"
            ) from e

        return str(full_path)


def make_filename(protocol_name: str) -> str:
    """生成约定文件名：config_<方案简称>_<YYYYMMDD_HHMMSS>.yaml"""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = protocol_name.strip().replace(" ", "_") or "unnamed"
    return f"config/config_{safe_name}_{ts}.yaml"


def make_commit_msg(protocol_name: str) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    return f"feat(tfl): update config for {protocol_name or 'unnamed'} at {ts}"
