import argparse
import os
import subprocess
import json
import sys


def fetch_review_comments(owner, repo_name, pr_number, include_outdated=False):
    """
    Fetch review comments (comments on specific code lines) using GitHub API.

    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number
        include_outdated: If True, include all comments; if False, only current ones

    Returns:
        List of review comment dictionaries
    """
    endpoint = f"repos/{owner}/{repo_name}/pulls/{pr_number}/comments"
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        comments = json.loads(result.stdout)

        if not include_outdated:
            # Filter to current comments (position > 0; outdated have position = null or 0)
            comments = [c for c in comments if c.get("position") and c.get("position") > 0]

        return comments
    except subprocess.CalledProcessError as e:
        print(f"Error fetching review comments: {e.stderr}", file=sys.stderr)
        return []


def fetch_issue_comments(owner, repo_name, pr_number):
    """
    Fetch issue comments (general PR discussion comments not attached to code).

    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number

    Returns:
        List of issue comment dictionaries
    """
    endpoint = f"repos/{owner}/{repo_name}/issues/{pr_number}/comments"
    try:
        result = subprocess.run(
            ["gh", "api", endpoint],
            capture_output=True,
            text=True,
            check=True
        )
        comments = json.loads(result.stdout)
        return comments
    except subprocess.CalledProcessError as e:
        print(f"Error fetching issue comments: {e.stderr}", file=sys.stderr)
        return []


def fetch_pr_comments(repo, pr_number, include_outdated=False):
    """
    Fetch all comments from a PR: both review comments and issue comments.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: Pull request number
        include_outdated: If True, include outdated review comments

    Returns:
        Dictionary with 'review_comments' and 'issue_comments' lists
    """
    # Parse repo into owner and repo_name
    try:
        owner, repo_name = repo.split('/')
    except ValueError:
        raise ValueError("Repository must be in 'owner/repo' format")

    review_comments = fetch_review_comments(owner, repo_name, pr_number, include_outdated)
    issue_comments = fetch_issue_comments(owner, repo_name, pr_number)

    return {
        "review_comments": review_comments,
        "issue_comments": issue_comments
    }


def main():
    parser = argparse.ArgumentParser(
        description="Fetch PR comments from GitHub and output as JSON"
    )
    parser.add_argument(
        "repo",
        type=str,
        help="Repository in 'owner/repo' format (e.g., 'facebook/react')"
    )
    parser.add_argument(
        "pr_number",
        type=int,
        help="Pull request number"
    )
    parser.add_argument(
        "--all-comments",
        action="store_true",
        help="Include all comments (including outdated ones)"
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output"
    )

    args = parser.parse_args()

    # Fetch comments
    comments = fetch_pr_comments(args.repo, args.pr_number, args.all_comments)

    # Output as JSON
    if args.pretty:
        print(json.dumps(comments, indent=2))
    else:
        print(json.dumps(comments))


if __name__ == "__main__":
    main()
