#!/usr/bin/env python3
"""Script to fix long lines in Python files."""

import re
import sys
from pathlib import Path


def fix_long_lines(file_path: Path, max_length: int = 79) -> None:
    """Fix long lines in a Python file."""
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    fixed_lines = []
    for i, line in enumerate(lines, 1):
        if len(line.rstrip()) > max_length:
            # Try to break long lines
            if '"""' in line and line.strip().startswith('"""'):
                # Docstring line - break it
                content = line.strip()[3:-3] if line.strip().endswith('"""') else line.strip()[3:]
                if len(content) > max_length - 6:  # Account for """ and spaces
                    # Break the docstring
                    words = content.split()
                    new_lines = []
                    current_line = '    """'
                    for word in words:
                        if len(current_line + ' ' + word) > max_length - 3:
                            new_lines.append(current_line)
                            current_line = '    ' + word
                        else:
                            current_line += ' ' + word if current_line != '    """' else word
                    if current_line:
                        new_lines.append(current_line)
                    if line.strip().endswith('"""'):
                        new_lines[-1] += '"""'
                    fixed_lines.extend([line + '\n' for line in new_lines])
                else:
                    fixed_lines.append(line)
            elif 'raise ImproperlyConfigured(' in line:
                # Break long error messages
                indent = len(line) - len(line.lstrip())
                content = line.strip()
                if content.startswith('raise ImproperlyConfigured('):
                    # Extract the message
                    msg_start = content.find('(') + 1
                    msg_end = content.rfind(')')
                    if msg_end > msg_start:
                        msg = content[msg_start:msg_end]
                        if len(msg) > max_length - indent - 30:  # Account for raise statement
                            # Break the message
                            words = msg.split()
                            new_lines = []
                            current_line = ' ' * indent + 'raise ImproperlyConfigured('
                            for word in words:
                                if len(current_line + ' ' + word) > max_length - 1:
                                    new_lines.append(current_line)
                                    current_line = ' ' * (indent + 4) + word
                                else:
                                    current_line += ' ' + word if current_line != ' ' * indent + 'raise ImproperlyConfigured(' else word
                            if current_line:
                                new_lines.append(current_line + ')')
                            fixed_lines.extend([line + '\n' for line in new_lines])
                        else:
                            fixed_lines.append(line)
                    else:
                        fixed_lines.append(line)
                else:
                    fixed_lines.append(line)
            else:
                # Generic line breaking
                if ' ' in line:
                    words = line.split()
                    new_lines = []
                    current_line = ''
                    for word in words:
                        if len(current_line + ' ' + word) > max_length:
                            if current_line:
                                new_lines.append(current_line + '\n')
                            current_line = word
                        else:
                            current_line += ' ' + word if current_line else word
                    if current_line:
                        new_lines.append(current_line + '\n')
                    fixed_lines.extend(new_lines)
                else:
                    fixed_lines.append(line)
        else:
            fixed_lines.append(line)
    
    with open(file_path, 'w', encoding='utf-8') as f:
        f.writelines(fixed_lines)


def main():
    """Main function."""
    tink_fields_dir = Path('tink_fields')
    for py_file in tink_fields_dir.rglob('*.py'):
        print(f"Fixing {py_file}")
        fix_long_lines(py_file)


if __name__ == '__main__':
    main()
