#!/usr/bin/env python3
"""Migration script to replace Rich CLI with Textual CLI."""

import os
import shutil
import sys

def backup_old_files():
    """Backup old Rich-based files."""
    files_to_backup = [
        "orchestrator_cli.py",
        "orchestrator_cli_rich.py",
        "src/utils/ui/rich_console.py",
        "src/utils/ui/rich_display.py"
    ]
    
    backup_dir = "backup_rich_ui"
    os.makedirs(backup_dir, exist_ok=True)
    
    for file_path in files_to_backup:
        if os.path.exists(file_path):
            backup_path = os.path.join(backup_dir, os.path.basename(file_path))
            shutil.copy2(file_path, backup_path)
            print(f"✓ Backed up {file_path} to {backup_path}")
        else:
            print(f"⚠ File not found: {file_path}")

def replace_main_cli():
    """Replace the main CLI with Textual version."""
    if os.path.exists("orchestrator_cli.py"):
        shutil.move("orchestrator_cli.py", "orchestrator_cli_rich_old.py")
        print("✓ Moved old CLI to orchestrator_cli_rich_old.py")
    
    shutil.copy2("orchestrator_cli_textual.py", "orchestrator_cli.py")
    print("✓ Replaced main CLI with Textual version")

def update_readme():
    """Update any README or documentation."""
    readme_content = """# Orchestrator CLI

## New Textual-Based UI

The CLI has been migrated to use Textual for better real-time updates and a more reliable UI.

### Usage

```bash
# Run the main CLI
python3 orchestrator_cli.py

# Or run the Textual version directly
python3 orchestrator_cli_textual.py
```

### Features

- **Real-time plan updates** - No more duplicate panels
- **Better SSE handling** - Proper event processing
- **Improved UI** - Clean, responsive terminal interface
- **Robust state management** - Single source of truth for all UI state

### Migration

Old Rich-based files have been backed up to `backup_rich_ui/`:
- orchestrator_cli.py (old Rich version)
- orchestrator_cli_rich.py 
- src/utils/ui/rich_console.py
- src/utils/ui/rich_display.py

### Testing

Run the test script to verify functionality:
```bash
python3 test_textual_ui.py
```
"""
    
    with open("TEXTUAL_MIGRATION.md", "w") as f:
        f.write(readme_content)
    
    print("✓ Created TEXTUAL_MIGRATION.md with migration notes")

def main():
    """Main migration process."""
    print("🚀 Starting migration to Textual CLI...")
    print()
    
    # Step 1: Backup old files
    print("Step 1: Backing up old Rich-based files...")
    backup_old_files()
    print()
    
    # Step 2: Replace main CLI
    print("Step 2: Replacing main CLI with Textual version...")
    replace_main_cli()
    print()
    
    # Step 3: Update documentation
    print("Step 3: Updating documentation...")
    update_readme()
    print()
    
    print("✅ Migration completed successfully!")
    print()
    print("Next steps:")
    print("1. Test the new CLI: python3 orchestrator_cli.py")
    print("2. Run unit tests: python3 test_textual_ui.py")
    print("3. Check TEXTUAL_MIGRATION.md for more details")
    print()
    print("If you encounter issues, the old files are backed up in backup_rich_ui/")

if __name__ == "__main__":
    main()