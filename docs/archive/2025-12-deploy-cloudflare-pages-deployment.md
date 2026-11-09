# Cloudflare Pages Deployment Guide

This guide walks through deploying the React frontend to Cloudflare Pages.

## Prerequisites

- Cloudflare account
- GitHub repository with the code
- Custom domain configured in Cloudflare (optional)

## Method 1: Via Cloudflare Dashboard (Recommended)

### Step 1: Connect GitHub Repository

1. Log in to [Cloudflare Dashboard](https://dash.cloudflare.com/)
2. Go to **Pages** in the sidebar
3. Click **Create a project**
4. Choose **Connect to Git**
5. Select your GitHub repository: `nomadkaraoke/karaoke-gen`
6. Authorize Cloudflare to access the repository

### Step 2: Configure Build Settings

Set the following build configuration:

- **Project name**: `karaoke-gen-frontend` (or your choice)
- **Production branch**: `main` (or your default branch)
- **Framework preset**: `Vite`
- **Build command**: `cd frontend-react && npm install && npm run build`
- **Build output directory**: `frontend-react/dist`
- **Root directory**: `/` (repository root)

### Step 3: Environment Variables

Add the following environment variable:

- **Variable name**: `VITE_API_URL`
- **Value**: `https://your-cloud-run-service-url/api`

Replace `your-cloud-run-service-url` with your actual Cloud Run service URL.

### Step 4: Deploy

Click **Save and Deploy**. Cloudflare will:
1. Clone your repository
2. Install dependencies
3. Build the React app
4. Deploy to their CDN
5. Provide you with a URL (e.g., `karaoke-gen-frontend.pages.dev`)

### Step 5: Custom Domain (Optional)

To use `gen.nomadkaraoke.com`:

1. In the Pages project, go to **Custom domains**
2. Click **Set up a custom domain**
3. Enter `gen.nomadkaraoke.com`
4. Cloudflare will guide you through DNS setup
5. If domain is already in Cloudflare, it will automatically configure DNS

## Method 2: Via Wrangler CLI

### Install Wrangler

```bash
npm install -g wrangler
```

### Authenticate

```bash
wrangler login
```

### Build and Deploy

```bash
# Build the React app
cd frontend-react
npm install
npm run build

# Deploy to Cloudflare Pages
npx wrangler pages deploy dist --project-name=karaoke-gen-frontend
```

### Set Environment Variables

```bash
wrangler pages project create karaoke-gen-frontend

# Add environment variable
wrangler pages env set VITE_API_URL https://your-cloud-run-service-url/api --project-name=karaoke-gen-frontend
```

## Continuous Deployment

Once connected to GitHub, Cloudflare Pages will automatically:

- Deploy on every push to the main branch
- Create preview deployments for pull requests
- Provide unique URLs for each deployment

### Configure Branch Deployments

In the Pages project settings:

1. **Production branch**: Set to your main branch (usually `main` or `master`)
2. **Preview deployments**: Enable for all branches or specific ones
3. **Build configuration**: Saved from initial setup

## Environment-Specific Configuration

### Production Environment

Create `.env.production` in `frontend-react/`:

```
VITE_API_URL=https://your-cloud-run-production-url/api
```

This will be used during production builds.

### Preview/Staging Environment

You can set different environment variables for preview deployments in Cloudflare Pages settings.

## Monitoring Deployments

### View Build Logs

1. Go to your Pages project in Cloudflare Dashboard
2. Click on a deployment
3. View **Build logs** for detailed output
4. Check for any build errors or warnings

### Deployment Status

- **Success**: Green checkmark, site is live
- **Failed**: Red X, check build logs
- **Building**: In progress

## Rollback

To rollback to a previous deployment:

1. Go to **Deployments** tab in your Pages project
2. Find the deployment you want to rollback to
3. Click **...** (three dots)
4. Select **Rollback to this deployment**

## Performance Optimization

Cloudflare Pages automatically provides:

- **Global CDN**: Content served from edge locations worldwide
- **HTTP/2 & HTTP/3**: Fast protocol support
- **Automatic minification**: HTML, CSS, and JS compression
- **Brotli compression**: Smaller file sizes
- **Preview deployments**: Test before production

## Custom Domain Setup Details

### DNS Configuration

For `gen.nomadkaraoke.com`:

#### If domain is in Cloudflare:
1. Cloudflare automatically creates a CNAME record
2. Points to your Pages deployment
3. SSL certificate is automatically provisioned

#### If domain is external:
1. Add CNAME record: `gen` → `karaoke-gen-frontend.pages.dev`
2. Or use Cloudflare nameservers for full integration

### SSL Certificate

Cloudflare automatically provisions and renews SSL certificates for custom domains. No manual configuration needed.

## Troubleshooting

### Build Fails

**Check build command:**
```bash
cd frontend-react && npm install && npm run build
```

**Verify output directory:**
```
frontend-react/dist
```

### Environment Variable Not Working

- Ensure variable name starts with `VITE_` prefix
- Rebuild after changing environment variables
- Check in build logs that variable is set

### 404 Errors

- Ensure `dist` directory is correctly specified
- Check that `index.html` exists in output
- Verify build completed successfully

### API Connection Issues

- Verify `VITE_API_URL` is correct
- Check CORS settings on Cloud Run backend
- Test API endpoint directly with curl

## Cost

Cloudflare Pages pricing:

- **Free tier**: 
  - 500 builds per month
  - Unlimited requests
  - Unlimited bandwidth
- **Paid tier** ($20/month):
  - 5,000 builds per month
  - Concurrent builds
  - Additional features

For most use cases, the free tier is sufficient.

## Next Steps

After successful deployment:

1. Test the frontend at your Cloudflare Pages URL
2. Verify API connectivity to Cloud Run backend
3. Configure custom domain if desired
4. Set up monitoring and analytics
5. Enable Web Analytics in Cloudflare (optional)

## Additional Resources

- [Cloudflare Pages Documentation](https://developers.cloudflare.com/pages/)
- [Vite Deployment Guide](https://vitejs.dev/guide/static-deploy.html)
- [React Deployment Best Practices](https://react.dev/learn/start-a-new-react-project#deploying-to-production)

