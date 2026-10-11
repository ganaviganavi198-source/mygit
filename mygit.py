import sys
import hashlib
from pathlib import Path
from datetime import datetime
import fnmatch
import os
import difflib


# =========================
# INIT
# =========================
def init_repository():
    git_dir = Path(".mygit")
    if git_dir.exists():
        print("Repository already exists.")
        return
    (git_dir / "objects").mkdir(parents=True)
    (git_dir / "refs" / "heads").mkdir(parents=True)
    (git_dir / "refs" / "tags").mkdir(parents=True)
    (git_dir / "HEAD").write_text("ref: refs/heads/main\n")
    (git_dir / "index").write_text("")
    print("Initialized empty MyGit repository.")
# =========================
# STATUS
# =========================
def status():
    print("MyGit Status")
    print("------------")

    index_file = Path(".mygit/index")
    head_file = Path(".mygit/HEAD")

    if not index_file.exists() or not head_file.exists():
        print("Repository not initialized.")
        return

    # Find the current branch
    head_content = head_file.read_text().strip()
    current_branch = "HEAD"
    commit_hash = ""

    if head_content.startswith("ref:"):
        branch_path = Path(
            ".mygit"
        ) / head_content.split(":", 1)[1].strip()

        current_branch = branch_path.name

        if branch_path.exists():
            commit_hash = branch_path.read_text().strip()
    else:
        commit_hash = head_content

    print(f"On branch {current_branch}")

    # Read the staging index
    index_entries = {}

    for line in index_file.read_text().splitlines():
        parts = line.split(" ", 1)

        if len(parts) == 2:
            index_entries[parts[0]] = parts[1]

    # Read files from the latest commit
    committed_entries = {}

    if commit_hash:
        committed_entries = get_commit_files(commit_hash)

    staged_changes = []
    unstaged_changes = []
    deleted_files = []
    untracked_files = []

    # Check staged changes
    for filename, staged_hash in index_entries.items():
        if committed_entries.get(filename) != staged_hash:
            staged_changes.append(filename)

    # Check files already in the index
    for filename, staged_hash in index_entries.items():
        file_path = Path(filename)

        if not file_path.exists():
            deleted_files.append(filename)
            continue

        if not file_path.is_file():
            continue

        current_hash = hash_file(filename)

        if current_hash != staged_hash:
            unstaged_changes.append(filename)

    # Find untracked files
    for file_path in Path(".").rglob("*"):
        if not file_path.is_file():
            continue

        relative_path = file_path.as_posix()

        # Ignore internal repository files
        if ".mygit" in file_path.parts:
            continue

        if relative_path == ".gitignore":
            continue

        if is_ignored(relative_path):
            continue

        if relative_path not in index_entries:
            untracked_files.append(relative_path)

    # Display staged changes
    print("\nChanges to be committed:")
    if staged_changes:
        for filename in sorted(staged_changes):
            print(f"  staged: {filename}")
    else:
        print("  None")

    # Display unstaged modifications
    print("\nChanges not staged:")
    if unstaged_changes:
        for filename in sorted(unstaged_changes):
            print(f"  modified: {filename}")
    else:
        print("  None")

    # Display deleted tracked files
    print("\nDeleted files:")
    if deleted_files:
        for filename in sorted(deleted_files):
            print(f"  deleted: {filename}")
    else:
        print("  None")

    # Display untracked files
    print("\nUntracked files:")
    if untracked_files:
        for filename in sorted(untracked_files):
            print(f"  untracked: {filename}")
    else:
        print("  None")
# =========================
# HASH FILE
# =========================
def hash_file(filename):
    with open(filename, "rb") as file:
        content = file.read()
    file_hash = hashlib.sha1(content).hexdigest()
    return file_hash
# =========================
# COMMIT
# =========================
def create_commit(message):
    if merge_in_progress():
        return 
    index_file = Path(".mygit/index")
    head_file = Path(".mygit/HEAD")

    if not index_file.exists() or not head_file.exists():
        print("Repository not initialized.")
        return

    index_content = index_file.read_text().strip()

    if not index_content:
        print("Nothing to commit.")
        return

    # Find the currently checked-out branch
    head_content = head_file.read_text().strip()

    if not head_content.startswith("ref:"):
        print("Cannot commit: detached HEAD is not supported yet.")
        return

    branch_path = Path(".mygit") / head_content.split(":", 1)[1].strip()

    if not branch_path.parent.exists():
        print("Current branch does not exist.")
        return

    previous_commit = ""
    if branch_path.exists():
        previous_commit = branch_path.read_text().strip()
# Prevent unnecessary commits
    
    staged_files = {}
    for line in index_content.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            staged_files[parts[0]] = parts[1]

    if previous_commit:
        previous_files = get_commit_files(previous_commit)
        if staged_files == previous_files:
            print("Nothing to commit. No changes detected.")
            return

    # Commit metadata
    author, email = get_identity()
    date = datetime.now().astimezone().isoformat(timespec="seconds")

    # Create commit data
    commit_data = (
        f"message: {message}\n"
        f"author: {author}\n"
        f"email: {email}\n"
        f"date: {date}\n"
        f"parent: {previous_commit}\n\n"
        f"{index_content}\n"
    )

    # Generate commit hash
    commit_hash = hashlib.sha1(
        commit_data.encode()
    ).hexdigest()

    # Store commit object
    object_file = Path(".mygit/objects") / commit_hash
    object_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(object_file, commit_data)

    # Update the currently checked-out branch
    branch_path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(branch_path, commit_hash)

    print("Commit created successfully!")
    print(f"Commit hash: {commit_hash}")
    print(f"Author: {author}")
    print(f"Email: {email}")
    print(f"Date: {date}")
    print(f"Message: {message}")

    
def add_file(filename):
    file_path = Path(filename)

    if not file_path.exists():
        print(f"Error: File '{filename}' does not exist.")
        return

    if is_ignored(filename):
        print(f"Ignored file: {filename}")
        return

    if not file_path.is_file():
        print("Error: Please provide a file.")
        return

    # Read the file and calculate its hash
    content = file_path.read_bytes()
    file_hash = hashlib.sha1(content).hexdigest()

    # Save the file content as an object
    object_path = Path(".mygit/objects") / file_hash
    object_path.parent.mkdir(parents=True, exist_ok=True)
    object_path.write_bytes(content)

    # Read the existing index
    index_path = Path(".mygit/index")
    index_path.parent.mkdir(parents=True, exist_ok=True)

    staged_files = {}

    if index_path.exists():
        for line in index_path.read_text().splitlines():
            parts = line.split(" ", 1)
            if len(parts) == 2:
                staged_files[parts[0]] = parts[1]

    # Add or update the file in the index
    staged_files[filename] = file_hash

    index_path.write_text(
        "".join(
            f"{name} {file_hash}\n"
            for name, file_hash in staged_files.items()
        )
    )

    print(f"Added '{filename}' to staging area.")
# =========================
# LOG
# =========================
def show_log():
    head_file = Path(".mygit/HEAD")
    if not head_file.exists():
        print("Repository not initialized.")
        return
    # Find the current branch
    head_content = head_file.read_text().strip()
    if not head_content.startswith("ref:"):
        print("Detached HEAD is not supported yet.")
        return
    branch_path = Path(".mygit") / head_content.split(":", 1)[1].strip()
    if not branch_path.exists():
        print("No commits yet.")
        return
    commit_hash = branch_path.read_text().strip()
    if not commit_hash:
        print("No commits yet.")
        return
    # Display commit history
    while commit_hash:
        object_file = Path(".mygit/objects") / commit_hash
        if not object_file.exists():
            print(f"Commit object not found: {commit_hash}")
            break
        commit_data = object_file.read_text(encoding="utf-8")
        message = ""
        author = "Unknown"
        email = "Unknown"
        date = "Unknown"
        parent = ""
        for line in commit_data.splitlines():
            if line.startswith("message:"):
                message = line.split(":", 1)[1].strip()
            elif line.startswith("author:"):
                author = line.split(":", 1)[1].strip()
            elif line.startswith("email:"):
                email = line.split(":", 1)[1].strip()
            elif line.startswith("date:"):
                date = line.split(":", 1)[1].strip()
            elif line.startswith("parent:"):
                parent = line.split(":", 1)[1].strip()
        print("--------------------------------")
        print(f"commit {commit_hash}")
        print(f"Author: {author} <{email}>")
        print(f"Date:   {date}")
        print(f"Message: {message}")
        commit_hash = parent
    print("--------------------------------")
# =========================
# DIFF
# =========================


def branch(name=None):
    heads_dir = Path(".mygit/refs/heads")
    heads_dir.mkdir(parents=True, exist_ok=True)

    current_branch, current_commit = get_head()

    # List branches
    if name is None:
        names = sorted(p.name for p in heads_dir.iterdir() if p.is_file())
        if not names:
            print("No branches yet.")
            return
        for branch_name in names:
            marker = "*" if branch_name == current_branch else " "
            print(f"{marker} {branch_name}")
        return

    # Create a new branch from the CURRENT commit
    if (".." in name or "\\" in name or "/" in name or name.startswith("-")):
        print(f"Invalid branch name: {name}")
        return

    new_branch = heads_dir / name
    if new_branch.exists():
        print(f"Branch '{name}' already exists.")
        return

    if not current_commit:
        print("No commits yet.")
        return

    atomic_write_text(new_branch, current_commit)
    print(f"Created branch '{name}' at {current_commit[:7]}")

def checkout_branch(branch_name):
    if merge_in_progress():
        return
    # 1. Check the branch name is safe
    if (not branch_name or ".." in branch_name
            or "\\" in branch_name or branch_name.startswith("/")):
        print(f"Invalid branch name: {branch_name}")
        return

    head_file = Path(".mygit/HEAD")
    target_ref = Path(".mygit/refs/heads") / branch_name
    objects_dir = Path(".mygit/objects")

    if not head_file.exists():
        print("Repository not initialized.")
        return
    if not target_ref.is_file():
        print(f"Branch '{branch_name}' does not exist.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot checkout: detached HEAD is not supported yet.")
        return
    if current_branch == branch_name:
        print(f"Already on '{branch_name}'.")
        return

    target_commit = target_ref.read_text(encoding="utf-8").strip()
    if not target_commit or not (objects_dir / target_commit).exists():
        print(f"Branch '{branch_name}' has no valid commit. Nothing changed.")
        return

    current_files = get_commit_files(current_commit) if current_commit else {}
    target_files = get_commit_files(target_commit)
    index_entries = read_index()

    # 2. Check every path and every file object BEFORE touching anything
    for filename in set(current_files) | set(target_files):
        try:
            normalize_path(filename)
        except ValueError as error:
            print(f"Unsafe path in commit: {error}. Nothing changed.")
            return
    for filename, file_hash in target_files.items():
        if not (objects_dir / file_hash).exists():
            print(f"Missing stored file for '{filename}'. Nothing changed.")
            return

    # 3. Protect your work
    problems = []
    for filename in sorted(set(index_entries) | set(current_files)):
        if index_entries.get(filename) != current_files.get(filename):
            problems.append(f"  staged change: {filename}")
    for filename, staged_hash in index_entries.items():
        path = Path(filename)
        if not path.is_file():
            problems.append(f"  deleted file: {filename}")
        elif hash_file(filename) != staged_hash:
            problems.append(f"  modified file: {filename}")
    for filename in target_files:
        if filename not in current_files and Path(filename).exists():
            problems.append(f"  untracked file would be overwritten: {filename}")

    if problems:
        print("Cannot switch branches. Your work could be lost:")
        for problem in problems:
            print(problem)
        print("Commit or restore these files, then try again.")
        return

    # 4. Work out what must change
    to_delete = [f for f in current_files if f not in target_files]
    to_write = [f for f, h in target_files.items() if current_files.get(f) != h]

    # 5. Save backups so we can roll back
    backups = {}
    for filename in to_delete + to_write:
        path = Path(filename)
        backups[filename] = path.read_bytes() if path.is_file() else None
    index_file = Path(".mygit/index")
    old_index_text = index_file.read_text(encoding="utf-8") if index_file.exists() else ""

    # 6. Do the checkout (HEAD moves last)
    try:
        for filename in to_delete:
            path = Path(filename)
            if path.is_file():
                path.unlink()
        for filename in to_write:
            path = Path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((objects_dir / target_files[filename]).read_bytes())
        write_index(target_files)
        atomic_write_text(head_file, f"ref: refs/heads/{branch_name}\n")
    except Exception as error:
        print(f"Checkout failed: {error}")
        print("Rolling back your files...")
        for filename, data in backups.items():
            path = Path(filename)
            try:
                if data is None:
                    if path.is_file():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            except OSError:
                print(f"  Could not restore: {filename}")
        atomic_write_text(index_file, old_index_text)
        atomic_write_text(head_file, f"ref: refs/heads/{current_branch}\n")
        print("Rollback finished. You are still on the old branch.")
        return

    print(f"Switched to branch '{branch_name}'")
    print(f"Files updated: {len(to_write)}, removed: {len(to_delete)}")

def merge_branch(branch_name):
    if merge_in_progress():
        return 
    if (not branch_name or ".." in branch_name
            or "\\" in branch_name or branch_name.startswith("/")):
        print(f"Invalid branch name: {branch_name}")
        return

    target_ref = Path(".mygit/refs/heads") / branch_name
    if not target_ref.is_file():
        # Not a local branch: try a remote-tracking branch such as origin/main
        target_ref = Path(".mygit/refs/remotes") / branch_name
    if not target_ref.is_file():
        print(f"Branch '{branch_name}' does not exist.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot merge: detached HEAD is not supported yet.")
        return
    if current_branch == branch_name:
        print("Cannot merge a branch into itself.")
        return

    target_commit = target_ref.read_text(encoding="utf-8").strip()
    if not target_commit or not is_commit_object(target_commit):
        print(f"Branch '{branch_name}' has no valid commit. Nothing changed.")
        return

    if current_commit == target_commit:
        print("Already up to date.")
        return

    base = find_merge_base(current_commit, target_commit) if current_commit else None
    if base == target_commit:
        print("Already up to date.")
        return

    # Fast-forward: the current branch is simply behind the other one
    if not current_commit or base == current_commit:
        old_files = get_commit_files(current_commit) if current_commit else {}
        new_files = get_commit_files(target_commit)
        current_ref = Path(".mygit/refs/heads") / current_branch

        def finish():
            atomic_write_text(current_ref, target_commit)

        if not update_working_tree(old_files, new_files, finish):
            print("Merge cancelled. Nothing changed.")
            return
        print(f"Merged '{branch_name}' into '{current_branch}' (fast-forward)")
        print(f"'{current_branch}' is now at {target_commit[:7]}")
        return

