import argparse
import os
import shutil
import stat
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from git import Repo
from github import Github


@dataclass
class RepoStatistics:
    repo_name: str
    state: str = "CLEAN"  # CLEAN or DIRTY
    dirty_branches: int = 0
    dirty_files: int = 0
    error_files: int = 0


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
        print(f"  ERROR from nbstripout command on {file}")
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
    print(f"Checking branch: {branch}")
    git_repo.git.switch(branch)

    files_to_check = path.rglob("*.ipynb")
    # print("  Files to check for output:")
    for file in files_to_check:
        # print(f"    {file}")
        repo_stat = check_file(file, repo_stat)

    changed_files = [item.a_path for item in git_repo.index.diff(None)]
    if changed_files:
        print("  Files that contains output:")
        for file in changed_files:
            print(f"    {file}")
        repo_stat.state = "DIRTY"
        repo_stat.dirty_branches += 1
        repo_stat.dirty_files += len(changed_files)

    # Cleanup
    git_repo.git.reset("--hard")

    print(f"  Branch {branch} is DIRTY") if changed_files else print(
        f"  Branch {branch} is CLEAN"
    )
    return repo_stat


def check_repo(repo, token):
    clone_url = credentials_url(repo.clone_url, token)
    print("--------------------------------------------")
    print(f"Checking repo: {repo.full_name}")
    # print(f"Checking repo: {repo.full_name}, {repo.name}, {repo.clone_url}")
    # Set clone path to ../tmp-repos/{repo.name}
    path = Path().resolve().parent / "tmp-repos" / repo.name
    delete_dir(path)
    git_repo = Repo.clone_from(clone_url, path)

    branches = [b.name[7:] for b in git_repo.remote().refs]
    if "HEAD" in branches:
        branches.remove("HEAD")
    print(f"Branches: {branches}")

    repo_stat = RepoStatistics(repo.full_name)
    for branch in branches:
        repo_stat = check_branch(git_repo, path, branch, repo_stat)

    print(f"Repo {repo.full_name} is {repo_stat.state}")
    print(repo_stat)

    # delete_dir(path)
    return repo_stat


def main(token):
    print("Scanning organization for repos containing Jupyter Notebooks...")
    g = Github(token)

    # jupyter_repos = [
    #     g.get_repo("statisticsnorway/testrepo1"),
    #     g.get_repo("statisticsnorway/testrepo2"),
    # ]
    jupyter_repos = []
    for repo in g.get_organization("statisticsnorway").get_repos():
        if "Jupyter Notebook" in repo.get_languages():
            print(f"{repo.full_name} contains notebooks")
            jupyter_repos.append(repo)
    print(f"There are {len(jupyter_repos)} repos with Jupyter Notebooks")

    repo_stats = []
    for repo in jupyter_repos:
        repo_stats.append(check_repo(repo, token))

    print("------------------------------------")
    print("Statistics:")
    print(f"Number of Jupyter repos : {len(repo_stats)}")
    print(f"Number of dirty repos   : {sum(rs.state == 'DIRTY' for rs in repo_stats)}")
    print(f"Number of dirty branches: {sum(rs.dirty_branches for rs in repo_stats)}")
    print(f"Number of dirty files   : {sum(rs.dirty_files for rs in repo_stats)}")
    print(f"Number of error files   : {sum(rs.error_files for rs in repo_stats)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=sys.modules[__name__].__doc__)
    parser.add_argument("token", help="GitHub Personal Access Token")
    args = parser.parse_args()

    main(args.token)
