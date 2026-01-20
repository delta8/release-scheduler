#!/bin/bash

# Clinical Analytics - GitHub Setup Guide
# Run these commands in order to push your code to GitHub

echo "=========================================="
echo "Clinical Analytics - GitHub Setup"
echo "=========================================="
echo ""

# Check if we're in the right directory
if [ ! -f "release_scheduler_v2.py" ]; then
    echo "ERROR: release_scheduler_v2.py not found in current directory"
    echo "Please run this script from the release-scheduler-github directory"
    exit 1
fi

echo "✓ Found release_scheduler_v2.py"
echo ""

echo "STEP 1: Create GitHub Repository"
echo "=================================="
echo "1. Go to: https://github.com/new"
echo "2. Repository name: release-scheduler"
echo "3. Description: Clinical Analytics Workload Assessment"
echo "4. Make it PUBLIC (for Render deployment)"
echo "5. Click 'Create repository'"
echo ""
echo "Press Enter when done..."
read

echo ""
echo "STEP 2: Initialize Local Git Repository"
echo "========================================"

# Initialize git
git init
git add .
git commit -m "Initial commit: Clinical Analytics dashboard"

echo ""
echo "STEP 3: Add Remote and Push"
echo "============================"
echo "Copy-paste this command (replace delta8 with your GitHub username):"
echo ""
echo "git remote add origin https://github.com/delta8/release-scheduler.git"
echo "git branch -M main"
echo "git push -u origin main"
echo ""
echo "Press Enter when ready to continue..."
read

# Run the commands
git remote add origin https://github.com/delta8/release-scheduler.git
git branch -M main
git push -u origin main

echo ""
echo "=========================================="
echo "✓ Code pushed to GitHub!"
echo "=========================================="
echo ""
echo "Next steps for online deployment:"
echo "1. Go to https://render.com"
echo "2. Sign in with GitHub"
echo "3. Create new 'Web Service'"
echo "4. Connect your 'release-scheduler' repo"
echo "5. Set runtime: Python"
echo "6. Build command: pip install -r requirements.txt"
echo "7. Start command: gunicorn release_scheduler_v2:server"
echo "8. Click 'Deploy'"
echo ""
echo "In ~2 minutes, you'll get a live URL to share with your manager!"
echo ""