# Diverged: real three-way merge
    base_files = get_commit_files(base) if base else {}
    our_files = get_commit_files(current_commit)
    their_files = get_commit_files(target_commit)
    our_label = f"ours ({current_branch})"
    their_label = f"theirs ({branch_name})"

    merged_files = {}      # what the working folder will contain
    index_files = {}       # what the staging index will contain
    conflicts = []
    conflict_hashes = {}
    try:
        for filename in sorted(set(base_files) | set(our_files) | set(their_files)):
            normalize_path(filename)
            data, conflict = merge_one_file(
                base_files.get(filename), our_files.get(filename),
                their_files.get(filename), our_label, their_label)
            if data is None:
                continue
            new_hash = store_blob(data)
            merged_files[filename] = new_hash
            if conflict:
                conflicts.append(filename)
                conflict_hashes[filename] = new_hash
                if filename in our_files:
                    index_files[filename] = our_files[filename]
            else:
                index_files[filename] = new_hash
    except (ValueError, OSError) as error:
        print(f"Merge failed: {error}")
        print("Nothing was changed.")
        return

    touched = sorted(f for f in set(our_files) | set(merged_files)
                     if our_files.get(f) != merged_files.get(f))
    current_ref = Path(".mygit/refs/heads") / current_branch
    message = f"Merge branch '{branch_name}' into {current_branch}"
    result = {}

    def finish():
        if conflicts:
            atomic_write_text(".mygit/MERGE_FILES", "".join(f"{f}\n" for f in touched))
            atomic_write_text(".mygit/MERGE_CONFLICTS",
                              "".join(f"{f} {conflict_hashes[f]}\n" for f in conflicts))
            atomic_write_text(".mygit/MERGE_MSG", message + "\n")
            atomic_write_text(".mygit/MERGE_HEAD", target_commit + "\n")
        else:
            commit_hash = write_commit_object(
                message, merged_files, [current_commit, target_commit])
            atomic_write_text(current_ref, commit_hash)
            result["hash"] = commit_hash

    if not update_working_tree(our_files, merged_files, finish, index_files):
        print("Merge cancelled. Nothing changed.")
        return

    if conflicts:
        print("Automatic merge stopped: conflicts found in:")
        for filename in conflicts:
            print(f"  - {filename}")
        print("The merge is NOT finished. Your files now contain conflict markers.")
        print("Fix the files, then run:  python mygit.py merge --continue")
        print("Or cancel with:           python mygit.py merge --abort")
        return

    print(f"Merged '{branch_name}' into '{current_branch}' (three-way merge)")
    print(f"Merge commit: {result['hash'][:7]}")
    
def reset(commit_hash):
    if merge_in_progress():
        return
    heads_dir = Path(".mygit/refs/heads")

    head_file = Path(".mygit/HEAD")

    if not head_file.exists():
        print("HEAD does not exist.")
        return

    head_content = head_file.read_text().strip()

    if not head_content.startswith("ref:"):
        print("Invalid HEAD.")
        return

    current_branch = head_content.split("/")[-1]

    branch_file = heads_dir / current_branch

    if not branch_file.exists():
        print(f"Branch '{current_branch}' does not exist.")
        return

    # Check whether commit exists
    commit_file = Path(".mygit/objects") / commit_hash

    if not commit_file.exists():
        print(f"Commit '{commit_hash}' does not exist.")
        return

    # Move current branch to the selected commit
    branch_file.write_text(commit_hash)

    print(f"HEAD is now at {commit_hash}")
    print(f"Reset branch '{current_branch}' successfully.")


def restore(filename):
    if merge_in_progress():
        return
    heads_dir = Path(".mygit/refs/heads")
    head_file = Path(".mygit/HEAD")
    objects_dir = Path(".mygit/objects")

    # Check HEAD
    if not head_file.exists():
        print("No repository found.")
        return

    head_content = head_file.read_text().strip()

    if not head_content.startswith("ref:"):
        print("Invalid HEAD.")
        return

    # Get current branch
    current_branch = head_content.split("/")[-1]

    # Get current commit
    branch_file = heads_dir / current_branch

    if not branch_file.exists():
        print("Current branch does not exist.")
        return

    commit_hash = branch_file.read_text().strip()

    if not commit_hash:
        print("No commits yet.")
        return

    # Read commit object
    commit_file = objects_dir / commit_hash

    if not commit_file.exists():
        print("Commit object not found.")
        return

    commit_content = commit_file.read_text()

    # Commit contains metadata + index
    parts = commit_content.split("\n\n", 1)

    if len(parts) < 2:
        print("Invalid commit format.")
        return

    committed_index = parts[1]

    # Find the requested file
    file_hash = None

    for line in committed_index.splitlines():
        line = line.strip()

        if not line:
            continue

        file_parts = line.split(maxsplit=1)

        if len(file_parts) == 2:
            saved_filename, saved_hash = file_parts

            if saved_filename == filename:
                file_hash = saved_hash
                break

    if file_hash is None:
        print(f"File '{filename}' was not found in the commit.")
        return

    # Find the stored file object
    object_file = objects_dir / file_hash

    if not object_file.exists():
        print("File object not found.")
        return

    # Restore file contents
    file_path = Path(filename)
    file_path.write_bytes(object_file.read_bytes())

    print(f"Restored '{filename}' successfully.")

def remove_file(filename):
    if merge_in_progress():
            return
    file_path = Path(filename)
    index_file = Path(".mygit/index")

    if not file_path.exists():
        print(f"File '{filename}' does not exist.")
        return

    # Remove file from working directory
    file_path.unlink()

    # Remove file from index
    if index_file.exists():
        lines = index_file.read_text().splitlines()

        new_lines = []

        for line in lines:
            parts = line.split(maxsplit=1)

            if len(parts) == 2 and parts[0] == filename:
                continue

            new_lines.append(line)

        index_file.write_text(
            "\n".join(new_lines) + ("\n" if new_lines else "")
        )

    print(f"Removed '{filename}'")

def show_commit(commit_hash):
    object_file = Path(".mygit/objects") / commit_hash
    if not object_file.exists():
        print(f"Error: Commit '{commit_hash}' not found.")
        return
    commit_data = object_file.read_text(encoding="utf-8")
    # Separate commit metadata from file information
    parts = commit_data.split("\n\n", 1)
    if len(parts) != 2:
        print("Error: Invalid commit format.")
        return
    metadata = parts[0]
    file_data = parts[1]
    message = ""
    author = "Unknown"
    email = "Unknown"
    date = "Unknown"
    parent = ""
    # Read commit metadata
    for line in metadata.splitlines():
        if line.startswith("message:"):
            message = line.split(":", 1)[1].strip()
        elif line.startswith("author:"):
            author = line.split(":", 1)[1].strip()
        elif line.startswith("email:"):
            email = line.split(":", 1)[1].strip()
        elif line.startswith("date:"):
            date = line.split(":", 1)[1].strip()
        elif line.startswith("parent:"):
            parent = line.split(":", 1)[1].strip()
    print("================================")
    print("          COMMIT DETAILS")
    print("================================")
    print(f"Commit:  {commit_hash}")
    print(f"Author:  {author}")
    print(f"Email:   {email}")
    print(f"Date:    {date}")
    print(f"Message: {message}")
    print(f"Parent:  {parent if parent else '(Initial commit)'}")
    print("\nFiles in this commit:")
    print("--------------------------------")
    found_files = False
    for line in file_data.splitlines():
        parts = line.split(" ", 1)
        if len(parts) == 2:
            filename, file_hash = parts
            print(f"File: {filename}")
            print(f"Hash: {file_hash}")
            print()
            found_files = True
    if not found_files:
        print("No file entries found.")
    print("================================")

def create_tag(tag_name):
    if merge_in_progress():
            return
    head_file = Path(".mygit/HEAD")
    heads_dir = Path(".mygit/refs/heads")
    tags_dir = Path(".mygit/refs/tags")

    if not head_file.exists():
        print("No repository found.")
        return

    head_content = head_file.read_text().strip()

    if not head_content.startswith("ref:"):
        print("Invalid HEAD.")
        return

    current_branch = head_content.split("/")[-1]

    branch_file = heads_dir / current_branch

    if not branch_file.exists():
        print("Current branch does not exist.")
        return

    commit_hash = branch_file.read_text().strip()

    if not commit_hash:
        print("No commits yet.")
        return

    tags_dir.mkdir(parents=True, exist_ok=True)

    tag_file = tags_dir / tag_name
    tag_file.write_text(commit_hash)

    print(f"Tag '{tag_name}' created successfully.")
    print(f"Commit: {commit_hash}")

def list_tags():
    tags_dir = Path(".mygit/refs/tags")

    if not tags_dir.exists():
        print("No tags found.")
        return

    tags = list(tags_dir.iterdir())

    if not tags:
        print("No tags found.")
        return

    print("Tags:")

    for tag in tags:
        print(tag.name)


def revert_commit(commit_hash):
    if merge_in_progress():
        return
    picked = resolve_commit(commit_hash)
    if picked is None or not is_commit_object(picked):
        print(f"'{commit_hash}' is not a valid commit. Nothing changed.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None or not current_commit:
        print("Cannot revert: you need a branch with commits (not detached HEAD).")
        return

    parents = read_commit_parents(picked)
    if len(parents) != 1:
        print("Cannot revert this commit (only commits with exactly one parent are supported).")
        print("Nothing changed.")
        return

    parent_files = get_commit_files(parents[0])
    picked_files = get_commit_files(picked)
    our_files = get_commit_files(current_commit)

    # Undo the change: base = the picked commit, theirs = its parent
    merged_files = {}
    conflicts = []
    try:
        for filename in sorted(set(parent_files) | set(picked_files) | set(our_files)):
            normalize_path(filename)
            data, conflict = merge_one_file(
                picked_files.get(filename), our_files.get(filename),
                parent_files.get(filename), "current", f"revert ({picked[:7]})")
            if conflict:
                conflicts.append(filename)
            elif data is not None:
                merged_files[filename] = store_blob(data)
    except (ValueError, OSError) as error:
        print(f"Revert failed: {error}. Nothing changed.")
        return

    if conflicts:
        print("Revert refused: it would conflict with your current files:")
        for filename in conflicts:
            print(f"  - {filename}")
        print("Nothing was changed.")
        return

    if merged_files == our_files:
        print("Nothing to revert: those changes are not in your branch.")
        return

    info = read_commit_info(picked)
    message = f'Revert "{info["message"]}"'
    current_ref = Path(".mygit/refs/heads") / current_branch
    result = {}

    def finish():
        new_hash = write_commit_object(message, merged_files, [current_commit])
        atomic_write_text(current_ref, new_hash)
        result["hash"] = new_hash

    if not update_working_tree(our_files, merged_files, finish):
        print("Revert cancelled. Nothing changed.")
        return

    print(f"Reverted commit {picked[:7]} on '{current_branch}'.")
    print(f"New commit: {result['hash'][:7]}")

def delete_branch(branch_name):
    if merge_in_progress():
            return
    heads_dir = Path(".mygit/refs/heads")
    head_file = Path(".mygit/HEAD")

    # Check if repository exists
    if not heads_dir.exists() or not head_file.exists():
        print("No repository found.")
        return

    # Check if branch exists
    branch_file = heads_dir / branch_name

    if not branch_file.exists():
        print(f"Branch '{branch_name}' does not exist.")
        return

    # Find current branch
    head_content = head_file.read_text().strip()

    if not head_content.startswith("ref:"):
        print("Invalid HEAD.")
        return

    current_branch = head_content.split("/")[-1]

    # Don't allow deleting current branch
    if current_branch == branch_name:
        print("Cannot delete the current branch.")
        return

    # Delete branch reference
    branch_file.unlink()

    print(f"Deleted branch '{branch_name}'")

def get_commit_files(commit_hash):
    objects_dir = Path(".mygit/objects")
    commit_file = objects_dir / commit_hash

    if not commit_file.exists():
        return {}

    content = commit_file.read_text()
    parts = content.split("\n\n", 1)

    if len(parts) < 2:
        return {}

    files = {}

    for line in parts[1].splitlines():
        parts_line = line.split(maxsplit=1)

        if len(parts_line) == 2:
            filename, file_hash = parts_line
            files[filename] = file_hash

    return files

def is_ignored(filename):
    ignore_file = Path(".gitignore")

    if not ignore_file.exists():
        return False
    
    path = Path(filename)

    try:
        relative_path = path.as_posix()
    except Exception:
        relative_path = str(filename)

    rules = ignore_file.read_text(encoding="utf-8").splitlines()

    for rule in rules:
        rule = rule.strip()

        # Skip blank lines and comments
        if not rule or rule.startswith("#"):
            continue

        # Ignore directories ending with /
        if rule.endswith("/"):
            directory = rule.rstrip("/")

            if directory in path.parts:
                return True

        # Match file patterns
        elif fnmatch.fnmatch(path.name, rule):
            return True

        # Match a path written relative to the project
        elif "/" in rule and fnmatch.fnmatch(relative_path, rule):
            return True

    return False

# =========================
# SHARED HELPERS
# =========================
def atomic_write_text(path, text):
    """Write to a temp file first, then swap it in. Also records branch and HEAD moves."""
    path = Path(path)
    old_text = None
    if path.is_file():
        try:
            old_text = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeDecodeError):
            old_text = None
    temp_path = path.with_name(path.name + ".tmp")
    temp_path.write_text(text, encoding="utf-8", newline="\n")
    os.replace(temp_path, path)
    record_if_ref_moved(path, old_text, text.strip())


