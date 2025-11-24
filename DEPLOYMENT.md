# 🚀 Bonds Screener - Deployment Guide

Complete guide for deploying the Bonds Screener application.

---

## 📋 Prerequisites

### Required Software
- **Docker Desktop** (Windows/macOS) or **Docker Engine** (Linux)
  - Download: https://www.docker.com/get-started
  - Version: 20.10+
- **Docker Compose**
  - Version: 2.0+ (included with Docker Desktop)

### System Requirements
- **Minimum**: 2 CPU cores, 4GB RAM, 2GB disk space
- **Recommended**: 4 CPU cores, 8GB RAM, 5GB disk space

---

## 🎯 Quick Start (One Command!)

### Windows
```bash
start.bat
```

### Linux/macOS
```bash
chmod +x start.sh
./start.sh
```

**That's it!** The application will:
1. ✅ Check Docker is installed and running
2. ✅ Build both backend and frontend images
3. ✅ Start all services
4. ✅ Run health checks
5. ✅ Display access URLs

---

## 🌐 Access URLs

Once deployed, access the application at:

| Service | URL | Description |
|---------|-----|-------------|
| **Frontend** | http://localhost:80 | Main application UI |
| **Backend API** | http://localhost:8000 | REST API |
| **API Docs (Swagger)** | http://localhost:8000/docs | Interactive API documentation |
| **API Docs (ReDoc)** | http://localhost:8000/redoc | Alternative API documentation |

---

## 🔧 Manual Deployment

If you prefer manual control:

### 1. Build Images
```bash
docker-compose build
```

### 2. Start Services
```bash
docker-compose up -d
```

### 3. Check Status
```bash
docker-compose ps
```

### 4. View Logs
```bash
# All services
docker-compose logs -f

# Backend only
docker-compose logs -f backend

# Frontend only
docker-compose logs -f frontend
```

### 5. Stop Services
```bash
docker-compose down
```

---

## 🐳 Docker Configuration

### Services

#### Backend Service
- **Image**: Custom FastAPI application
- **Port**: 8000
- **Health Check**: GET /health every 30s
- **Restart Policy**: unless-stopped

#### Frontend Service
- **Image**: Custom React + nginx
- **Port**: 80
- **Health Check**: GET /health every 30s
- **Restart Policy**: unless-stopped
- **Depends On**: Backend (waits for backend to be healthy)

### Volumes
- `./backend/data:/app/data:ro` - Bond data files (read-only)

### Networks
- `bonds-network` - Bridge network for inter-service communication

---

## ⚙️ Configuration

### Environment Variables

Create a `.env` file in the root directory (or use `.env.example`):

```bash
# Backend Configuration
BACKEND_PORT=8000
CORS_ORIGINS=http://localhost,http://localhost:80

# Frontend Configuration
FRONTEND_PORT=80
VITE_API_BASE_URL=http://localhost:8000

# Data Directory
DATA_DIR=./backend/data
```

### Custom Ports

To use different ports, modify `docker-compose.yml`:

```yaml
services:
  backend:
    ports:
      - "8080:8000"  # Change 8080 to your desired port
  
  frontend:
    ports:
      - "3000:80"  # Change 3000 to your desired port
```

Then update environment variables accordingly.

---

## 🔍 Health Checks

Both services include health checks:

