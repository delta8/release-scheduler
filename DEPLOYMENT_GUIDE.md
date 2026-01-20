# Setup Guide: Deploy to GitHub and Render.com

## What You'll Do

1. Create a GitHub repository (free)
2. Push your code to GitHub
3. Deploy to Render.com (free hosting)
4. Share a live URL with your manager

**Total time: ~15 minutes**

---

## Step 1: Create GitHub Repository

1. Go to **https://github.com/new**
2. Enter repository details:
   - **Repository name**: `release-scheduler`
   - **Description**: `Clinical Analytics Workload Assessment`
   - **Visibility**: PUBLIC (required for free Render deployment)
3. Click **"Create repository"**

Your new repo URL will be: `https://github.com/delta8/release-scheduler`

---

## Step 2: Push Code to GitHub

### From Terminal (easiest)

1. Open Terminal
2. Navigate to your project folder:
   ```bash
   cd /tmp/release-scheduler-github
   ```

3. Initialize and push:
   ```bash
   git init
   git add .
   git commit -m "Initial commit: Clinical Analytics dashboard"
   git remote add origin https://github.com/delta8/release-scheduler.git
   git branch -M main
   git push -u origin main
   ```

4. Enter your GitHub credentials when prompted

**Done!** Your code is now on GitHub.

---

## Step 3: Deploy to Render.com (Free)

### Sign Up
1. Go to **https://render.com**
2. Click **"Sign up"**
3. Select **"Sign up with GitHub"**
4. Authorize Render to access your GitHub account
5. Complete signup

### Create Web Service
1. Click **"New +"** → **"Web Service"**
2. Find and select **`release-scheduler`** repo
3. Fill in the settings:
   - **Name**: `release-scheduler` (auto-filled)
   - **Environment**: `Python 3`
   - **Build command**: `pip install -r requirements.txt`
   - **Start command**: `gunicorn release_scheduler_v2:server`
4. Click **"Create Web Service"**

### Wait for Deployment
- Render builds and deploys your app (~2 minutes)
- You'll see logs as it progresses
- When done, you'll get a URL like: `https://release-scheduler.onrender.com`

---

## Step 4: Share with Your Manager

Copy this URL and send to your manager:
```
https://release-scheduler.onrender.com
```

They can:
1. Open the URL in any browser
2. Upload CSVs
3. Use the dashboard
4. **No installation needed!**

---

## Troubleshooting

### Git commands don't work
- Make sure you have Git installed: `git --version`
- If not: Install from https://git-scm.com/

### GitHub push fails
- Make sure you created the repo on GitHub first
- Check your username is correct in the URL
- Use Personal Access Token if password doesn't work

### Render deployment fails
- Check the build logs on Render
- Make sure all files (especially `requirements.txt`) are in the repo
- Verify `Procfile` is present

### App loads but no data
- Upload CSV files using the dashboard
- Check for error messages in Render logs

---

## File Contents

| File | Purpose |
|------|---------|
| `release_scheduler_v2.py` | Main application |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Render how to run the app |
| `.gitignore` | Which files to skip in Git |
| `README.md` | Project description |

---

## What's Happening

1. **GitHub**: Acts as your code backup and source for deployment
2. **Render**: Reads code from GitHub and runs it on their servers
3. **Your Manager**: Accesses the live app via the URL you send

No local Python needed for your manager—everything runs in the cloud!

---

## Next Steps After Deployment

### Monitor Your App
- Go to Render dashboard to check logs
- App automatically restarts if it crashes

### Update Code
- Make changes locally
- Push to GitHub: `git add . && git commit -m "message" && git push`
- Render auto-deploys within 1-2 minutes

### Custom Domain (Optional)
- Render lets you add your own domain for free tier
- Settings → Custom Domain

---

## Common Questions

**Q: Will my manager need Python?**  
A: No! They just open the URL in their browser.

**Q: Does it cost money?**  
A: No! Both GitHub and Render free tiers work perfectly.

**Q: How long does the app stay online?**  
A: Forever (as long as you keep the Render account).

**Q: Can multiple people use it at once?**  
A: Yes! Render handles multiple users automatically.

---

**Ready? Start with GitHub Setup above!**