def normalize_path(filename):
    """Return a safe repo-relative path like 'src/a.txt' (works for src\\a.txt too)."""
    root = Path.cwd().resolve()
    resolved = (root / filename).resolve()
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        raise ValueError(f"Path is outside the repository: {filename}")
    if ".mygit" in relative.parts:
        raise ValueError(f"Path is inside .mygit: {filename}")
    return relative.as_posix()


def read_index():
    """Return the staging index as {filename: hash}."""
    index_file = Path(".mygit/index")
    entries = {}
    if index_file.exists():
        for line in index_file.read_text(encoding="utf-8").splitlines():
            parts = line.rsplit(" ", 1)
            if len(parts) == 2 and parts[0]:
                entries[parts[0]] = parts[1]
    return entries


def write_index(entries):
    """Save {filename: hash} to the index safely."""
    text = "".join(
        f"{filename} {file_hash}\n"
        for filename, file_hash in sorted(entries.items())
    )
    atomic_write_text(".mygit/index", text)


def get_head():
    """Return (branch_name, commit_hash). branch_name is None if HEAD is detached."""
    head_file = Path(".mygit/HEAD")
    if not head_file.exists():
        return None, ""
    content = head_file.read_text(encoding="utf-8").strip()
    if content.startswith("ref:"):
        ref = content.split(":", 1)[1].strip()
        ref_file = Path(".mygit") / ref
        commit = ""
        if ref_file.exists():
            commit = ref_file.read_text(encoding="utf-8").strip()
        # During a rebase, the "current commit" is the rebased tip, not the branch file
        rebase_tip = Path(".mygit/REBASE_TIP")
        if rebase_tip.exists():
            commit = rebase_tip.read_text(encoding="utf-8").strip()
        return ref.replace("refs/heads/", "", 1), commit
    return None, content

def read_config():
    """Return the settings in .mygit/config as {key: value}."""
    config_file = Path(".mygit/config")
    settings = {}
    if config_file.exists():
        for line in config_file.read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, value = line.split("=", 1)
                settings[key.strip()] = value.strip()
    return settings


def write_config(settings):
    text = "".join(f"{key} = {value}\n" for key, value in sorted(settings.items()))
    atomic_write_text(".mygit/config", text)


def validate_config_value(key, value):
    """Return an error message, or None if the value is fine."""
    if not value:
        return "Value cannot be empty."
    if any(ch in value for ch in "\r\n\t"):
        return "Value cannot contain new lines or tabs."
    if len(value) > 100:
        return "Value is too long (maximum 100 characters)."
    if key == "user.name" and ("<" in value or ">" in value):
        return "Name cannot contain < or >."
    if key == "user.email":
        local, _, domain = value.partition("@")
        if (not local or " " in value or "." not in domain
                or domain.startswith(".") or domain.endswith(".")):
            return "Invalid email. Example: you@example.com"
    return None

DEFAULT_NAME = "MyGit User"
DEFAULT_EMAIL = "mygit@example.com"


def get_identity():
    """Return (name, email) for new commits, using defaults if not configured."""
    settings = read_config()
    return (settings.get("user.name", DEFAULT_NAME),
            settings.get("user.email", DEFAULT_EMAIL))


def config_command(args):
    if not Path(".mygit").exists():
        print("Repository not initialized.")
        return
    if not args:
        print('Usage: python mygit.py config user.name "Your Name"')
        print('       python mygit.py config user.email "you@example.com"')
        print("       python mygit.py config --list")
        return

    settings = read_config()

    if args[0] == "--list":
        if not settings:
            print("No configuration set.")
        for key, value in sorted(settings.items()):
            print(f"{key} = {value}")
        return
    key = args[0]
    if key not in ("user.name", "user.email"):
        print(f"Unknown setting: {key}")
        print("Supported settings: user.name, user.email")
        return

    if len(args) == 1:
        print(settings.get(key, f"{key} is not set."))
        return

    value = " ".join(args[1:]).strip()
    error = validate_config_value(key, value)
    if error:
        print(f"Error: {error}")
        return

    settings[key] = value
    write_config(settings)
    print(f"Set {key} = {value}")

# =========================
# DIFF (line by line)
# =========================
def is_commit_object(object_hash):
    path = Path(".mygit/objects") / object_hash
    if not path.is_file():
        return False
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return False
    return text.startswith("message:") and "\nparent:" in text


def resolve_commit(name):
    """Turn a branch, tag, or commit hash (or its start) into a full commit hash.
    Annotated tags are followed to the commit they point to."""
    if name and ".." not in name and "\\" not in name and not name.startswith("/"):
        for folder in ("refs/heads", "refs/tags", "refs/remotes"):
            ref = Path(".mygit") / folder / name
            if ref.is_file():
                value = ref.read_text(encoding="utf-8").strip()
                if value:
                    return peel_tag(value)
    name = name.lower()
    objects_dir = Path(".mygit/objects")
    if len(name) >= 4 and objects_dir.exists() and all(c in "0123456789abcdef" for c in name):
        matches = [p.name for p in objects_dir.iterdir()
                   if p.name.startswith(name) and is_commit_object(p.name)]
        if len(matches) == 1:
            return matches[0]
    return None


def decode_lines(data):
    """Bytes -> list of lines, or None if the file is not text."""
    try:
        return data.decode("utf-8-sig").splitlines()
    except UnicodeDecodeError:
        return None


def side_hash(side, filename):
    kind, files = side
    if kind == "working":
        return hash_file(filename) if Path(filename).is_file() else None
    return files.get(filename)


def side_lines(side, filename):
    """Return (exists, lines). lines is None for binary or unreadable files."""
    kind, files = side
    if kind == "working":
        path = Path(filename)
        if not path.is_file():
            return False, []
        return True, decode_lines(path.read_bytes())
    file_hash = files.get(filename)
    if file_hash is None:
        return False, []
    blob = Path(".mygit/objects") / file_hash
    if not blob.is_file():
        return True, None
    return True, decode_lines(blob.read_bytes())


def show_file_diff(filename, old_side, new_side):
    old_exists, old_lines = side_lines(old_side, filename)
    new_exists, new_lines = side_lines(new_side, filename)
    print(f"\n=== {filename} ===")
    if old_lines is None or new_lines is None:
        print("(binary or unreadable file: line diff not shown)")
        return
    diff = list(difflib.unified_diff(
        old_lines, new_lines,
        fromfile=f"a/{filename}" if old_exists else "/dev/null",
        tofile=f"b/{filename}" if new_exists else "/dev/null",
        lineterm="",
    ))
    if not diff:
        print("(content differs, but no visible line changes - maybe line endings)")
        return
    for line in diff:
        print(line)


def diff_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return

    staged = False
    head_mode = False
    rest = []
    for arg in args:
        if arg in ("--staged", "--cached"):
            staged = True
        elif arg == "--head":
            head_mode = True
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            return
        else:
            rest.append(arg)

    _, head_commit = get_head()
    head_files = get_commit_files(head_commit) if head_commit else {}
    index_files = read_index()

    first = resolve_commit(rest[0]) if rest else None
    second = resolve_commit(rest[1]) if len(rest) > 1 else None

    if first and (staged or head_mode):
        print("Do not combine --staged or --head with a commit name.")
        return

    if first and second:
        old_side = ("files", get_commit_files(first))
        new_side = ("files", get_commit_files(second))
        title = f"commit {first[:7]} -> commit {second[:7]}"
        wanted = rest[2] if len(rest) > 2 else None
        candidates = set(old_side[1]) | set(new_side[1])
    elif first:
        old_side = ("files", get_commit_files(first))
        new_side = ("working", None)
        title = f"commit {first[:7]} -> working files"
        wanted = rest[1] if len(rest) > 1 else None
        candidates = set(old_side[1]) | set(index_files)
    else:
        wanted = rest[0] if rest else None
        if staged:
            old_side = ("files", head_files)
            new_side = ("files", index_files)
            title = "last commit -> staged (index)"
            candidates = set(head_files) | set(index_files)
        elif head_mode:
            old_side = ("files", head_files)
            new_side = ("working", None)
            title = "last commit -> working files"
            candidates = set(head_files) | set(index_files)
        else:
            old_side = ("files", index_files)
            new_side = ("working", None)
            title = "staged (index) -> working files (unstaged changes)"
            candidates = set(index_files)

    if wanted:
        try:
            wanted = normalize_path(wanted)
        except ValueError as error:
            print(f"Error: {error}")
            return
        if wanted not in candidates:
            print(f"'{wanted}' is not a tracked file, branch, tag, or commit.")
            return
        candidates = {wanted}

    print(f"Comparing: {title}")
    changed = 0
    for filename in sorted(candidates):
        if side_hash(old_side, filename) == side_hash(new_side, filename):
            continue
        show_file_diff(filename, old_side, new_side)
        changed += 1

    if changed == 0:
        print("No differences.")
    else:
        print(f"\n{changed} file(s) with differences.")


# =========================
# MERGE HELPERS
# =========================
def read_commit_parents(commit_hash):
    """Return the parent hashes of a commit (0, 1 or 2 of them)."""
    path = Path(".mygit/objects") / commit_hash
    if not path.is_file():
        return []
    parents = []
    metadata = path.read_text(encoding="utf-8").split("\n\n", 1)[0]
    for line in metadata.splitlines():
        if line.startswith("parent:") or line.startswith("parent2:"):
            value = line.split(":", 1)[1].strip()
            if value:
                parents.append(value)
    return parents


def get_ancestors(commit_hash):
    """Return {commit: distance} for a commit and every commit before it."""
    seen = {}
    queue = [(commit_hash, 0)]
    while queue:
        current, distance = queue.pop(0)
        if current in seen:
            continue
        seen[current] = distance
        for parent in read_commit_parents(current):
            queue.append((parent, distance + 1))
    return seen


def find_merge_base(commit_a, commit_b):
    """Return the closest commit that both histories share, or None."""
    ancestors_a = get_ancestors(commit_a)
    ancestors_b = get_ancestors(commit_b)
    common = set(ancestors_a) & set(ancestors_b)
    if not common:
        return None
    history = {c: get_ancestors(c) for c in common}
    best = [c for c in common
            if not any(c != other and c in history[other] for other in common)]
    return min(best, key=lambda c: ancestors_a[c] + ancestors_b[c])


def update_working_tree(old_files, new_files, finish, index_files=None):
    """Change the working files and index from old_files to new_files.
    'finish' runs last (it moves the branch). Rolls back if anything fails.
    Returns True on success, False if nothing was changed."""
    objects_dir = Path(".mygit/objects")
    index_entries = read_index()

    for filename in set(old_files) | set(new_files):
        try:
            normalize_path(filename)
        except ValueError as error:
            print(f"Unsafe path in commit: {error}. Nothing changed.")
            return False
    for filename, file_hash in new_files.items():
        if not (objects_dir / file_hash).exists():
            print(f"Missing stored file for '{filename}'. Nothing changed.")
            return False

    problems = []
    for filename in sorted(set(index_entries) | set(old_files)):
        if index_entries.get(filename) != old_files.get(filename):
            problems.append(f"  staged change: {filename}")
    for filename, staged_hash in index_entries.items():
        path = Path(filename)
        if not path.is_file():
            problems.append(f"  deleted file: {filename}")
        elif hash_file(filename) != staged_hash:
            problems.append(f"  modified file: {filename}")
    for filename in new_files:
        if filename not in old_files and Path(filename).exists():
            problems.append(f"  untracked file would be overwritten: {filename}")
    if problems:
        print("Your work could be lost, so nothing was changed:")
        for problem in problems:
            print(problem)
        return False

    to_delete = [f for f in old_files if f not in new_files]
    to_write = [f for f, h in new_files.items() if old_files.get(f) != h]

    backups = {}
    for filename in to_delete + to_write:
        path = Path(filename)
        backups[filename] = path.read_bytes() if path.is_file() else None
    index_file = Path(".mygit/index")
    old_index_text = index_file.read_text(encoding="utf-8") if index_file.exists() else ""

    try:
        for filename in to_delete:
            path = Path(filename)
            if path.is_file():
                path.unlink()
        for filename in to_write:
            path = Path(filename)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((objects_dir / new_files[filename]).read_bytes())
        write_index(index_files if index_files is not None else new_files)
        finish()
    except Exception as error:
        print(f"Operation failed: {error}")
        print("Rolling back your files...")
        for filename, data in backups.items():
            path = Path(filename)
            try:
                if data is None:
                    if path.is_file():
                        path.unlink()
                else:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(data)
            except OSError:
                print(f"  Could not restore: {filename}")
        atomic_write_text(index_file, old_index_text)
        print("Rollback finished.")
        return False
    return True

def store_blob(data):
    """Save file bytes as an object and return its hash."""
    file_hash = hashlib.sha1(data).hexdigest()
    path = Path(".mygit/objects") / file_hash
    if not path.exists():
        path.write_bytes(data)
    return file_hash


def read_blob(file_hash):
    if file_hash is None:
        return None
    return (Path(".mygit/objects") / file_hash).read_bytes()


def write_commit_object(message, files, parents, author=None, email=None):
    """Create a commit object. parents has 1 hash, or 2 for a merge commit."""
    if not author or not email:
        author, email = get_identity()
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    message = message.replace("\r", " ").replace("\n", " ")
    lines = [
        f"message: {message}",
        f"author: {author}",
        f"email: {email}",
        f"date: {date}",
        f"parent: {parents[0] if parents else ''}",
    ]
    if len(parents) > 1:
        lines.append(f"parent2: {parents[1]}")
    snapshot = "".join(f"{name} {h}\n" for name, h in sorted(files.items()))
    commit_data = "\n".join(lines) + "\n\n" + snapshot
    commit_hash = hashlib.sha1(commit_data.encode("utf-8")).hexdigest()
    atomic_write_text(Path(".mygit/objects") / commit_hash, commit_data)
    return commit_hash