### Backend Health Check
```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

### Frontend Health Check
```bash
curl http://localhost:80/health
# Expected: OK
```

### Docker Health Status
```bash
docker-compose ps
# Should show "healthy" for both services
```

---

## 🐛 Troubleshooting

### Docker Not Running
**Windows/macOS:**
1. Open Docker Desktop
2. Wait for Docker to start
3. Look for green "Docker is running" indicator

**Linux:**
```bash
sudo systemctl start docker
```

### Port Already in Use
If ports 80 or 8000 are already in use:

1. **Option A**: Stop the conflicting service
2. **Option B**: Change ports in `docker-compose.yml` (see Configuration section)

### Services Not Starting
1. Check logs:
```bash
docker-compose logs
```

2. Rebuild images:
```bash
docker-compose build --no-cache
docker-compose up -d
```

3. Check Docker resources:
- Ensure Docker has sufficient CPU and memory allocated
- Docker Desktop: Settings → Resources

### Frontend Can't Connect to Backend
1. Check backend is running:
```bash
docker-compose ps backend
```

2. Check backend health:
```bash
curl http://localhost:8000/health
```

3. Check CORS configuration in `backend/app/config.py`

### Data Not Loading
1. Verify data files exist:
```bash
ls -la backend/data/
# Should show: bonds.json, columns.json, describe.json
```

2. Check file permissions (Linux/macOS):
```bash
chmod -R 644 backend/data/*.json
```

---

## 🔄 Updates & Maintenance

### Update Application Code
```bash
# Stop services
docker-compose down

# Pull latest code (if using git)
git pull

# Rebuild images
docker-compose build

# Start services
docker-compose up -d
```

### Update Data Files
1. Place new JSON files in `backend/data/`
2. Restart backend:
```bash
docker-compose restart backend
```

### View Resource Usage
```bash
docker stats
```

### Clean Up
Remove all containers, networks, and unused images:
```bash
docker-compose down
docker system prune -a
```

---

## 📊 Monitoring

### Check Service Logs
```bash
# Real-time logs
docker-compose logs -f

# Last 100 lines
docker-compose logs --tail=100

# Specific service
docker-compose logs -f backend
```

### Check Container Stats
```bash
docker stats bonds-screener-backend bonds-screener-frontend
```

### Health Check Status
```bash
docker inspect --format='{{.State.Health.Status}}' bonds-screener-backend
docker inspect --format='{{.State.Health.Status}}' bonds-screener-frontend
```

---

## 🔒 Security Considerations

### Production Deployment

1. **Change Default Ports**: Don't use port 80 in production
2. **Use HTTPS**: Set up nginx with SSL certificates
3. **Firewall**: Only expose necessary ports
4. **Environment Variables**: Use secrets management (Docker secrets, Kubernetes secrets)
5. **Update CORS**: Restrict CORS origins to your domain
6. **Regular Updates**: Keep Docker images and dependencies updated

### Example Production CORS Configuration
Edit `backend/app/config.py`:
```python
CORS_ORIGINS: List[str] = [
    "https://yourdomain.com",
    "https://www.yourdomain.com"
]
```

---

## 🌍 Cloud Deployment

### AWS (ECS/Fargate)
1. Push images to ECR
2. Create ECS task definition using `docker-compose.yml` as reference
3. Deploy to Fargate

### Google Cloud (Cloud Run)
1. Push images to GCR
2. Deploy each service to Cloud Run
3. Configure internal networking

### Azure (Container Instances)
1. Push images to ACR
2. Create container group from docker-compose
3. Configure networking

### DigitalOcean (App Platform)
1. Connect GitHub repository
2. App Platform auto-detects Dockerfile
3. Configure environment variables

---

## 📚 Additional Resources

- **Docker Documentation**: https://docs.docker.com
- **Docker Compose Documentation**: https://docs.docker.com/compose
- **FastAPI Documentation**: https://fastapi.tiangolo.com
- **React Documentation**: https://react.dev
- **Project Documentation**: See `cursor-memory-bank/` directory

---

## 🆘 Getting Help

If you encounter issues:

1. Check this deployment guide
2. Review logs: `docker-compose logs`
3. Check `cursor-memory-bank/BUILD_SUMMARY.md`
4. Review `README.md`
5. Open an issue on GitHub

---

## ✅ Deployment Checklist

Before going to production:

- [ ] Docker and Docker Compose installed
- [ ] Data files present in `backend/data/`
- [ ] Environment variables configured
- [ ] Custom ports configured (if needed)
- [ ] CORS origins updated for production domain
- [ ] SSL/HTTPS configured (for production)
- [ ] Firewall rules set
- [ ] Monitoring configured
- [ ] Backup strategy in place
- [ ] Health checks verified
- [ ] Performance tested
- [ ] Security reviewed

---

**Ready to deploy? Run the startup script and you're live in minutes!** 🚀
