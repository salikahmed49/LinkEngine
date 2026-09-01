# 🚀 Git, GitHub, Render & Vercel Deployment Guide

Complete step-by-step guide to push this codebase to GitHub and deploy the fullstack platform across **Render** (Backend API + Worker + Postgres + Redis) and **Vercel** (React Frontend).

---

## 🐙 Part 1: How to Push Code to GitHub via Git

### Step 1: Open PowerShell / Terminal in Project Directory
```powershell
cd c:\Users\salik\Documents\link-analytics-platform
```

### Step 2: Initialize Git and Check Untracked Files
```powershell
git status
```

### Step 3: Add All Files to Git Staging
```powershell
git add .
```

### Step 4: Create the Initial Commit
```powershell
git commit -m "feat: complete distributed link analytics platform (Phases 1-7)"
```

### Step 5: Rename Branch to `main`
```powershell
git branch -M main
```

### Step 6: Create a New Repository on GitHub
1. Go to [https://github.com/new](https://github.com/new).
2. Set repository name: `link-analytics-platform`.
3. Set visibility: **Public**.
4. Leave *"Initialize this repository with a README"* **unchecked** (we already have a complete README).
5. Click **Create repository**.

### Step 7: Link Your Local Repository to GitHub and Push
*(Replace `<your-username>` with your actual GitHub username)*:
```powershell
git remote add origin https://github.com/<your-username>/link-analytics-platform.git
git push -u origin main
```

---

## ☁️ Part 2: Deploying the Backend on Render

The repository includes a ready-to-use [`render.yaml`](file:///c:/Users/salik/Documents/link-analytics-platform/render.yaml) Blueprint that automatically provisions:
1. **FastAPI Web Service** (`link-analytics-api`)
2. **ClickConsumer Background Worker** (`link-analytics-worker`)
3. **Managed PostgreSQL** (`link-analytics-db`)
4. **Managed Redis** (`link-analytics-redis`)

### 1-Click Blueprint Deployment (Recommended)
1. Log in to [https://render.com](https://render.com).
2. In the Render Dashboard, click **New +** $\rightarrow$ **Blueprint**.
3. Connect your GitHub repository: `link-analytics-platform`.
4. Render will automatically detect `render.yaml` and display the 4 services it will create.
5. Click **Apply**.
6. Once deployed, copy your public Web API URL (e.g., `https://link-analytics-api-xxxx.onrender.com`).

---

## ⚡ Part 3: Deploying the Frontend on Vercel

### Step 1: Import Project into Vercel
1. Log in to [https://vercel.com](https://vercel.com).
2. Click **Add New...** $\rightarrow$ **Project**.
3. Select your GitHub repository: `link-analytics-platform`.

### Step 2: Configure Project Settings
In the Vercel project configuration screen:
- **Framework Preset**: `Vite`
- **Root Directory**: Click *Edit* and select **`frontend`**.
- **Build Command**: `npm run build` (or leave default)
- **Output Directory**: `dist` (or leave default)

### Step 3: Add Environment Variable
Under **Environment Variables**, add:
- **Name**: `VITE_API_URL`
- **Value**: Your Render backend URL (e.g., `https://link-analytics-api-xxxx.onrender.com` without trailing slash).

### Step 4: Deploy
1. Click **Deploy**.
2. Vercel will build and assign your production URL (e.g. `https://link-analytics-frontend.vercel.app`).
3. Open the URL — your React frontend is now live and talking to your Render backend cluster!
