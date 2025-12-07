"""GitHub integration for fetching PR comments and data"""

import os
import sys
from typing import Dict, List, Optional
from github import Github, Auth
from dotenv import load_dotenv

try:
    from .config import settings
    GH_TOKEN = settings.GH_TOKEN
except ImportError:
    GH_TOKEN = os.getenv("GH_TOKEN")

# Load environment variables from .env file
load_dotenv()


def _get_github_client() -> Github:
    """
    Initialize GitHub client with authentication.
    Tries to get token from GH_TOKEN environment variable (loaded from .env).
    """
    token = os.environ.get("GH_TOKEN")
    if token:
        auth = Auth.Token(token)
        return Github(auth=auth)
    else:
        # Use without authentication (has lower rate limits)
        return Github()


def fetch_review_comments(owner: str, repo_name: str, pr_number: int, include_outdated: bool = False) -> List[Dict]:
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
    try:
        g = _get_github_client()
        repo = g.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)

        comments = []
        for comment in pr.get_review_comments():
            # Safely extract all fields with proper None handling
            comment_dict = {
                "id": comment.id if hasattr(comment, 'id') else None,
                "body": comment.body if hasattr(comment, 'body') else None,
                "user": {"login": comment.user.login} if (hasattr(comment, 'user') and comment.user) else None,
                "created_at": comment.created_at.isoformat() if (hasattr(comment, 'created_at') and comment.created_at) else None,
                "updated_at": comment.updated_at.isoformat() if (hasattr(comment, 'updated_at') and comment.updated_at) else None,
                "path": comment.path if hasattr(comment, 'path') else None,
                "position": comment.position if hasattr(comment, 'position') else None,
                "original_position": comment.original_position if hasattr(comment, 'original_position') else None,
                "commit_id": comment.commit_id if hasattr(comment, 'commit_id') else None,
                "original_commit_id": comment.original_commit_id if hasattr(comment, 'original_commit_id') else None,
                "diff_hunk": comment.diff_hunk if hasattr(comment, 'diff_hunk') else None,
                "line": comment.line if hasattr(comment, 'line') else None,
                "start_line": comment.start_line if hasattr(comment, 'start_line') else None,
                "start_side": comment.start_side if hasattr(comment, 'start_side') else None,
                "side": comment.side if hasattr(comment, 'side') else None,
            }
            comments.append(comment_dict)

        if not include_outdated:
            # Filter to current comments (position > 0; outdated have position = null or 0)
            comments = [c for c in comments if c.get("position") and c.get("position") > 0]

        return comments
    except Exception as e:
        print(f"Error fetching review comments: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []


def fetch_issue_comments(owner: str, repo_name: str, pr_number: int) -> List[Dict]:
    """
    Fetch issue comments (general PR discussion comments not attached to code).

    Args:
        owner: Repository owner
        repo_name: Repository name
        pr_number: Pull request number

    Returns:
        List of issue comment dictionaries
    """
    try:
        g = _get_github_client()
        repo = g.get_repo(f"{owner}/{repo_name}")
        pr = repo.get_pull(pr_number)

        comments = []
        for comment in pr.get_issue_comments():
            comment_dict = {
                "id": comment.id if hasattr(comment, 'id') else None,
                "body": comment.body if hasattr(comment, 'body') else None,
                "user": {"login": comment.user.login} if (hasattr(comment, 'user') and comment.user) else None,
                "created_at": comment.created_at.isoformat() if (hasattr(comment, 'created_at') and comment.created_at) else None,
                "updated_at": comment.updated_at.isoformat() if (hasattr(comment, 'updated_at') and comment.updated_at) else None,
            }
            comments.append(comment_dict)

        return comments
    except Exception as e:
        print(f"Error fetching issue comments: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return []


def fetch_pr_comments(repo: str, pr_number: int, include_outdated: bool = False) -> Dict[str, List]:
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


def fetch_pr_info(repo: str, pr_number: int) -> Optional[Dict]:
    """
    Fetch PR information including title, description, status, etc.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: Pull request number

    Returns:
        Dictionary with PR information or None if error
    """
    try:
        owner, repo_name = repo.split('/')
    except ValueError:
        raise ValueError("Repository must be in 'owner/repo' format")

    try:
        g = _get_github_client()
        repository = g.get_repo(f"{owner}/{repo_name}")
        pr = repository.get_pull(pr_number)

        pr_info = {
            "id": pr.id if hasattr(pr, 'id') else None,
            "number": pr.number if hasattr(pr, 'number') else None,
            "title": pr.title if hasattr(pr, 'title') else None,
            "body": pr.body if hasattr(pr, 'body') else None,
            "state": pr.state if hasattr(pr, 'state') else None,
            "user": {"login": pr.user.login} if (hasattr(pr, 'user') and pr.user) else None,
            "created_at": pr.created_at.isoformat() if (hasattr(pr, 'created_at') and pr.created_at) else None,
            "updated_at": pr.updated_at.isoformat() if (hasattr(pr, 'updated_at') and pr.updated_at) else None,
            "closed_at": pr.closed_at.isoformat() if (hasattr(pr, 'closed_at') and pr.closed_at) else None,
            "merged_at": pr.merged_at.isoformat() if (hasattr(pr, 'merged_at') and pr.merged_at) else None,
            "merge_commit_sha": pr.merge_commit_sha if hasattr(pr, 'merge_commit_sha') else None,
            "assignees": [{"login": a.login} for a in pr.assignees] if (hasattr(pr, 'assignees') and pr.assignees) else [],
            "labels": [{"name": l.name} for l in pr.labels] if (hasattr(pr, 'labels') and pr.labels) else [],
            "head": {
                "ref": pr.head.ref if hasattr(pr.head, 'ref') else None,
                "sha": pr.head.sha if hasattr(pr.head, 'sha') else None,
            } if hasattr(pr, 'head') else None,
            "base": {
                "ref": pr.base.ref if hasattr(pr.base, 'ref') else None,
                "sha": pr.base.sha if hasattr(pr.base, 'sha') else None,
            } if hasattr(pr, 'base') else None,
            "draft": pr.draft if hasattr(pr, 'draft') else None,
            "merged": pr.merged if hasattr(pr, 'merged') else None,
            "mergeable": pr.mergeable if hasattr(pr, 'mergeable') else None,
            "mergeable_state": pr.mergeable_state if hasattr(pr, 'mergeable_state') else None,
            "comments": pr.comments if hasattr(pr, 'comments') else None,
            "review_comments": pr.review_comments if hasattr(pr, 'review_comments') else None,
            "commits": pr.commits if hasattr(pr, 'commits') else None,
            "additions": pr.additions if hasattr(pr, 'additions') else None,
            "deletions": pr.deletions if hasattr(pr, 'deletions') else None,
            "changed_files": pr.changed_files if hasattr(pr, 'changed_files') else None,
        }
        return pr_info
    except Exception as e:
        print(f"Error fetching PR info: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None


def respond_to_pr_comment(repo: str, pr_number: int, comment_id: int, body: str) -> Optional[Dict]:
    """
    Respond to a PR review comment.

    Args:
        repo: Repository in 'owner/repo' format
        pr_number: Pull request number
        comment_id: ID of the comment to respond to
        body: The response text

    Returns:
        Dictionary with the created reply information or None if error
    """
    try:
        owner, repo_name = repo.split('/')
    except ValueError:
        raise ValueError("Repository must be in 'owner/repo' format")

    try:
        g = _get_github_client()
        repository = g.get_repo(f"{owner}/{repo_name}")
        pr = repository.get_pull(pr_number)

        # Get the review comment by ID to verify it exists
        comment = None
        for review_comment in pr.get_review_comments():
            if review_comment.id == comment_id:
                comment = review_comment
                break

        if not comment:
            raise ValueError(f"Comment with ID {comment_id} not found in PR #{pr_number}")

        # Create reply using the PR's method
        reply = pr.create_review_comment_reply(comment_id, body)

        # Return the reply information
        reply_info = {
            "id": reply.id if hasattr(reply, 'id') else None,
            "body": reply.body if hasattr(reply, 'body') else None,
            "user": {"login": reply.user.login} if (hasattr(reply, 'user') and reply.user) else None,
            "created_at": reply.created_at.isoformat() if (hasattr(reply, 'created_at') and reply.created_at) else None,
            "in_reply_to_id": comment_id,
            "path": reply.path if hasattr(reply, 'path') else None,
        }
        return reply_info
    except Exception as e:
        print(f"Error responding to PR comment: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return None
