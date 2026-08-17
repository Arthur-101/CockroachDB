import os
import subprocess
import fnmatch
from pathlib import Path
from typing import Dict, Any, List, Optional

class FileExplorerTool:
    """Provides tools for workspace directory tree browsing, pattern finding, and keyword search."""

    def open_in_explorer(self, path: str) -> Dict[str, Any]:
        """Open a directory or highlight a specific file in Windows File Explorer."""
        try:
            resolved_path = os.path.abspath(path)
            if not os.path.exists(resolved_path):
                return {"success": False, "result": None, "message": f"Path does not exist: {resolved_path}"}

            # On Windows, launch Explorer.exe
            if os.path.isfile(resolved_path):
                subprocess.Popen(f'explorer.exe /select,"{resolved_path}"')
            else:
                subprocess.Popen(f'explorer.exe "{resolved_path}"')

            return {
                "success": True,
                "result": {"path": resolved_path},
                "message": f"Opened path in File Explorer: {resolved_path}"
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Error opening explorer: {str(e)}"}

    def get_file_tree(self, directory: Optional[str] = None, depth: int = 3) -> Dict[str, Any]:
        """Generate a formatted text tree of directory contents recursively."""
        try:
            target_dir = os.path.abspath(directory or os.getcwd())
            if not os.path.exists(target_dir):
                return {"success": False, "result": None, "message": f"Directory not found: {target_dir}"}

            exclude_names = {".git", "node_modules", ".venv", "__pycache__", ".svelte-kit", "dist", "build"}
            
            def _build_tree(path: Path, current_depth: int) -> List[str]:
                if current_depth > depth:
                    return ["... (depth limit reached)"]
                
                lines = []
                try:
                    # Sort directories first, then files
                    items = sorted(list(path.iterdir()), key=lambda x: (not x.is_dir(), x.name.lower()))
                    for item in items:
                        if item.name in exclude_names:
                            continue
                        
                        prefix = "  " * (current_depth - 1)
                        if item.is_dir():
                            lines.append(f"{prefix}[DIR]  {item.name}/")
                            lines.extend(_build_tree(item, current_depth + 1))
                        else:
                            lines.append(f"{prefix}[FILE] {item.name}")
                except Exception as e:
                    lines.append(f"{prefix}[Error reading dir: {str(e)}]")
                return lines

            tree_lines = [f"[ROOT] {os.path.basename(target_dir)}/"]
            tree_lines.extend(_build_tree(Path(target_dir), 1))
            
            return {
                "success": True,
                "result": {"tree": "\n".join(tree_lines)},
                "message": "File tree generated successfully"
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Error generating tree: {str(e)}"}

    def find_files(self, pattern: str, directory: Optional[str] = None) -> Dict[str, Any]:
        """Find files matching a wildcard/glob pattern recursively."""
        try:
            target_dir = os.path.abspath(directory or os.getcwd())
            if not os.path.exists(target_dir):
                return {"success": False, "result": None, "message": f"Directory not found: {target_dir}"}

            exclude_names = {".git", "node_modules", ".venv", "__pycache__"}
            matches = []

            for root, dirs, files in os.walk(target_dir):
                # Prune excluded directories in-place to prevent traversing them
                dirs[:] = [d for d in dirs if d not in exclude_names]
                
                for filename in fnmatch.filter(files, pattern):
                    full_path = os.path.join(root, filename)
                    rel_path = os.path.relpath(full_path, target_dir)
                    matches.append(rel_path)

            return {
                "success": True,
                "result": {"matches": matches, "count": len(matches)},
                "message": f"Found {len(matches)} files matching pattern '{pattern}'"
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Error finding files: {str(e)}"}

    def grep_search(self, query: str, directory: Optional[str] = None, file_pattern: Optional[str] = None) -> Dict[str, Any]:
        """Search recursively for lines containing a specific keyword/query in text files."""
        try:
            target_dir = os.path.abspath(directory or os.getcwd())
            if not os.path.exists(target_dir):
                return {"success": False, "result": None, "message": f"Directory not found: {target_dir}"}

            exclude_names = {".git", "node_modules", ".venv", "__pycache__"}
            matches = []
            max_results = 100

            for root, dirs, files in os.walk(target_dir):
                dirs[:] = [d for d in dirs if d not in exclude_names]
                
                for filename in files:
                    if len(matches) >= max_results:
                        break
                    
                    if file_pattern and not fnmatch.fnmatch(filename, file_pattern):
                        continue
                    
                    full_path = os.path.join(root, filename)
                    try:
                        # Scan file line by line
                        with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                            for line_num, line in enumerate(f, 1):
                                if query.lower() in line.lower():
                                    rel_path = os.path.relpath(full_path, target_dir)
                                    matches.append({
                                        "file": rel_path,
                                        "line_number": line_num,
                                        "content": line.strip()
                                    })
                                    if len(matches) >= max_results:
                                        break
                    except Exception:
                        continue  # Skip unreadable or binary files

            return {
                "success": True,
                "result": {"matches": matches, "count": len(matches), "truncated": len(matches) >= max_results},
                "message": f"Found {len(matches)} matches for query '{query}'"
            }
        except Exception as e:
            return {"success": False, "result": None, "message": f"Error searching files: {str(e)}"}