def merge_lines(base, ours, theirs, our_label, their_label):
    """Three-way merge of line lists. Returns (merged_lines, conflict_count)."""
    def changes(side):
        matcher = difflib.SequenceMatcher(None, base, side, autojunk=False)
        return [(i1, i2, side[j1:j2])
                for tag, i1, i2, j1, j2 in matcher.get_opcodes() if tag != "equal"]

    def apply(group, start, end):
        out = []
        cursor = start
        for i1, i2, replacement in group:
            out.extend(base[cursor:i1])
            out.extend(replacement)
            cursor = i2
        out.extend(base[cursor:end])
        return out

    our_changes = changes(ours)
    their_changes = changes(theirs)
    merged = []
    conflicts = 0
    position = 0
    oi = ti = 0

    while oi < len(our_changes) or ti < len(their_changes):
        o = our_changes[oi] if oi < len(our_changes) else None
        t = their_changes[ti] if ti < len(their_changes) else None
        first = o if (t is None or (o is not None and o[0] <= t[0])) else t
        start, end = first[0], first[1]
        our_group, their_group = [], []
        grew = True
        while grew:
            grew = False
            while oi < len(our_changes) and our_changes[oi][0] <= end:
                our_group.append(our_changes[oi])
                end = max(end, our_changes[oi][1])
                oi += 1
                grew = True
            while ti < len(their_changes) and their_changes[ti][0] <= end:
                their_group.append(their_changes[ti])
                end = max(end, their_changes[ti][1])
                ti += 1
                grew = True
        merged.extend(base[position:start])
        if our_group and not their_group:
            merged.extend(apply(our_group, start, end))
        elif their_group and not our_group:
            merged.extend(apply(their_group, start, end))
        else:
            our_text = apply(our_group, start, end)
            their_text = apply(their_group, start, end)
            if our_text == their_text:
                merged.extend(our_text)
            else:
                conflicts += 1
                merged.append(f"<<<<<<< {our_label}")
                merged.extend(our_text)
                merged.append("=======")
                merged.extend(their_text)
                merged.append(f">>>>>>> {their_label}")
        position = end
    merged.extend(base[position:])
    return merged, conflicts


def merge_one_file(base_hash, ours_hash, theirs_hash, our_label, their_label):
    """Return (data, conflict). data is bytes, or None if the file is deleted."""
    if ours_hash == theirs_hash:
        return read_blob(ours_hash), False
    if base_hash == ours_hash:
        return read_blob(theirs_hash), False
    if base_hash == theirs_hash:
        return read_blob(ours_hash), False

    # Both branches changed this file in different ways
    if ours_hash is None or theirs_hash is None:
        return read_blob(ours_hash or theirs_hash), True   # modified vs deleted

    ours_bytes = read_blob(ours_hash)
    theirs_bytes = read_blob(theirs_hash)
    base_lines = decode_lines(read_blob(base_hash) or b"")
    ours_lines = decode_lines(ours_bytes)
    theirs_lines = decode_lines(theirs_bytes)
    if base_lines is None or ours_lines is None or theirs_lines is None:
        return ours_bytes, True                            # binary file

    merged, conflicts = merge_lines(base_lines, ours_lines, theirs_lines,
                                    our_label, their_label)
    newline = "\r\n" if b"\r\n" in ours_bytes else "\n"
    text = newline.join(merged) + (newline if merged else "")
    data = text.encode("utf-8")
    if ours_bytes.startswith(b"\xef\xbb\xbf"):
        data = b"\xef\xbb\xbf" + data
    return data, conflicts > 0

MERGE_STATE_FILES = ("MERGE_HEAD", "MERGE_MSG", "MERGE_CONFLICTS", "MERGE_FILES","MERGE_KIND","MERGE_AUTHOR")


def merge_in_progress():
    """Return True (and print help) if a merge, cherry-pick or rebase is waiting."""
    if not Path(".mygit/MERGE_HEAD").exists():
        return False
    if merge_kind() == "rebase":
        print("A rebase is in progress.")
        print("Finish it:  python mygit.py rebase --continue")
        print("Cancel it:  python mygit.py rebase --abort")
        return True
    print("A merge is in progress.")
    print("Finish it:  python mygit.py merge --continue")
    print("Cancel it:  python mygit.py merge --abort")
    return True

def clear_merge_state():
    for name in MERGE_STATE_FILES:
        path = Path(".mygit") / name
        if path.exists():
            path.unlink()


def read_state_lines(name):
    path = Path(".mygit") / name
    if not path.exists():
        return []
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def has_conflict_markers(filename):
    path = Path(filename)
    if not path.is_file():
        return False
    lines = decode_lines(path.read_bytes())
    if lines is None:
        return False
    has_start = any(line.startswith("<<<<<<< ") for line in lines)
    has_end = any(line.startswith(">>>>>>> ") for line in lines)
    return has_start and has_end


def merge_abort():
    if merge_kind() == "rebase":
        rebase_abort()
        return
    if not Path(".mygit/MERGE_HEAD").exists():
        print("No merge in progress. Nothing to abort.")
        return

    current_branch, current_commit = get_head()
    head_files = get_commit_files(current_commit) if current_commit else {}
    touched = read_state_lines("MERGE_FILES")
    objects_dir = Path(".mygit/objects")

    # Check everything first, so we never stop halfway
    for filename in touched:
        try:
            normalize_path(filename)
        except ValueError as error:
            print(f"Unsafe path in merge state: {error}. Nothing changed.")
            return
        file_hash = head_files.get(filename)
        if file_hash and not (objects_dir / file_hash).exists():
            print(f"Missing stored file for '{filename}'. Nothing changed.")
            return

    try:
        index_entries = read_index()
        for filename in touched:
            path = Path(filename)
            file_hash = head_files.get(filename)
            if file_hash:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes((objects_dir / file_hash).read_bytes())
                index_entries[filename] = file_hash
            else:
                if path.is_file():
                    path.unlink()
                index_entries.pop(filename, None)
        write_index(index_entries)
        clear_merge_state()
    except OSError as error:
        print(f"Abort stopped: {error}")
        print("Run 'python mygit.py merge --abort' again to finish it.")
        return

    print(f"{operation_name()} aborted.  Your branch is back to how it was before the {operation_name().lower()}.")
    for filename in touched:
        print(f"  restored: {filename}")


def merge_continue():
    merge_head_file = Path(".mygit/MERGE_HEAD")
    if not merge_head_file.exists():
        print("No merge in progress.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot continue: detached HEAD is not supported yet.")
        return
    merge_head = merge_head_file.read_text(encoding="utf-8").strip()
    if not is_commit_object(merge_head):
        print("The merge state is damaged (incoming commit not found).")
        print("Run: python mygit.py merge --abort")
        return

    final_files = read_index()
    unresolved = []
    try:
        for line in read_state_lines("MERGE_CONFLICTS"):
            filename, recorded_hash = line.rsplit(" ", 1)
            normalize_path(filename)
            path = Path(filename)
            if not path.is_file():
                final_files.pop(filename, None)      # resolved by deleting the file
            elif has_conflict_markers(filename) or hash_file(filename) == recorded_hash:
                unresolved.append(filename)
            else:
                final_files[filename] = store_blob(path.read_bytes())
    except (ValueError, OSError) as error:
        print(f"Cannot continue: {error}")
        return

    if unresolved:
        print("Cannot finish the merge. These files are still unresolved:")
        for filename in unresolved:
            print(f"  - {filename}")
        print("Edit each file (remove the <<<<<<<, =======, >>>>>>> lines), save,")
        print("then run: python mygit.py merge --continue")
        return

    message = " ".join(read_state_lines("MERGE_MSG")) or "Merge commit"
    kind = merge_kind()
    if kind == "rebase":
        rebase_step_done(final_files)
        return
    
    if kind == "cherry-pick":
        parents = [current_commit]
        author_lines = read_state_lines("MERGE_AUTHOR")
        author = author_lines[0] if len(author_lines) == 2 else None
        email = author_lines[1] if len(author_lines) == 2 else None
    else:
        parents = [current_commit, merge_head]
        author = email = None
    try:
        commit_hash = write_commit_object(
            message, final_files, parents, author, email)
        write_index(final_files)
        atomic_write_text(Path(".mygit/refs/heads") / current_branch, commit_hash)
        clear_merge_state()
    except OSError as error:
        print(f"Could not finish the merge: {error}")
        print("Your files were not lost. Fix the problem and run merge --continue again.")
        return

    if kind == "cherry-pick":
        print("Cherry-pick completed.")
        print(f"New commit: {commit_hash[:7]}")
    else:
        print("Merge completed.")
        print(f"Merge commit: {commit_hash[:7]}")

# =========================
# CONFLICT TOOLS
# =========================
def read_conflict_entries():
    """Return {filename: hash the file had when the merge stopped}."""
    entries = {}
    for line in read_state_lines("MERGE_CONFLICTS"):
        filename, _, recorded_hash = line.rpartition(" ")
        if filename:
            entries[filename] = recorded_hash
    return entries


def write_conflict_entries(entries):
    text = "".join(f"{name} {h}\n" for name, h in sorted(entries.items()))
    atomic_write_text(".mygit/MERGE_CONFLICTS", text)


def show_conflict_blocks(filename):
    path = Path(filename)
    if not path.is_file():
        print(f"'{filename}' does not exist in your folder.")
        return
    lines = decode_lines(path.read_bytes())
    if lines is None:
        print("This is a binary file, so there are no conflict markers to show.")
        return
    inside = False
    count = 0
    for number, line in enumerate(lines, start=1):
        if line.startswith("<<<<<<< "):
            inside = True
            count += 1
            print(f"--- conflict {count} ---")
        if inside:
            print(f"{number:4}: {line}")
        if line.startswith(">>>>>>> "):
            inside = False
    if count == 0:
        print("No conflict markers found in this file.")


def conflicts_command(args):
    if not Path(".mygit/MERGE_HEAD").exists():
        print("No merge in progress. There are no conflicts.")
        return
    entries = read_conflict_entries()

    if args:                                   # conflicts <file>
        try:
            filename = normalize_path(args[0])
        except ValueError as error:
            print(f"Error: {error}")
            return
        if filename not in entries:
            print(f"'{filename}' is not an unresolved conflict.")
            return
        show_conflict_blocks(filename)
        return

    if not entries:
        print("All conflicts are resolved.")
        print("Finish the merge with: python mygit.py merge --continue")
        return

    print("Conflicted files:")
    for filename, recorded_hash in sorted(entries.items()):
        path = Path(filename)
        if not path.is_file():
            note = "file deleted - run 'resolve --mark' to accept the deletion"
        elif has_conflict_markers(filename):
            note = "still has conflict markers"
        elif hash_file(filename) == recorded_hash:
            note = "not edited yet"
        else:
            note = "edited, no markers - run 'resolve --mark' to confirm"
        print(f"  {filename}  ({note})")
    print("Show markers:  python mygit.py conflicts <file>")
    print("Resolve:       python mygit.py resolve --ours|--theirs|--mark <file>")


def resolve_command(args):
    if not Path(".mygit/MERGE_HEAD").exists():
        print("No merge in progress. Nothing to resolve.")
        return

    force = "--force" in args
    args = [a for a in args if a != "--force"]
    if len(args) != 2 or args[0] not in ("--ours", "--theirs", "--mark"):
        print("Usage: python mygit.py resolve --ours <file> [--force]")
        print("       python mygit.py resolve --theirs <file> [--force]")
        print("       python mygit.py resolve --mark <file>")
        return
    option, name = args

    try:
        filename = normalize_path(name)
    except ValueError as error:
        print(f"Error: {error}")
        return

    entries = read_conflict_entries()
    if filename not in entries:
        print(f"'{filename}' is not an unresolved conflict.")
        print("See the list with: python mygit.py conflicts")
        return

    path = Path(filename)
    index_entries = read_index()

    if option == "--mark":
        if path.is_file():
            if has_conflict_markers(filename):
                print(f"'{filename}' still has conflict markers. Edit it first.")
                print("Nothing changed.")
                return
            try:
                index_entries[filename] = store_blob(path.read_bytes())
            except OSError as error:
                print(f"Error: {error}")
                return
        else:
            index_entries.pop(filename, None)          # you deleted the file
        message = f"Marked '{filename}' as resolved."
    else:
        _, current_commit = get_head()
        merge_head = Path(".mygit/MERGE_HEAD").read_text(encoding="utf-8").strip()
        if option == "--ours":
            chosen = get_commit_files(current_commit).get(filename)
        else:
            chosen = get_commit_files(merge_head).get(filename)

        # Never silently throw away your own edits
        if path.is_file() and hash_file(filename) != entries[filename] and not force:
            print(f"'{filename}' has been edited by you since the merge stopped.")
            print("Nothing changed. Use --force to overwrite your edits,")
            print(f"or run: python mygit.py resolve --mark {filename}")
            return
        try:
            if chosen is None:
                if path.is_file():
                    path.unlink()
                index_entries.pop(filename, None)
            else:
                data = read_blob(chosen)
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                index_entries[filename] = chosen
        except OSError as error:
            print(f"Error: {error}. Nothing was marked as resolved.")
            return
        side = "your branch's" if option == "--ours" else "the incoming branch's"
        message = f"Resolved '{filename}' using {side} version."

    del entries[filename]
    try:
        write_index(index_entries)
        write_conflict_entries(entries)
    except OSError as error:
        print(f"Error saving: {error}")
        print(f"Run: python mygit.py resolve --mark {filename}")
        return

    print(message)
    if entries:
        print(f"{len(entries)} conflict(s) left.")
    else:
        print("All conflicts resolved. Run: python mygit.py merge --continue")

# =========================
# STASH
# =========================
def read_commit_message(commit_hash):
    path = Path(".mygit/objects") / commit_hash
    if path.is_file():
        metadata = path.read_text(encoding="utf-8").split("\n\n", 1)[0]
        for line in metadata.splitlines():
            if line.startswith("message:"):
                return line.split(":", 1)[1].strip()
    return ""


def get_stash_files():
    """Return stash files, newest first. The newest one is stash@{0}."""
    stash_dir = Path(".mygit/stash")
    if not stash_dir.exists():
        return []
    files = [p for p in stash_dir.iterdir() if p.name.isdigit()]
    return sorted(files, key=lambda p: int(p.name), reverse=True)


def parse_stash_number(rest):
    """Accepts nothing (newest), '1', or 'stash@{1}'. Returns None if invalid."""
    if not rest:
        return 0
    text = rest[0]
    if text.startswith("stash@{") and text.endswith("}"):
        text = text[7:-1]
    return int(text) if text.isdigit() else None


