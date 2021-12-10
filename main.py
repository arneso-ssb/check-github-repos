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
from github import Github


logging.basicConfig(
    level=logging.INFO,
    handlers=[
        logging.FileHandler("jupyter-output-check.log", mode="w"),
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
    """For deleting read_only files in .git directory by making them writeable"""
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
            f"  Checking branch: {branch}, DIRTY. Repo: {repo_stat.repo_name}. Files that contains output:"
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


def check_repo(repo, token):
    clone_url = credentials_url(repo.clone_url, token)
    logging.info("--------------------------------------------")
    logging.info(f"Checking repo: {repo.full_name}")

    # Set clone path to ../tmp-repos/{repo.name}
    path = Path().resolve().parent / "tmp-repos" / repo.name
    delete_dir(path)
    git_repo = Repo.clone_from(clone_url, path)

    # Strip "origin/"-part of branch names
    branches = [b.name[7:] for b in git_repo.remote().refs]
    if "HEAD" in branches:
        branches.remove("HEAD")
    logging.info(f"  Branches: {branches}")

    repo_stat = RepoStatistics(repo.full_name)
    for branch in branches:
        repo_stat = check_branch(git_repo, path, branch, repo_stat)

    if repo_stat.state == "CLEAN":
        logging.info(f"Repo {repo.full_name} is CLEAN")
    else:
        logging.warning(f"Repo {repo.full_name} is {repo_stat.state}")
        contributors = repo.get_contributors()
        if contributors:
            repo_stat.repo_contact_name = contributors[0].name
            repo_stat.repo_contact_email = contributors[0].email

    logging.info(repo_stat)

    delete_dir(path)
    return repo_stat


def main(token):
    logging.info("Scanning organization for repos containing Jupyter Notebooks...")
    g = Github(token)

    # jupyter_repos = [
    #     g.get_repo("statisticsnorway/testrepo1"),
    #     g.get_repo("statisticsnorway/testrepo2"),
    # ]
    jupyter_repos = []
    for repo in g.get_organization("statisticsnorway").get_repos():
        if "Jupyter Notebook" in repo.get_languages():
            logging.info(f"{repo.full_name} contains notebooks")
            jupyter_repos.append(repo)
    logging.info(f"There are {len(jupyter_repos)} repos with Jupyter Notebooks")

    repo_stats = []
    for repo in jupyter_repos:
        repo_stats.append(check_repo(repo, token))

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
