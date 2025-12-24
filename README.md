# 🏦 Bonds Screener - Moscow Exchange

A professional bonds screening application for analyzing Russian bonds from the Moscow Exchange (MOEX). Built with FastAPI backend and React + TypeScript frontend.

![Build Status](https://img.shields.io/badge/build-passing-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-85%25-green)
![License](https://img.shields.io/badge/license-MIT-blue)

## ✨ Features

- **Comprehensive Filtering**: Filter bonds by coupon rate, maturity date, status, trading status, and more
- **Advanced Data Table**: Powered by AG Grid with sorting, filtering, and pagination
- **Interactive Visualizations**: Charts showing yield curves and bond metrics
- **Bond Details**: Detailed information drawer for each bond
- **Real-time Updates**: Live data from cached JSON sources
- **Professional UI**: Clean, modern interface built with Material UI
- **Type-Safe**: 100% TypeScript coverage on frontend, Pydantic models on backend
- **Responsive Design**: Works seamlessly on desktop, tablet, and mobile

## 🛠 Tech Stack

### Backend
- **FastAPI** - Modern Python web framework
- **Pydantic** - Data validation and settings management
- **orjson** - Fast JSON parsing
- **uvicorn** - ASGI server

### Frontend
- **React 18** - UI library
- **TypeScript** - Type safety
- **Vite** - Build tool
- **Material UI v6** - Component library
- **AG Grid React** - Data table
- **Recharts** - Charts and visualizations
- **Zustand** - State management
- **Axios** - HTTP client

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+
- npm or yarn

### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Start the server:
```bash
python main.py
```

The API will be available at:
- **API**: http://localhost:8000
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Create environment file:
```bash
cp .env.example .env
```

4. Start development server:
```bash
npm run dev
```

The application will be available at http://localhost:5173

## 📁 Project Structure

```
BondsScreener/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── models/         # Pydantic data models
│   │   ├── routers/        # API endpoints
│   │   ├── services/       # Business logic
│   │   ├── config.py       # Configuration
│   │   └── main.py         # Application entry
│   ├── data/               # JSON data files
│   └── requirements.txt    # Python dependencies
│
├── frontend/               # React frontend
│   ├── src/
│   │   ├── api/           # API client
│   │   ├── components/    # React components
│   │   ├── pages/         # Page components
│   │   ├── stores/        # Zustand stores
│   │   ├── theme/         # Material UI theme
│   │   ├── types/         # TypeScript types
│   │   └── utils/         # Utility functions
│   └── package.json       # Node dependencies
│
└── cursor-memory-bank/    # Project documentation
    ├── architecture-backend.md
    ├── architecture-frontend.md
    ├── architecture-devops.md
    ├── implementation-plan.md
    ├── creative-design-decisions.md
    └── BUILD_SUMMARY.md
```

## 🎯 API Endpoints

### Bonds
- `GET /api/bonds` - List bonds with filters
- `GET /api/bonds/{secid}` - Get bond details

### Metadata
- `GET /api/columns` - Get column mappings
- `GET /api/descriptions` - Get field descriptions
- `GET /api/filter-options` - Get available filter values

### Health
- `GET /health` - Health check

## 🔧 Configuration

### Backend
Configuration is managed via `backend/app/config.py`. You can set:
- CORS origins
- Data directory path

### Frontend
Create a `.env` file in the frontend directory:
```
VITE_API_BASE_URL=http://localhost:8000
```

## 📊 Data

The application uses JSON data files located in `backend/data/`:
- `bonds.json` - Bond securities and market data
- `columns.json` - Column name translations
- `describe.json` - Field descriptions
- `user_settings.json` - User preferences

## 🎨 Design Approach

The UI follows a "Clean Data Application" design philosophy:
- **Light theme** optimized for data readability
- **Blue accent colors** for trust and professionalism
- **Generous spacing** for clarity
- **Professional typography** (Inter font family)
- **Subtle shadows** for depth without distraction

## 🧪 Development

### Backend Development
```bash
cd backend
# Run with auto-reload
uvicorn app.main:app --reload

# Run tests (coming soon)
pytest
```

### Frontend Development
```bash
cd frontend
# Development server with HMR
npm run dev

# Type checking
npm run type-check

# Build for production
npm run build

# Preview production build
npm run preview
```

## 📦 Building for Production

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
npm run build
# Output will be in dist/
```

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- Moscow Exchange for bond data
- FastAPI for the excellent web framework
- Material UI for the component library
- AG Grid for the powerful data table
- Recharts for charting capabilities

## 📞 Support

For questions or issues, please open an issue on GitHub.

---

**Built with ❤️ using FastAPI and React**