def write_stash_entry(message, branch, base, index_files, work_files):
    stash_dir = Path(".mygit/stash")
    stash_dir.mkdir(parents=True, exist_ok=True)
    numbers = [int(p.name) for p in stash_dir.iterdir() if p.name.isdigit()]
    number = max(numbers, default=0) + 1
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    message = message.replace("\r", " ").replace("\n", " ")
    lines = [f"message: {message}", f"branch: {branch}",
             f"base: {base}", f"date: {date}", "", "[index]"]
    lines += [f"{name} {h}" for name, h in sorted(index_files.items())]
    lines.append("[work]")
    lines += [f"{name} {h}" for name, h in sorted(work_files.items())]
    atomic_write_text(stash_dir / f"{number:04d}", "\n".join(lines) + "\n")
    return number


def read_stash_entry(path):
    """Return (info, index_files, work_files) for one stash file."""
    info, index_files, work_files = {}, {}, {}
    section = None
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if line == "[index]":
            section = index_files
        elif line == "[work]":
            section = work_files
        elif section is None:
            if ": " in line:
                key, value = line.split(": ", 1)
                info[key] = value
        elif line.strip():
            name, _, file_hash = line.rpartition(" ")
            if name:
                section[name] = file_hash
    return info, index_files, work_files


def stash_push(custom_message=None):
    if merge_in_progress():
        return
    current_branch, current_commit = get_head()
    if not current_commit:
        print("Cannot stash: there are no commits yet.")
        return

    head_files = get_commit_files(current_commit)
    index_entries = read_index()
    tracked = sorted(set(head_files) | set(index_entries))

    # Check everything BEFORE touching any file
    for filename in tracked:
        try:
            normalize_path(filename)
        except ValueError as error:
            print(f"Unsafe path: {error}. Nothing changed.")
            return
    for file_hash in head_files.values():
        if not (Path(".mygit/objects") / file_hash).exists():
            print("A stored file from the last commit is missing. Nothing changed.")
            return

    # Take a snapshot of the working files
    work_files = {}
    try:
        for filename in tracked:
            path = Path(filename)
            if path.is_file():
                work_files[filename] = store_blob(path.read_bytes())
    except OSError as error:
        print(f"Could not read your files: {error}. Nothing changed.")
        return

    if index_entries == head_files and work_files == head_files:
        print("No local changes to save.")
        return

    branch_name = current_branch or "(detached HEAD)"
    if custom_message:
        message = f"On {branch_name}: {custom_message}"
    else:
        subject = read_commit_message(current_commit)
        message = f"WIP on {branch_name}: {current_commit[:7]} {subject}".strip()

    # Save the stash FIRST, so your work is safe
    try:
        write_stash_entry(message, branch_name, current_commit,
                          index_entries, work_files)
    except OSError as error:
        print(f"Could not save the stash: {error}")
        print("Nothing was changed.")
        return

    # Now put the tracked files and the index back to the last commit
    try:
        for filename in tracked:
            path = Path(filename)
            if filename in head_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(read_blob(head_files[filename]))
            elif path.is_file():
                path.unlink()
        write_index(head_files)
    except OSError as error:
        print(f"Your changes ARE saved in the stash, but cleaning your folder failed: {error}")
        print("Use 'python mygit.py restore <file>' for any file that looks wrong.")
        return

    print(f"Saved working directory and index state: {message}")
    print("Your tracked files are back to the last commit.")


def stash_list():
    files = get_stash_files()
    if not files:
        print("No stashes saved.")
        return
    for number, path in enumerate(files):
        try:
            info, _, _ = read_stash_entry(path)
        except OSError:
            info = {}
        # {{ and }} print real curly brackets
        print(f"stash@{{{number}}}: {info.get('message', '(unreadable stash)')}")


def apply_stash(rest, pop):
    if merge_in_progress():
        return
    files = get_stash_files()
    if not files:
        print("No stashes saved.")
        return
    number = parse_stash_number(rest)
    if number is None or number >= len(files):
        print("That stash does not exist. See: python mygit.py stash list")
        return
    entry_path = files[number]
    try:
        info, stash_index, stash_work = read_stash_entry(entry_path)
    except OSError as error:
        print(f"Cannot read the stash: {error}")
        return

    base = info.get("base", "")
    current_branch, current_commit = get_head()
    if current_branch is None or not current_commit:
        print("Cannot apply a stash here (no commits yet, or detached HEAD).")
        return
    if not is_commit_object(base):
        print("The commit this stash was made from is missing. Nothing changed.")
        return

    base_files = get_commit_files(base)
    our_files = get_commit_files(current_commit)
    merged_files = {}
    conflicts = []
    try:
        names = set(base_files) | set(our_files) | set(stash_index) | set(stash_work)
        for filename in sorted(names):
            normalize_path(filename)
            data, conflict = merge_one_file(
                base_files.get(filename), our_files.get(filename),
                stash_work.get(filename), "current files", "stash")
            if conflict:
                conflicts.append(filename)
            elif data is not None:
                merged_files[filename] = store_blob(data)
    except (ValueError, OSError) as error:
        print(f"Cannot apply the stash: {error}")
        print("Nothing was changed.")
        return

    if conflicts:
        print("Cannot apply the stash: it conflicts with your current files:")
        for filename in conflicts:
            print(f"  - {filename}")
        print("Nothing was changed. The stash is still saved.")
        return

    if base == current_commit:
        index_files = stash_index
        note = "Your staged and unstaged changes are back as they were."
    else:
        index_files = our_files
        note = "Changes were applied as unstaged (the branch moved since the stash)."

    def finish():
        if pop:
            entry_path.unlink()

    if not update_working_tree(our_files, merged_files, finish, index_files):
        print("Stash not applied. Nothing changed.")
        return

    print(f"Applied stash@{{{number}}}.")
    print(note)
    if pop:
        print(f"Dropped stash@{{{number}}}.")
    else:
        print("The stash is still saved. Remove it with: python mygit.py stash drop")


def stash_drop(rest):
    files = get_stash_files()
    if not files:
        print("No stashes saved.")
        return
    number = parse_stash_number(rest)
    if number is None or number >= len(files):
        print("That stash does not exist. See: python mygit.py stash list")
        return
    try:
        files[number].unlink()
    except OSError as error:
        print(f"Could not drop the stash: {error}")
        return
    print(f"Dropped stash@{{{number}}}. Its saved changes are permanently deleted.")


def stash_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    action = args[0] if args else "push"
    rest = args[1:]
    if action == "push":
        message = None
        if rest[:1] == ["-m"] and len(rest) == 2 and rest[1].strip():
            message = rest[1].strip()
        elif rest:
            print('Usage: python mygit.py stash push -m "message"')
            return
        stash_push(message)
    elif action == "list":
        stash_list()
    elif action == "apply":
        apply_stash(rest, pop=False)
    elif action == "pop":
        apply_stash(rest, pop=True)
    elif action == "drop":
        stash_drop(rest)
    else:
        print(f"Unknown stash command: {action}")
        print("Use: stash, stash push -m, stash list, stash apply, stash pop, stash drop")

# =========================
# CHERRY-PICK
# =========================
def merge_kind():
    """Return 'merge' or 'cherry-pick' while one is unfinished, else None."""
    if not Path(".mygit/MERGE_HEAD").exists():
        return None
    lines = read_state_lines("MERGE_KIND")
    return lines[0] if lines else "merge"


def read_commit_info(commit_hash):
    """Return a dict with message, author, email and date for a commit."""
    info = {"message": "", "author": "", "email": "", "date": ""}
    path = Path(".mygit/objects") / commit_hash
    if path.is_file():
        metadata = path.read_text(encoding="utf-8").split("\n\n", 1)[0]
        for line in metadata.splitlines():
            key, _, value = line.partition(":")
            if key in info:
                info[key] = value.strip()
    return info


def cherry_pick_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return

    if args in (["--abort"], ["--continue"]):
        if merge_kind() != "cherry-pick":
            print("No cherry-pick in progress.")
            return
        if args[0] == "--abort":
            merge_abort()
        else:
            merge_continue()
        return

    if len(args) != 1 or args[0].startswith("-"):
        print("Usage: python mygit.py cherry-pick <commit>")
        print("       python mygit.py cherry-pick --abort")
        print("       python mygit.py cherry-pick --continue")
        return
    if merge_in_progress():
        return

    picked = resolve_commit(args[0])
    if picked is None or not is_commit_object(picked):
        print(f"'{args[0]}' is not a valid commit, branch, or tag. Nothing changed.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot cherry-pick: detached HEAD is not supported yet.")
        return
    if not current_commit:
        print("Cannot cherry-pick: this branch has no commits yet.")
        return
    if picked in get_ancestors(current_commit):
        print("That commit is already part of this branch's history. Nothing changed.")
        return

    parents = read_commit_parents(picked)
    if len(parents) > 1:
        print("Cannot cherry-pick a merge commit (it has two parents). Nothing changed.")
        return
    if parents and not is_commit_object(parents[0]):
        print("The parent of that commit is missing. Nothing changed.")
        return

    base_files = get_commit_files(parents[0]) if parents else {}
    pick_files = get_commit_files(picked)
    our_files = get_commit_files(current_commit)
    our_label = f"ours ({current_branch})"
    their_label = f"cherry-pick ({picked[:7]})"

    merged_files = {}
    index_files = {}
    conflicts = []
    conflict_hashes = {}
    try:
        for filename in sorted(set(base_files) | set(our_files) | set(pick_files)):
            normalize_path(filename)
            data, conflict = merge_one_file(
                base_files.get(filename), our_files.get(filename),
                pick_files.get(filename), our_label, their_label)
            if data is None:
                continue
            new_hash = store_blob(data)
            merged_files[filename] = new_hash
            if conflict:
                conflicts.append(filename)
                conflict_hashes[filename] = new_hash
                if filename in our_files:
                    index_files[filename] = our_files[filename]
            else:
                index_files[filename] = new_hash
    except (ValueError, OSError) as error:
        print(f"Cherry-pick failed: {error}")
        print("Nothing was changed.")
        return

    if not conflicts and merged_files == our_files:
        print("The changes from this commit are already in your branch.")
        print("Nothing to commit.")
        return

    touched = sorted(f for f in set(our_files) | set(merged_files)
                     if our_files.get(f) != merged_files.get(f))
    info = read_commit_info(picked)
    default_name, default_email = get_identity()
    author = info["author"] if info["author"] not in ("", "Unknown") else default_name
    email = info["email"] if info["email"] not in ("", "Unknown") else default_email
    message = f"{info['message']} (cherry picked from commit {picked[:7]})".strip()
    current_ref = Path(".mygit/refs/heads") / current_branch
    result = {}

    def finish():
        if conflicts:
            atomic_write_text(".mygit/MERGE_FILES", "".join(f"{f}\n" for f in touched))
            atomic_write_text(".mygit/MERGE_CONFLICTS",
                              "".join(f"{f} {conflict_hashes[f]}\n" for f in conflicts))
            atomic_write_text(".mygit/MERGE_MSG", message + "\n")
            atomic_write_text(".mygit/MERGE_KIND", "cherry-pick\n")
            atomic_write_text(".mygit/MERGE_AUTHOR", f"{author}\n{email}\n")
            atomic_write_text(".mygit/MERGE_HEAD", picked + "\n")
        else:
            commit_hash = write_commit_object(
                message, merged_files, [current_commit], author, email)
            atomic_write_text(current_ref, commit_hash)
            result["hash"] = commit_hash

    if not update_working_tree(our_files, merged_files, finish, index_files):
        print("Cherry-pick cancelled. Nothing changed.")
        return

    if conflicts:
        print("Cherry-pick stopped: conflicts found in:")
        for filename in conflicts:
            print(f"  - {filename}")
        print("The cherry-pick is NOT finished. Your files now contain conflict markers.")
        print("See them with:  python mygit.py conflicts")
        print("Then run:       python mygit.py cherry-pick --continue")
        print("Or cancel with: python mygit.py cherry-pick --abort")
        return

    print(f"Cherry-picked {picked[:7]} onto '{current_branch}'.")
    print(f"New commit: {result['hash'][:7]} (author kept: {author})")
    print(f"The original commit {picked[:7]} was not changed.")

# =========================
# REBASE
# =========================
REBASE_STATE_FILES = ("REBASE_BRANCH", "REBASE_ORIG", "REBASE_BASE",
                      "REBASE_TODO", "REBASE_TIP")


def rebase_in_progress():
    return Path(".mygit/REBASE_ORIG").exists()


def rebase_clear_state():
    clear_merge_state()
    for name in REBASE_STATE_FILES:
        path = Path(".mygit") / name
        if path.exists():
            path.unlink()


def write_rebase_todo(todo):
    atomic_write_text(".mygit/REBASE_TODO", "".join(f"{c}\n" for c in todo))


def three_way_pick(base_files, our_files, their_files, our_label, their_label):
    """Merge three file snapshots. Returns (merged, index, conflicts, conflict_hashes)."""
    merged_files = {}
    index_files = {}
    conflicts = []
    conflict_hashes = {}
    for filename in sorted(set(base_files) | set(our_files) | set(their_files)):
        normalize_path(filename)
        data, conflict = merge_one_file(
            base_files.get(filename), our_files.get(filename),
            their_files.get(filename), our_label, their_label)
        if data is None:
            continue
        new_hash = store_blob(data)
        merged_files[filename] = new_hash
        if conflict:
            conflicts.append(filename)
            conflict_hashes[filename] = new_hash
            if filename in our_files:
                index_files[filename] = our_files[filename]
        else:
            index_files[filename] = new_hash
    return merged_files, index_files, conflicts, conflict_hashes


def commits_to_replay(tip, base):
    """List commits from base (not included) up to tip, oldest first.
    Returns None if the range has a merge commit or a root commit."""
    commits = []
    current = tip
    while current != base:
        parents = read_commit_parents(current)
        if len(parents) != 1:
            return None
        commits.append(current)
        current = parents[0]
    return list(reversed(commits))


