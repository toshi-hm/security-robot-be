#!/usr/bin/env python3
"""
Script to convert map_generator.py from [x][y] to [y][x] indexing.
This is a helper script to identify all the changes needed.
"""

import re

# Read the file
with open('/home/maya/work/security-robot-be/rl/environments/map_generator.py', 'r') as f:
    content = f.read()

# Pattern 1: Grid initialization - swap width and height
# [[False for _ in range(self.height)] for _ in range(self.width)]
# -> [[False for _ in range(self.width)] for _ in range(self.height)]
pattern1 = r'\[\[([^\]]+) for _ in range\(self\.height\)\] for _ in range\(self\.width\)\]'
replacement1 = r'[[\1 for _ in range(self.width)] for _ in range(self.height)]'
content = re.sub(pattern1, replacement1, content)

# Pattern 2: Loop order - swap i/j or x/y loops
# This is more complex and needs manual review

# Pattern 3: Access patterns obstacles[i][j] where i is width-based, j is height-based
# This requires understanding the context

print("Modified content preview (first 2000 chars):")
print(content[:2000])

# Write to a temp file for review
with open('/tmp/map_generator_converted.py', 'w') as f:
    f.write(content)

print("\nWrote converted file to /tmp/map_generator_converted.py")
print("Please review before applying!")
