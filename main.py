"""This script checks an organization's repos for notebooks which contains outputs."""

import argparse
import logging
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from git import Repo
from github import Github, Repository


logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("jupyter-output-check.log", mode="w", encoding="utf-8"),
        logging.StreamHandler(),
    ],
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


@dataclass
class RepoStatistics:
    repo_name: str
    state: str = "CLEAN"  # CLEAN or DIRTY
    dirty_branches: int = 0
    dirty_files: int = 0
    error_files: int = 0
    repo_contact_name: str = ""
    repo_contact_email: str = ""
    repo_contact_rank: int = 0


def credentials_url(url, token):
    """Create url including credentials."""
    credentials = token + "@"
    split_index = url.find("//") + 2
    url_with_credentials = url[:split_index] + credentials + url[split_index:]
    return url_with_credentials


def check_file(file, repo_stat):
    argv = ["nbstripout", file]
    try:
        subprocess.run(argv, check=True)
    except subprocess.CalledProcessError:
        logging.warning(f"ERROR from nbstripout command on {file}")
        repo_stat.error_files += 1
    return repo_stat


def del_ro(function, path, excinfo):
    """For deleting read_only files in .git directory by making them writeable."""
    os.chmod(path, stat.S_IWRITE)
    os.remove(path)


def delete_dir(path):
    if path.exists():
        shutil.rmtree(path, onerror=del_ro)


def check_branch(git_repo, path, branch, repo_stat):
    git_repo.git.switch(branch)
    files_to_check = path.rglob("*.ipynb")
    logging.debug("  Files to check for output:")

    for file in files_to_check:
        logging.debug(f"    {file}")
        repo_stat = check_file(file, repo_stat)

    changed_files = [item.a_path for item in git_repo.index.diff(None)]
    if changed_files:
        logging.warning(
            f"  Checking branch: {branch}, DIRTY. Repo: {repo_stat.repo_name}. "
            f"Files that contains output:"
        )
        for file in changed_files:
            logging.warning(f"      {file}")
        repo_stat.state = "DIRTY"
        repo_stat.dirty_branches += 1
        repo_stat.dirty_files += len(changed_files)
    else:
        logging.info(f"  Checking branch: {branch}, CLEAN")

    # Cleanup
    git_repo.git.reset("--hard")

    return repo_stat


def get_contact_name_and_email(
    github_repo: Repository, git_repo: Repo
) -> tuple[str, str, int]:
    """Get the name and email of the person to be contacted for the repo.

    The priority order is the most frequent contributors(up to three).
    If the name or email is empty, the next item is tried.
    If no contributor with name and email is found, the name and email of
    the last committer on the default branch is selected.

    Contact rank:
        1..3 = contributor rank
        4 = last committer on default the branch

    Args:
        github_repo: The GitHub repo.
        git_repo: The cloned git repo.

    Returns:
        Tuple with name, email and contact rank.
    """
    name = ""
    email = ""
    contributors = github_repo.get_contributors()
    for i, contributor in enumerate(contributors, start=1):
        name = contributor.name
        email = contributor.email
        if name and email:
            return name, email, i
        if i >= 3:
            break

    # Fallback to name and email of last commit on default branch
    git_repo.git.switch(github_repo.default_branch)
    last_commit = git_repo.head.commit
    author_email = git_repo.git.show("-s", "--format=%ae", last_commit.hexsha)
    return last_commit.author.name, author_email, 4


def check_repo(github_repo, token, progress_text=""):
    clone_url = credentials_url(github_repo.clone_url, token)
    logging.info("--------------------------------------------")
    logging.info(f"Checking repo{progress_text}: {github_repo.full_name}")

    # Set clone path to ../tmp-repos/{repo.name}
    path = Path().resolve().parent / "tmp-repos" / github_repo.name
    delete_dir(path)
    git_repo = Repo.clone_from(clone_url, path)

    # Strip "origin/"-part of branch names
    branches = [b.name[7:] for b in git_repo.remote().refs]
    if "HEAD" in branches:
        branches.remove("HEAD")
    logging.info(f"  Branches: {branches}")

    repo_stat = RepoStatistics(github_repo.full_name)
    for branch in branches:
        repo_stat = check_branch(git_repo, path, branch, repo_stat)

    (
        repo_stat.repo_contact_name,
        repo_stat.repo_contact_email,
        repo_stat.repo_contact_rank,
    ) = get_contact_name_and_email(github_repo, git_repo)

    if repo_stat.state == "CLEAN":
        logging.info(f"Repo {github_repo.full_name} is CLEAN")
    else:
        logging.warning(f"Repo {github_repo.full_name} is {repo_stat.state}")

    logging.info(repo_stat)

    delete_dir(path)
    return repo_stat


def main(token):
    logging.info("Scanning organization for repos containing Jupyter Notebooks...")
    g = Github(token)

    jupyter_repos = []
    for repo in g.get_organization("statisticsnorway").get_repos():
        if "Jupyter Notebook" in repo.get_languages() and not repo.archived:
            logging.info(f"{repo.full_name} contains notebooks")
            jupyter_repos.append(repo)
    logging.info(f"There are {len(jupyter_repos)} repos with Jupyter Notebooks")

    repo_stats = []
    for i, repo in enumerate(jupyter_repos, start=1):
        progress_text = f" [{i}/{len(jupyter_repos)}]"
        repo_stats.append(check_repo(repo, token, progress_text))

    logging.info("------------------------------------")
    logging.info("Statistics:")
    logging.info(f"Number of Jupyter repos : {len(repo_stats)}")
    logging.info(
        f"Number of dirty repos   : {sum(rs.state == 'DIRTY' for rs in repo_stats)}"
    )
    logging.info(
        f"Number of dirty branches: {sum(rs.dirty_branches for rs in repo_stats)}"
    )
    logging.info(
        f"Number of dirty files   : {sum(rs.dirty_files for rs in repo_stats)}"
    )
    logging.info(
        f"Number of error files   : {sum(rs.error_files for rs in repo_stats)}"
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