def rebase_start(branch_name):
    if (not branch_name or ".." in branch_name
            or "\\" in branch_name or branch_name.startswith("/")):
        print(f"Invalid branch name: {branch_name}")
        return

    target_ref = Path(".mygit/refs/heads") / branch_name
    if not target_ref.is_file():
        print(f"Branch '{branch_name}' does not exist.")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot rebase: detached HEAD is not supported yet.")
        return
    if not current_commit:
        print("Cannot rebase: this branch has no commits yet.")
        return
    if current_branch == branch_name:
        print(f"Cannot rebase '{branch_name}' onto itself.")
        return

    target_commit = target_ref.read_text(encoding="utf-8").strip()
    if not target_commit or not is_commit_object(target_commit):
        print(f"Branch '{branch_name}' has no valid commit. Nothing changed.")
        return

    base = find_merge_base(current_commit, target_commit)
    if base is None:
        print("Cannot rebase: these branches have unrelated histories (no common commit).")
        print("Nothing changed.")
        return
    if base == target_commit:
        print(f"'{current_branch}' is already based on '{branch_name}'. Already up to date.")
        return

    head_files = get_commit_files(current_commit)
    target_files = get_commit_files(target_commit)

    # Fast-forward: your branch is simply behind the target
    if base == current_commit:
        current_ref = Path(".mygit/refs/heads") / current_branch

        def finish():
            atomic_write_text(current_ref, target_commit)

        if not update_working_tree(head_files, target_files, finish):
            print("Rebase cancelled. Nothing changed.")
            return
        print(f"Rebased '{current_branch}' onto '{branch_name}' (fast-forward).")
        print(f"'{current_branch}' is now at {target_commit[:7]}")
        return

    todo = commits_to_replay(current_commit, base)
    if todo is None:
        print("Cannot rebase: the commits to replay include a merge or root commit.")
        print("This is not supported yet. Nothing changed.")
        return

    # Save the rebase state first. The branch file is NOT changed here.
    atomic_write_text(".mygit/REBASE_BRANCH", current_branch + "\n")
    atomic_write_text(".mygit/REBASE_ORIG", current_commit + "\n")
    atomic_write_text(".mygit/REBASE_BASE", base + "\n")
    atomic_write_text(".mygit/REBASE_ONTO", branch_name + "\n")
    atomic_write_text(".mygit/REBASE_TIP", target_commit + "\n")
    write_rebase_todo(todo)

    # Move your files from the original branch to the target (the new base).
    # If your files have unsaved changes, this refuses and we clear the state.
    if not update_working_tree(head_files, target_files, lambda: None):
        rebase_clear_state()
        print("Rebase cancelled. Nothing changed.")
        return

    print(f"Rebasing {len(todo)} commit(s) of '{current_branch}' onto '{branch_name}'...")
    rebase_run()


def rebase_run():
    """Replay the commits in REBASE_TODO one at a time. Stops at a conflict."""
    branch_name = read_state_lines("REBASE_BRANCH")[0]
    base = read_state_lines("REBASE_BASE")[0]
    onto_name = read_state_lines("REBASE_ONTO")[0]
    todo = read_state_lines("REBASE_TODO")
    tip = read_state_lines("REBASE_TIP")[0]
    default_name, default_email = get_identity()

    while todo:
        picked = todo[0]
        parents = read_commit_parents(picked)
        if not parents:
            print("Rebase stopped: a commit in the list is missing.")
            print("Run: python mygit.py rebase --abort")
            return
        our_files = get_commit_files(tip)
        try:
            merged, index_files, conflicts, conflict_hashes = three_way_pick(
                get_commit_files(parents[0]), our_files, get_commit_files(picked),
                f"ours (rebasing {branch_name})", f"commit {picked[:7]}")
        except (ValueError, OSError) as error:
            print(f"Rebase stopped: {error}")
            print("Run: python mygit.py rebase --abort")
            return

        if not conflicts and merged == our_files:
            print(f"Skipped {picked[:7]}: its changes are already in the branch.")
            todo = todo[1:]
            write_rebase_todo(todo)
            continue

        info = read_commit_info(picked)
        message = info["message"] or "(no message)"
        author = info["author"] if info["author"] not in ("", "Unknown") else default_name
        email = info["email"] if info["email"] not in ("", "Unknown") else default_email
        touched = sorted(f for f in set(our_files) | set(merged)
                         if our_files.get(f) != merged.get(f))

        if conflicts:
            def stop_here():
                atomic_write_text(".mygit/MERGE_FILES", "".join(f"{f}\n" for f in touched))
                atomic_write_text(".mygit/MERGE_CONFLICTS",
                                  "".join(f"{f} {conflict_hashes[f]}\n" for f in conflicts))
                atomic_write_text(".mygit/MERGE_MSG", message + "\n")
                atomic_write_text(".mygit/MERGE_KIND", "rebase\n")
                atomic_write_text(".mygit/MERGE_AUTHOR", f"{author}\n{email}\n")
                atomic_write_text(".mygit/MERGE_HEAD", picked + "\n")
                write_rebase_todo(todo[1:])

            if not update_working_tree(our_files, merged, stop_here, index_files):
                print("Rebase cancelled. Nothing changed.")
                return
            print(f"Rebase stopped on commit {picked[:7]}: conflicts found in:")
            for filename in conflicts:
                print(f"  - {filename}")
            print("Your files now contain conflict markers.")
            print("See them with:  python mygit.py conflicts")
            print("Fix them, then: python mygit.py rebase --continue")
            print("Or cancel with: python mygit.py rebase --abort")
            return

        new_hash = write_commit_object(message, merged, [tip], author, email)

        def finish_clean():
            atomic_write_text(".mygit/REBASE_TIP", new_hash + "\n")
            write_rebase_todo(todo[1:])

        if not update_working_tree(our_files, merged, finish_clean, index_files):
            print("Rebase cancelled. Nothing changed.")
            return
        tip = new_hash
        todo = todo[1:]
        print(f"Replayed {picked[:7]} as {new_hash[:7]}")

    # Every commit is replayed: only now move the branch
    atomic_write_text(Path(".mygit/refs/heads") / branch_name, tip)
    rebase_clear_state()
    print(f"Successfully rebased '{branch_name}' onto '{onto_name}'.")
    print(f"'{branch_name}' is now at {tip[:7]}")
    print("Original commits were not changed. Replayed commits have new hashes.")


def rebase_step_done(final_files):
    """Called by 'merge --continue' when the stopped rebase commit is resolved."""
    picked = read_state_lines("MERGE_HEAD")[0]
    message = " ".join(read_state_lines("MERGE_MSG")) or "(no message)"
    author_lines = read_state_lines("MERGE_AUTHOR")
    author, email = ((author_lines[0], author_lines[1])
                     if len(author_lines) == 2 else (None, None))
    tip = read_state_lines("REBASE_TIP")[0]
    try:
        new_hash = write_commit_object(message, final_files, [tip], author, email)
        write_index(final_files)
        atomic_write_text(".mygit/REBASE_TIP", new_hash + "\n")
    except OSError as error:
        print(f"Could not save the resolved commit: {error}")
        print("Fix the problem, then run: python mygit.py rebase --continue")
        return
    clear_merge_state()
    print(f"Resolved commit {picked[:7]} saved as {new_hash[:7]}.")
    rebase_run()


def rebase_abort():
    if not rebase_in_progress():
        print("No rebase in progress.")
        return
    orig_files = get_commit_files(read_state_lines("REBASE_ORIG")[0])
    tip_files = get_commit_files(read_state_lines("REBASE_TIP")[0])
    touched = set(read_state_lines("MERGE_FILES")) | set(tip_files) | set(orig_files)
    objects_dir = Path(".mygit/objects")

    # Check everything first, so we never stop halfway
    try:
        for filename in touched:
            normalize_path(filename)
    except ValueError as error:
        print(f"Unsafe path in rebase state: {error}. Nothing changed.")
        return
    for file_hash in orig_files.values():
        if not (objects_dir / file_hash).exists():
            print("A stored file from the original branch is missing. Nothing changed.")
            return

    try:
        for filename in sorted(touched):
            path = Path(filename)
            if filename in orig_files:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(read_blob(orig_files[filename]))
            elif path.is_file():
                path.unlink()
        write_index(orig_files)
        rebase_clear_state()
    except OSError as error:
        print(f"Rebase abort stopped: {error}")
        print("Run 'python mygit.py rebase --abort' again to finish.")
        return

    print("Rebase aborted. Your branch and files are back to how they were before the rebase.")
    print("Edits you made to conflicted files during the rebase were discarded.")


def rebase_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if args in (["--abort"], ["--continue"]):
        if not rebase_in_progress():
            print("No rebase in progress.")
            return
        if args[0] == "--abort":
            rebase_abort()
        else:
            merge_continue()
        return
    if len(args) != 1 or args[0].startswith("-"):
        print("Usage: python mygit.py rebase <branch>")
        print("       python mygit.py rebase --continue")
        print("       python mygit.py rebase --abort")
        return
    if rebase_in_progress():
        print("A rebase is already in progress.")
        print("Finish it:  python mygit.py rebase --continue")
        print("Cancel it:  python mygit.py rebase --abort")
        return
    if merge_in_progress():
        return
    rebase_start(args[0])

# =========================
# RESET AND RESTORE (Feature 9)
# =========================
def snapshot_files(filenames):
    """Save the current content of each existing file as a blob. Returns {name: hash}."""
    snapshot = {}
    for filename in sorted(filenames):
        path = Path(filename)
        if path.is_file():
            snapshot[filename] = store_blob(path.read_bytes())
    return snapshot


def reset_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if merge_in_progress():
        return

    mode = "mixed"
    yes = False
    rest = []
    for arg in args:
        if arg in ("--soft", "--mixed", "--hard"):
            mode = arg[2:]
        elif arg == "--yes":
            yes = True
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            return
        else:
            rest.append(arg)

    if len(rest) != 1:
        print("Usage: python mygit.py reset [--soft|--mixed|--hard] <commit>")
        print("       python mygit.py reset --hard <commit> --yes")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot reset: detached HEAD is not supported yet.")
        return
    if not current_commit:
        print("Cannot reset: this branch has no commits yet.")
        return

    target = resolve_commit(rest[0])
    if target is None or not is_commit_object(target):
        print(f"'{rest[0]}' is not a valid commit, branch, or tag. Nothing changed.")
        return

    objects_dir = Path(".mygit/objects")
    target_files = get_commit_files(target)
    current_files = get_commit_files(current_commit)
    index_entries = read_index()

    for filename, file_hash in target_files.items():
        try:
            normalize_path(filename)
        except ValueError as error:
            print(f"Unsafe path in commit: {error}. Nothing changed.")
            return
        if not (objects_dir / file_hash).exists():
            print(f"Missing stored file for '{filename}'. Nothing changed.")
            return

    if mode == "hard":
        tracked = sorted(set(current_files) | set(index_entries) | set(target_files))
        lost = []
        for filename in tracked:
            path = Path(filename)
            working_hash = hash_file(filename) if path.is_file() else None
            if working_hash != current_files.get(filename):
                lost.append(filename)

        if lost and not yes:
            print("Hard reset would discard your changes to:")
            for filename in lost:
                print(f"  {filename}")
            print("Nothing changed. To proceed, add --yes (a backup goes to the stash first).")
            return

        if lost:
            snapshot = snapshot_files(tracked)
            write_stash_entry(f"Backup before reset --hard to {target[:7]}",
                              current_branch, current_commit, index_entries, snapshot)
            print("Saved a backup of your changes in the stash (see: stash list).")

        try:
            for filename in tracked:
                path = Path(filename)
                if filename in target_files:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(read_blob(target_files[filename]))
                elif path.is_file():
                    path.unlink()
        except OSError as error:
            print(f"Hard reset stopped: {error}")
            print("Your changes are in the stash (see: stash list).")
            return

    if mode in ("mixed", "hard"):
        write_index(target_files)
    atomic_write_text(Path(".mygit/refs/heads") / current_branch, target)

    print(f"Reset '{current_branch}' to {target[:7]} ({mode}).")
    if mode == "soft":
        print("Your staged changes and working files were kept.")
    elif mode == "mixed":
        print("Your working files were kept. Changes since that commit show as unstaged.")
    else:
        print("Your files and staging now match that commit.")


def restore_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if merge_in_progress():
        return

    staged = False
    from_index = False
    yes = False
    source = None
    rest = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--staged":
            staged = True
        elif arg == "--index":
            from_index = True
        elif arg == "--yes":
            yes = True
        elif arg == "--source":
            if i + 1 >= len(args):
                print("Usage: python mygit.py restore --source <commit> <file>")
                return
            source = args[i + 1]
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            return
        else:
            rest.append(arg)
        i += 1

    if len(rest) != 1 or (from_index and (staged or source is not None)):
        print("Usage: python mygit.py restore <file>                  (from last commit)")
        print("       python mygit.py restore --index <file>          (from staging area)")
        print("       python mygit.py restore --source <commit> <file>")
        print("       python mygit.py restore --staged <file>         (unstage a file)")
        print("Add --yes if a file has unsaved changes that would be overwritten.")
        return

    try:
        filename = normalize_path(rest[0])
    except ValueError as error:
        print(f"Error: {error}")
        return

    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot restore: detached HEAD is not supported yet.")
        return

    if source is not None:
        commit = resolve_commit(source)
        if commit is None or not is_commit_object(commit):
            print(f"'{source}' is not a valid commit, branch, or tag. Nothing changed.")
            return
        source_files = get_commit_files(commit)
        source_name = f"commit {commit[:7]}"
    elif from_index:
        source_files = read_index()
        source_name = "the staging area"
    else:
        source_files = get_commit_files(current_commit) if current_commit else {}
        source_name = "the last commit"

    objects_dir = Path(".mygit/objects")
    if filename in source_files and not (objects_dir / source_files[filename]).exists():
        print(f"Stored file for '{filename}' is missing. Nothing changed.")
        return

    if staged:
        index_entries = read_index()
        if filename in source_files:
            index_entries[filename] = source_files[filename]
            write_index(index_entries)
            print(f"Staging for '{filename}' now matches {source_name}. Your file was not changed.")
        else:
            index_entries.pop(filename, None)
            write_index(index_entries)
            print(f"'{filename}' is no longer staged. Your file was not changed.")
        return

    if filename not in source_files:
        print(f"'{filename}' is not in {source_name}. Nothing changed.")
        return

    file_hash = source_files[filename]
    path = Path(filename)
    if path.is_file() and hash_file(filename) != file_hash and not yes:
        print(f"'{filename}' has changes that restore would overwrite. Nothing changed.")
        print("To discard them, run the same command again with --yes.")
        return

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(read_blob(file_hash))
    print(f"Restored '{filename}' from {source_name}.")

