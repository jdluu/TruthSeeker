#!/bin/bash

# Exclude the project package named 'truthseeker' from upgrades
packages=$(uv tree | awk '/^[a-zA-Z0-9\-]+/ && $1 != "truthseeker" {print $1}')

# Upgrade each package via uv
for pkg in $packages
do
  echo "Upgrading $pkg..."
  uv add --upgrade "$pkg"
done

# Synchronize environment with updated packages
uv sync

# Export freeze to requirements.txt for legacy compatibility
echo "Exporting dependencies to requirements.txt..."
pip freeze > requirements.txt

echo "All packages upgraded and requirements.txt updated."
