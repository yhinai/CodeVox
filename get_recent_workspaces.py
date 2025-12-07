#!/usr/bin/env python3
"""
Get the 25 most recent VS Code workspaces from workspace.json files
"""

import json
import os
import sqlite3
from pathlib import Path
from datetime import datetime

def get_folder_from_state_db(workspace_dir):
    """Extract folder path from state.vscdb SQLite database

    Args:
        workspace_dir: Path to workspace directory

    Returns:
        Folder path as string or None
    """
    state_db = workspace_dir / "state.vscdb"
    if not state_db.exists():
        return None

    try:
        conn = sqlite3.connect(state_db)
        cursor = conn.cursor()

        # Try to find folder information in various keys
        import re

        # First try to find file:// URIs
        for key_pattern in ['%folder%', '%root%', '%workspace%']:
            cursor.execute(
                "SELECT key, value FROM ItemTable WHERE key LIKE ?",
                (key_pattern,)
            )
            results = cursor.fetchall()
            for key, value in results:
                # Extract file:// URIs from the value
                if 'file://' in value:
                    match = re.search(r'file://(/[^"\s]+)', value)
                    if match:
                        folder_path = match.group(1)
                        # Clean up the path (remove trailing parts like .vscode/launch.json)
                        if '/.vscode/' in folder_path:
                            folder_path = folder_path.split('/.vscode/')[0]
                        conn.close()
                        return f"file://{folder_path}"

                # Handle vscode-userdata: URIs (VS Code settings, extensions, etc.)
                if 'vscode-userdata:' in value:
                    conn.close()
                    return "vscode-userdata (VS Code settings/config)"

                # Handle vscode-remote:// URIs
                if 'vscode-remote://' in value:
                    match = re.search(r'(vscode-remote://[^"\s]+)', value)
                    if match:
                        conn.close()
                        return match.group(1)

        conn.close()
    except Exception as e:
        pass

    return None

def get_recent_workspaces(limit=25):
    """Get the most recent VS Code workspace.json files

    Args:
        limit: Number of most recent workspaces to return

    Returns:
        List of tuples (workspace_path, workspace_data, mtime)
    """
    workspace_storage = Path.home() / ".config/Code/User/workspaceStorage"

    if not workspace_storage.exists():
        print(f"Error: Workspace storage directory not found: {workspace_storage}")
        return []

    # Find all workspace directories and get their most recent modification time
    workspace_files = []
    for workspace_dir in workspace_storage.iterdir():
        if workspace_dir.is_dir():
            try:
                # Find the most recently modified file in the workspace directory
                # This gives us a better indicator of when the workspace was actually used
                most_recent_mtime = 0
                for file_path in workspace_dir.rglob('*'):
                    if file_path.is_file():
                        file_mtime = file_path.stat().st_mtime
                        if file_mtime > most_recent_mtime:
                            most_recent_mtime = file_mtime

                # Skip if no files found in directory
                if most_recent_mtime == 0:
                    continue

                workspace_json = workspace_dir / "workspace.json"
                workspace_files.append((workspace_json if workspace_json.exists() else workspace_dir, most_recent_mtime, workspace_dir))
            except Exception as e:
                print(f"Warning: Could not process {workspace_dir}: {e}")

    # Sort by modification time (most recent first)
    workspace_files.sort(key=lambda x: x[1], reverse=True)

    # Get top N most recent
    recent_workspaces = []
    for workspace_path, mtime, workspace_dir in workspace_files[:limit]:
        try:
            # Handle both workspace.json paths and directory paths
            if workspace_path.is_file():
                with open(workspace_path, 'r') as f:
                    data = json.load(f)
            else:
                # Directory without workspace.json - try to extract from state.vscdb
                folder = get_folder_from_state_db(workspace_dir)
                if folder:
                    data = {"folder": folder}
                else:
                    data = {"folder": f"Unknown (workspace ID: {workspace_path.name})"}
            recent_workspaces.append((workspace_path, data, mtime))
        except Exception as e:
            print(f"Warning: Could not read {workspace_path}: {e}")

    return recent_workspaces

def main():
    """Main function"""
    print("Finding 25 most recent VS Code workspaces...\n")

    workspaces = get_recent_workspaces(25)

    if not workspaces:
        print("No workspaces found!")
        return

    print(f"Found {len(workspaces)} recent workspaces:\n")
    print("=" * 80)

    for i, (path, data, mtime) in enumerate(workspaces, 1):
        # Format modification time
        mod_time = datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M:%S')

        # Extract folder path if available
        folder = data.get('folder', 'Unknown')
        if folder and folder != 'Unknown':
            # Handle URI format (file:///path/to/folder)
            if isinstance(folder, str) and folder.startswith('file://'):
                folder = folder[7:]  # Remove 'file://'

        # Get workspace directory name
        workspace_id = path.parent.name if path.is_file() else path.name

        print(f"{i}. {folder}")
        print(f"   Workspace ID: {workspace_id}")
        print(f"   Last modified: {mod_time}")
        print(f"   Path: {path}")
        print(f"   Data: {json.dumps(data, indent=2)}")
        print("-" * 80)

    # Save to a JSON file in current working directory
    output_file = Path.cwd() / "recent_vscode_workspaces.json"
    output_data = [
        {
            "rank": i,
            "workspace_id": path.parent.name if path.is_file() else path.name,
            "folder": data.get('folder', 'Unknown'),
            "last_modified": datetime.fromtimestamp(mtime).isoformat(),
            "path": str(path),
            "data": data
        }
        for i, (path, data, mtime) in enumerate(workspaces, 1)
    ]

    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"\nSaved results to: {output_file}")

if __name__ == "__main__":
    main()