# =========================
# REFLOG (Feature 10)
# =========================
REFLOG_FILE = Path(".mygit/reflog")
REFLOG_ACTION = "unknown"


def set_reflog_action(text):
    """Remember the command being run, so reflog entries say what caused them."""
    global REFLOG_ACTION
    REFLOG_ACTION = " ".join(text.split())[:120] or "unknown"


def head_branch_name(text):
    """'ref: refs/heads/main' becomes 'main'. A detached HEAD is kept as it is."""
    if text.startswith("ref:"):
        return text.split(":", 1)[1].strip().replace("refs/heads/", "", 1)
    return text


def append_reflog(ref, old_value, new_value):
    """Add one line: date, ref, old value, new value, action."""
    REFLOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    line = f"{date}\t{ref}\t{old_value}\t{new_value}\t{REFLOG_ACTION}\n"
    with open(REFLOG_FILE, "a", encoding="utf-8", newline="\n") as file:
        file.write(line)


def record_if_ref_moved(path, old_text, new_text):
    """Called by atomic_write_text. Records changes to branches and HEAD only."""
    if path.as_posix() == ".mygit/HEAD":
        old_value = head_branch_name(old_text) if old_text else "-"
        new_value = head_branch_name(new_text)
        ref = "HEAD"
    elif path.parent.as_posix() == ".mygit/refs/heads":
        old_value = old_text or "-"
        new_value = new_text
        ref = path.name
    else:
        return
    if old_value != new_value:
        append_reflog(ref, old_value, new_value)


def read_reflog():
    """Return all reflog lines, oldest first, as lists of 5 fields."""
    if not REFLOG_FILE.exists():
        return []
    entries = []
    for line in REFLOG_FILE.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 5:
            entries.append(parts)
    return entries


def short_value(value):
    return value[:7] if len(value) == 40 else value


def reflog_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    show_all = "--all" in args
    numbers = [a for a in args if a.isdigit()]
    limit = int(numbers[0]) if numbers else 20

    current_branch, _ = get_head()
    entries = read_reflog()
    if not show_all and current_branch:
        entries = [e for e in entries if e[1] in (current_branch, "HEAD")]
    if not entries:
        print("No reflog entries yet.")
        return

    shown = list(reversed(entries))[:limit]
    print(f"Reflog (newest first, showing {len(shown)} of {len(entries)}):")
    for number, (date, ref, old_value, new_value, action) in enumerate(shown):
        print(f"  {number}: {ref}  {short_value(old_value)} -> {short_value(new_value)}  {action}")
        print(f"       {date}")
    print("To go back to an old position: python mygit.py reset <hash>")
    print("(The 7-letter short hash is enough.)")


# =========================
# TAGS (Feature 11)
# =========================
TAG_NAME_HELP = "Tag names cannot be empty, contain / or \\ or .., or start with - or ."


def valid_tag_name(name):
    return (bool(name) and ".." not in name and "/" not in name
            and "\\" not in name and not name.startswith(("-", ".")))


def tag_path(name):
    return Path(".mygit/refs/tags") / name


def peel_tag(value):
    """If value is an annotated tag object, return the commit it points to.
    Otherwise return value unchanged."""
    path = Path(".mygit/objects") / value
    if path.is_file():
        first_line = path.read_text(encoding="utf-8", errors="replace").splitlines()[:1]
        if first_line and first_line[0].startswith("object:"):
            return first_line[0].split(":", 1)[1].strip()
    return value


def read_tag_kind(value):
    """Return ('annotated', commit) or ('lightweight', commit)."""
    commit = peel_tag(value)
    kind = "annotated" if commit != value else "lightweight"
    return kind, commit


def read_annotated_tag(value):
    info = {"tag": "", "tagger": "", "email": "", "date": "", "message": ""}
    text = (Path(".mygit/objects") / value).read_text(encoding="utf-8", errors="replace")
    header, _, body = text.partition("\n\n")
    for line in header.splitlines():
        key, _, val = line.partition(":")
        if key in info:
            info[key] = val.strip()
    info["message"] = body.strip()
    return info


def write_tag_object(name, target, message):
    """Save an annotated tag object and return its hash."""
    author, email = get_identity()
    date = datetime.now().astimezone().isoformat(timespec="seconds")
    text = (f"object: {target}\n"
            "type: commit\n"
            f"tag: {name}\n"
            f"tagger: {author}\n"
            f"email: {email}\n"
            f"date: {date}\n\n"
            f"{message}\n")
    tag_hash = hashlib.sha1(text.encode("utf-8")).hexdigest()
    atomic_write_text(Path(".mygit/objects") / tag_hash, text)
    return tag_hash


def tag_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return

    annotated = False
    force = False
    message = None
    rest = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "-a":
            annotated = True
        elif arg == "-f":
            force = True
        elif arg == "-m":
            if i + 1 >= len(args):
                print('Usage: python mygit.py tag -a <name> -m "message"')
                return
            message = args[i + 1]
            i += 1
        elif arg.startswith("-"):
            print(f"Unknown option: {arg}")
            return
        else:
            rest.append(arg)
        i += 1

    if not rest or len(rest) > 2:
        print("Usage: python mygit.py tag <name> [commit]")
        print('       python mygit.py tag -a <name> -m "message" [commit]')
        print("       python mygit.py tag -f <name> [commit]   (replace an existing tag)")
        return

    name = rest[0]
    if not valid_tag_name(name):
        print(f"Invalid tag name: {name}. {TAG_NAME_HELP}")
        return
    if annotated and not (message and message.strip()):
        print('Annotated tags need a message: python mygit.py tag -a <name> -m "message"')
        return
    if message is not None and not annotated:
        print("-m can only be used together with -a (annotated tags).")
        return

    if len(rest) == 2:
        target = resolve_commit(rest[1])
        if target is None or not is_commit_object(target):
            print(f"'{rest[1]}' is not a valid commit, branch, or tag. Nothing changed.")
            return
    else:
        _, target = get_head()
        if not target:
            print("Cannot tag: this branch has no commits yet.")
            return

    existing = tag_path(name)
    replacing = existing.exists()
    if replacing and not force:
        print(f"Tag '{name}' already exists. Add -f to replace it. Nothing changed.")
        return

    try:
        value = write_tag_object(name, target, message.strip()) if annotated else target
        existing.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(existing, value)
    except OSError as error:
        print(f"Could not create the tag: {error}. Nothing changed.")
        return

    kind = "annotated" if annotated else "lightweight"
    note = " (replaced the old tag)" if replacing else ""
    print(f"Created {kind} tag '{name}' at {target[:7]}{note}.")


def tag_list_command():
    tags_dir = Path(".mygit/refs/tags")
    names = sorted(p.name for p in tags_dir.iterdir() if p.is_file()) if tags_dir.exists() else []
    if not names:
        print("No tags yet.")
        return
    for name in names:
        value = tag_path(name).read_text(encoding="utf-8").strip()
        kind, commit = read_tag_kind(value)
        print(f"  {name}  ({kind})  -> {commit[:7]}")


def tag_show_command(args):
    if len(args) != 1:
        print("Usage: python mygit.py tag-show <name>")
        return
    name = args[0]
    if not valid_tag_name(name) or not tag_path(name).is_file():
        print(f"Tag '{name}' does not exist.")
        return
    value = tag_path(name).read_text(encoding="utf-8").strip()
    kind, commit = read_tag_kind(value)
    print(f"Tag:            {name}")
    print(f"Type:           {kind}")
    print(f"Points to:      {commit}")
    if kind == "annotated":
        info = read_annotated_tag(value)
        print(f"Tagger:         {info['tagger']} <{info['email']}>")
        print(f"Date:           {info['date']}")
        print(f"Tag message:    {info['message']}")
    commit_info = read_commit_info(commit)
    print(f"Commit message: {commit_info['message']}")


def tag_delete_command(args):
    if len(args) != 1:
        print("Usage: python mygit.py tag-delete <name>")
        return
    name = args[0]
    if not valid_tag_name(name) or not tag_path(name).is_file():
        print(f"Tag '{name}' does not exist.")
        return
    value = tag_path(name).read_text(encoding="utf-8").strip()
    kind, commit = read_tag_kind(value)
    tag_path(name).unlink()
    print(f"Deleted tag '{name}' (was {kind}, pointing to {commit[:7]}).")
    if kind == "annotated":
        print("Its tag object is still stored until garbage collection (Feature 12) removes it.")

# =========================
# INTEGRITY CHECK AND GARBAGE COLLECTION (Feature 12)
# =========================
def stored_object_names():
    """Names of all files in .mygit/objects (ignores leftover .tmp files)."""
    objects_dir = Path(".mygit/objects")
    if not objects_dir.exists():
        return []
    return sorted(p.name for p in objects_dir.iterdir()
                  if p.is_file() and not p.name.endswith(".tmp"))


def sha1_of_file(path):
    return hashlib.sha1(path.read_bytes()).hexdigest()


def hashes_in_text(text):
    import re
    return set(re.findall(r"\b[0-9a-f]{40}\b", text))


def ref_targets():
    """Return (name, hash) for every branch and tag file."""
    results = []
    for folder in ("refs/heads", "refs/tags", "refs/remotes"):
        base = Path(".mygit") / folder
        if base.exists():
            for path in base.rglob("*"):
                if path.is_file():
                    value = path.read_text(encoding="utf-8").strip()
                    results.append((path.relative_to(".mygit").as_posix(), value))
    return results


def state_hashes():
    """Hashes mentioned in HEAD, the index, the reflog, merge/rebase state and the stash.
    Anything named here counts as in use, so gc keeps it."""
    mygit = Path(".mygit")
    paths = [mygit / name for name in (
        "HEAD", "index", "reflog", "MERGE_HEAD", "MERGE_MSG", "MERGE_FILES",
        "MERGE_CONFLICTS", "MERGE_AUTHOR", "REBASE_ORIG", "REBASE_BASE",
        "REBASE_TIP", "REBASE_TODO")]
    stash = mygit / "stash"
    if stash.exists():
        paths += [p for p in stash.iterdir() if p.is_file()]
    found = set()
    for path in paths:
        if path.is_file():
            found |= hashes_in_text(path.read_text(encoding="utf-8", errors="ignore"))
    return found


def walk_repository():
    """Follow every reference to find the objects in use. Returns (in_use, problems)."""
    objects_dir = Path(".mygit/objects")
    problems = []
    in_use = set()
    queue = []

    for name, value in ref_targets():
        if not value:
            continue
        if (objects_dir / value).is_file():
            queue.append(value)
        else:
            problems.append(f"{name} points to {value[:7]}, which is missing")

    for value in state_hashes():
        if (objects_dir / value).is_file():
            queue.append(value)

    while queue:
        value = queue.pop()
        if value in in_use:
            continue
        in_use.add(value)
        text = (objects_dir / value).read_bytes().decode("utf-8", errors="replace")

        if text.startswith("object:"):
            children = [text.split("\n", 1)[0].split(":", 1)[1].strip()]
        elif is_commit_object(value):
            try:
                children = read_commit_parents(value) + list(get_commit_files(value).values())
            except (ValueError, OSError) as error:
                problems.append(f"commit {value[:7]} could not be read ({error})")
                continue
        else:
            children = []

        for child in children:
            if (objects_dir / child).is_file():
                queue.append(child)
            else:
                problems.append(f"{value[:7]} needs {child[:7]}, which is missing")
    return in_use, problems


def fsck_command():
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    problems = []
    names = stored_object_names()
    for name in names:
        if sha1_of_file(Path(".mygit/objects") / name) != name:
            problems.append(f"object {name[:7]} does not match its own hash (damaged)")
    in_use, walk_problems = walk_repository()
    problems += walk_problems

    if problems:
        print(f"Check found {len(problems)} problem(s):")
        for problem in problems:
            print(f"  - {problem}")
        print("Nothing was changed.")
        return
    unused = len([n for n in names if n not in in_use])
    print(f"Check passed: {len(names)} objects stored, {len(in_use)} in use, {unused} unused.")


def gc_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if any(arg != "--yes" for arg in args):
        print("Usage: python mygit.py gc          (shows what would be deleted)")
        print("       python mygit.py gc --yes    (deletes unused objects)")
        return
    yes = "--yes" in args

    in_use, problems = walk_repository()

    for name in stored_object_names():
        if sha1_of_file(Path(".mygit/objects")/name)!=name:
            problems.append(f"object {name[:7]} does not match its own hash (damaged)")
    if problems:
        print("The repository has problems, so nothing was deleted.")
        print("Run: python mygit.py fsck")
        return

    objects_dir = Path(".mygit/objects")
    unused = [n for n in stored_object_names() if n not in in_use]
    if not unused:
        print("Nothing to clean up. Every stored object is in use.")
        return

    if not yes:
        size = sum((objects_dir / n).stat().st_size for n in unused)
        print(f"Would delete {len(unused)} unused object(s), about {size} bytes:")
        for name in unused[:20]:
            print(f"  {name[:7]}")
        if len(unused) > 20:
            print(f"  ... and {len(unused) - 20} more")
        print("Nothing deleted. Run 'python mygit.py gc --yes' to delete them.")
        return

    deleted = 0
    for name in unused:
        try:
            (objects_dir / name).unlink()
            deleted += 1
        except OSError as error:
            print(f"Could not delete {name[:7]}: {error}")
    print(f"Deleted {deleted} unused object(s).")

# =========================
# REMOTES (Feature 13)
# =========================
REMOTES_FILE = Path(".mygit/remotes")


def read_remotes():
    """Return {name: folder} from .mygit/remotes (one 'name<TAB>folder' per line)."""
    remotes = {}
    if REMOTES_FILE.exists():
        for line in REMOTES_FILE.read_text(encoding="utf-8").splitlines():
            if "\t" in line:
                name, folder = line.split("\t", 1)
                remotes[name] = folder
    return remotes


