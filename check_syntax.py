import os
import sys
import compileall

def check_syntax(start_dir):
    print(f"Checking Python syntax in {start_dir}...")
    success = compileall.compile_dir(start_dir, force=True, quiet=1)
    if success:
        print("No Python syntax errors found.")
    else:
        print("Python syntax errors found.")
        sys.exit(1)

if __name__ == "__main__":
    check_syntax(".")