def write_remotes(remotes):
    text = "".join(f"{name}\t{folder}\n" for name, folder in sorted(remotes.items()))
    atomic_write_text(REMOTES_FILE, text)


def valid_remote_name(name):
    return bool(name) and all(c.isalnum() or c in "-_" for c in name)


def remote_repo_path(folder_text):
    """Return the full folder of a remote if it holds a MyGit repository, else None."""
    folder = Path(folder_text).expanduser().resolve()
    if not (folder / ".mygit" / "HEAD").exists():
        return None
    return folder


def copy_missing_objects(source_objects, destination_objects):
    """Copy every stored object the destination does not have. Returns how many were copied."""
    if not source_objects.exists():
        return 0
    destination_objects.mkdir(parents=True, exist_ok=True)
    copied = 0
    for path in source_objects.iterdir():
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        target = destination_objects / path.name
        if target.exists():
            continue
        temp = destination_objects / (path.name + ".tmp")
        temp.write_bytes(path.read_bytes())
        os.replace(temp, target)
        copied += 1
    return copied


def remote_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return

    remotes = read_remotes()

    if not args or args == ["-v"]:
        if not remotes:
            print("No remotes yet. Add one: python mygit.py remote add <name> <folder>")
            return
        for name, folder in remotes.items():
            print(f"  {name}  {folder}")
        return

    if args[0] == "add" and len(args) == 3:
        name, folder_text = args[1], args[2]
        if not valid_remote_name(name):
            print(f"Invalid remote name: {name}. Use letters, numbers, - or _ only.")
            return
        if name in remotes:
            print(f"Remote '{name}' already exists. Remove it first. Nothing changed.")
            return
        folder = remote_repo_path(folder_text)
        if folder is None:
            print(f"'{folder_text}' is not a MyGit repository (no .mygit folder). Nothing changed.")
            return
        remotes[name] = str(folder)
        write_remotes(remotes)
        print(f"Added remote '{name}' -> {folder}")
        return

    if args[0] == "remove" and len(args) == 2:
        name = args[1]
        if name not in remotes:
            print(f"Remote '{name}' does not exist.")
            return
        del remotes[name]
        write_remotes(remotes)
        tracking = Path(".mygit/refs/remotes") / name
        if tracking.exists():
            for path in list(tracking.rglob("*")):
                if path.is_file():
                    path.unlink()
        print(f"Removed remote '{name}'. Its tracking branches were deleted.")
        return

    print("Usage: python mygit.py remote                    (list remotes)")
    print("       python mygit.py remote add <name> <folder>")
    print("       python mygit.py remote remove <name>")

# =========================
# PUSH (Feature 13, part 2)
# =========================
def push_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if merge_in_progress():
        return
    if not args or len(args) > 2 or args[0].startswith("-"):
        print("Usage: python mygit.py push <remote> [branch]")
        print("       (with no branch, the current branch is pushed)")
        return

    remote_name = args[0]
    remotes = read_remotes()
    if remote_name not in remotes:
        print(f"Remote '{remote_name}' does not exist. Add it: python mygit.py remote add <name> <folder>")
        return
    remote_folder = remote_repo_path(remotes[remote_name])
    if remote_folder is None:
        print(f"Remote '{remote_name}' is missing or is no longer a MyGit repository. Nothing changed.")
        return

    current_branch, _ = get_head()
    branch_name = args[1] if len(args) == 2 else current_branch
    if branch_name is None:
        print("Cannot push: HEAD is detached. Name a branch: python mygit.py push <remote> <branch>")
        return
    if (".." in branch_name or "/" in branch_name or "\\" in branch_name
            or branch_name.startswith("-")):
        print(f"Invalid branch name: {branch_name}")
        return

    local_ref = Path(".mygit/refs/heads") / branch_name
    if not local_ref.is_file():
        print(f"Branch '{branch_name}' does not exist locally. Nothing changed.")
        return
    local_tip = local_ref.read_text(encoding="utf-8").strip()
    if not is_commit_object(local_tip):
        print(f"Branch '{branch_name}' has no valid commit. Nothing changed.")
        return

    remote_ref = remote_folder / ".mygit" / "refs" / "heads" / branch_name
    remote_tip = remote_ref.read_text(encoding="utf-8").strip() if remote_ref.is_file() else ""

    if remote_tip == local_tip:
        print(f"Everything up to date: '{branch_name}' on {remote_name} is already at {local_tip[:7]}.")
        return

    # Fast-forward check: the remote's tip must be one of our commits.
    if remote_tip and remote_tip not in get_ancestors(local_tip):
        print(f"Rejected: '{branch_name}' on {remote_name} has commits that your branch does not include.")
        print("This would overwrite them (non-fast-forward). Fetch and merge first, then push again.")
        print("Nothing changed.")
        return

    try:
        copied = copy_missing_objects(Path(".mygit/objects"), remote_folder / ".mygit" / "objects")
        remote_ref.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(remote_ref, local_tip)
        tracking = Path(".mygit/refs/remotes") / remote_name / branch_name
        tracking.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(tracking, local_tip)
    except OSError as error:
        print(f"Push stopped: {error}. Run push again to retry.")
        return

    if remote_tip:
        print(f"Pushed '{branch_name}' to {remote_name} (fast-forward): {remote_tip[:7]} -> {local_tip[:7]}")
    else:
        print(f"Created branch '{branch_name}' on {remote_name} at {local_tip[:7]}.")
    print(f"Copied {copied} new object(s) to {remote_name}.")
    print(f"Tracking branch {remote_name}/{branch_name} is now at {local_tip[:7]}.")

# =========================
# FETCH AND PULL (Feature 13, part 3)
# =========================
def remote_branch_tips(remote_folder):
    """Return {branch_name: commit_hash} for every branch on the remote."""
    heads = remote_folder / ".mygit" / "refs" / "heads"
    tips = {}
    if heads.exists():
        for path in heads.rglob("*"):
            if path.is_file():
                value = path.read_text(encoding="utf-8").strip()
                tips[path.relative_to(heads).as_posix()] = value
    return tips


def fetch_remote(remote_name):
    """Copy missing objects from the remote, then update tracking branches.
    Returns (copied_count, update_lines), or None if the fetch was refused."""
    remotes = read_remotes()
    if remote_name not in remotes:
        print(f"Remote '{remote_name}' does not exist. Add it: python mygit.py remote add <name> <folder>")
        return None
    remote_folder = remote_repo_path(remotes[remote_name])
    if remote_folder is None:
        print(f"Remote '{remote_name}' is missing or is no longer a MyGit repository. Nothing changed.")
        return None

    tips = remote_branch_tips(remote_folder)
    try:
        # Copy the objects first, so every tracking branch we update points to stored commits.
        copied = copy_missing_objects(remote_folder / ".mygit" / "objects", Path(".mygit/objects"))
        updates = []
        for branch, tip in sorted(tips.items()):
            tracking = Path(".mygit/refs/remotes") / remote_name / branch
            old = tracking.read_text(encoding="utf-8").strip() if tracking.is_file() else ""
            if old == tip:
                continue
            tracking.parent.mkdir(parents=True, exist_ok=True)
            atomic_write_text(tracking, tip)
            if old:
                updates.append(f"  {remote_name}/{branch}: {old[:7]} -> {tip[:7]}")
            else:
                updates.append(f"  {remote_name}/{branch}: new ({tip[:7]})")
    except OSError as error:
        print(f"Fetch stopped: {error}. Run fetch again to retry.")
        return None
    return copied, updates


def fetch_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if merge_in_progress():
        return
    if len(args) != 1 or args[0].startswith("-"):
        print("Usage: python mygit.py fetch <remote>")
        return

    result = fetch_remote(args[0])
    if result is None:
        return
    copied, updates = result
    if updates:
        print(f"Fetched from {args[0]}:")
        for line in updates:
            print(line)
    else:
        print(f"Already up to date with {args[0]}.")
    print(f"Copied {copied} new object(s) from {args[0]}.")
    print("Your files and branches were not changed.")


def pull_command(args):
    if not Path(".mygit/HEAD").exists():
        print("Repository not initialized.")
        return
    if merge_in_progress():
        return
    if len(args) != 1 or args[0].startswith("-"):
        print("Usage: python mygit.py pull <remote>")
        return

    remote_name = args[0]
    current_branch, current_commit = get_head()
    if current_branch is None:
        print("Cannot pull: detached HEAD is not supported yet.")
        return
    if not current_commit:
        print("Cannot pull: this branch has no commits yet.")
        return

    result = fetch_remote(remote_name)
    if result is None:
        return
    copied, updates = result
    for line in updates:
        print(line)

    tracking = Path(".mygit/refs/remotes") / remote_name / current_branch
    if not tracking.is_file():
        print(f"'{remote_name}' has no branch '{current_branch}'. Push it first: "
              f"python mygit.py push {remote_name} {current_branch}")
        return
    remote_tip = tracking.read_text(encoding="utf-8").strip()

    if remote_tip == current_commit:
        print(f"'{current_branch}' is already up to date with {remote_name}/{current_branch}.")
        return
    if remote_tip in get_ancestors(current_commit):
        print(f"Your '{current_branch}' is ahead of {remote_name}/{current_branch}. Nothing to pull.")
        print(f"Share your commits: python mygit.py push {remote_name} {current_branch}")
        return

    if current_commit not in get_ancestors(remote_tip):
        print(f"Cannot fast-forward: '{current_branch}' and {remote_name}/{current_branch} have both changed.")
        print(f"Merge them with: python mygit.py merge {remote_name}/{current_branch}")
        print("Nothing was changed.")
        return

    # Fast-forward: the remote simply has newer commits on top of ours.
    head_files = get_commit_files(current_commit)
    target_files = get_commit_files(remote_tip)
    current_ref = Path(".mygit/refs/heads") / current_branch

    def finish():
        atomic_write_text(current_ref, remote_tip)

    if not update_working_tree(head_files, target_files, finish):
        print("Pull cancelled. Nothing changed.")
        return
    print(f"Pulled {remote_name}/{current_branch} into '{current_branch}' (fast-forward).")
    print(f"'{current_branch}' is now at {remote_tip[:7]}")

# =========================
# OPERATION NAME (Feature 14)
# =========================
def operation_name():
    """Return the name of the operation in progress, for messages."""
    kind = merge_kind()
    if kind == "cherry-pick":
        return "Cherry-pick"
    if kind == "rebase":
        return "Rebase"
    return "Merge"


# MAIN
# =========================
def main():
    if len(sys.argv) < 2:
        print("Usage: python mygit.py <command>")
        return
    command = sys.argv[1]
    set_reflog_action(" ".join(sys.argv[1:]))
    # INIT
    if command == "init":
        init_repository()
    # STATUS
    elif command == "status":
        status()
    # HASH
    elif command == "hash":
        filename = sys.argv[2]
        print(hash_file(filename))

    # COMMIT
    elif command == "commit":
        if len(sys.argv) < 4 or sys.argv[2] != "-m":
            print('Usage: python mygit.py commit -m "message"')
            return
        message = sys.argv[3]
        create_commit(message)
    # LOG
    elif command == "log":
        show_log()
    # DIFF
    elif command == "diff":
        diff_command(sys.argv[2:])
        
    elif command == "branch":
        if len(sys.argv) == 2:
           branch()

        else:
           branch(sys.argv[2])

    elif command == "checkout":

        if len(sys.argv) < 3:
            print("Usage: python mygit.py checkout <branch>")
            return

        branch_name = sys.argv[2]

        checkout_branch(branch_name)

    elif command == "merge":
        if len(sys.argv) < 3:
            print("Usage: python mygit.py merge <branch>")
            print("       python mygit.py merge --abort")
            print("       python mygit.py merge --continue")
            return
        if sys.argv[2] == "--abort":
            merge_abort()
        elif sys.argv[2] == "--continue":
            merge_continue()
        else:
            merge_branch(sys.argv[2])

    elif command == "reset":
        reset_command(sys.argv[2:])

    elif command == "restore":
        restore_command(sys.argv[2:])

    elif command == "rm":

        if len(sys.argv) < 3:
           print("Usage: python mygit.py rm <filename>")
           return

        filename = sys.argv[2]

        remove_file(filename)

    elif command == "show":

        if len(sys.argv) < 3:
           print("Usage: python mygit.py show <commit_hash>")
           return

        commit_hash = sys.argv[2]

        show_commit(commit_hash)  

    elif command == "tag":
        tag_command(sys.argv[2:])

    elif command == "tag-list":
        tag_list_command()

    elif command == "tag-show":
        tag_show_command(sys.argv[2:])

    elif command == "tag-delete":
        tag_delete_command(sys.argv[2:])

    elif command == "fsck":
        fsck_command()

    elif command == "gc":
        gc_command(sys.argv[2:])

    elif command == "branch-delete":

        if len(sys.argv) < 3:
             print("Usage: python mygit.py branch-delete <branch_name>")
             return

        branch_name = sys.argv[2]

        delete_branch(branch_name)   

    elif command == "revert":

        if len(sys.argv) < 3:
            print("Usage: python mygit.py revert <commit_hash>")
            return

        commit_hash = sys.argv[2]

        revert_commit(commit_hash)

    elif command == "add":
        if len(sys.argv) < 3:
            print("Usage: python mygit.py add <filename>")
            return

        add_file(sys.argv[2])

    elif command == "config":
        config_command(sys.argv[2:])

    elif command == "conflicts":
        conflicts_command(sys.argv[2:])

    elif command == "resolve":
        resolve_command(sys.argv[2:])

    elif command == "stash":
        stash_command(sys.argv[2:])

    elif command == "cherry-pick":
        cherry_pick_command(sys.argv[2:])

    elif command == "rebase":
        rebase_command(sys.argv[2:])

    elif command == "reflog":
        reflog_command(sys.argv[2:])

    elif command == "remote":
        remote_command(sys.argv[2:])

    elif command == "push":
        push_command(sys.argv[2:])

    elif command == "fetch":
        fetch_command(sys.argv[2:])

    elif command == "pull":
        pull_command(sys.argv[2:])

        
    # UNKNOWN COMMAND
    else:
     print(f"Unknown command: {command}")
# =========================
# PROGRAM START
# =========================
if __name__ == "__main__":
    main()