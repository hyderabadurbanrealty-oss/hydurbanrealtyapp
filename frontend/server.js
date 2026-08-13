/**
 * Production Express Server for Hyderabad Urban Realty
 * 
 * This server does two things:
 *   1) Serves Angular build output (dist/)
 *   2) Proxies API calls to the backend service specified via env vars
 */

const express = require('express');
const path = require('path');
const compression = require('compression');
const helmet = require('helmet');
const { createProxyMiddleware } = require('http-proxy-middleware');

const app = express();
const PORT = process.env.PORT || 4200;

// Backend endpoints (set via Railway variables or env vars)
const BACKEND_URL = process.env.BACKEND_URL || process.env.API_URL || 'http://localhost:5001';
const PYTHON_URL = process.env.PYTHON_URL || 'http://localhost:5000';

// Security middleware - Helmet adds various HTTP headers for security
app.use(helmet({
  contentSecurityPolicy: {
    directives: {
      defaultSrc: ["'self'"],
      styleSrc: ["'self'", "'unsafe-inline'", "https://fonts.googleapis.com"],
      fontSrc: ["'self'", "https://fonts.gstatic.com"],
      scriptSrc: ["'self'", "'unsafe-inline'", "'unsafe-eval'"], // Angular requires unsafe-eval
      imgSrc: ["'self'", "data:", "https:"],
      connectSrc: ["'self'", BACKEND_URL, PYTHON_URL]
    }
  },
  crossOriginEmbedderPolicy: false
}));

// Compression middleware - reduces response size
app.use(compression());

// Serve static files from the Angular build folder
const distFolder = path.join(__dirname, 'dist', 'hyderabad-urban-realty');
app.use(express.static(distFolder, {
  maxAge: '1y', // Cache static assets for 1 year
  etag: true,
  lastModified: true,
  setHeaders: (res, filePath) => {
    // Don't cache index.html
    if (filePath.endsWith('index.html')) {
      res.setHeader('Cache-Control', 'no-cache, no-store, must-revalidate');
    }
  }
}));

// Health check endpoint
app.get('/health', (req, res) => {
  res.status(200).json({ 
    status: 'healthy', 
    timestamp: new Date().toISOString(),
    uptime: process.uptime()
  });
});

// Proxy API calls to the backend (same origin from the browser)
app.use('/api', createProxyMiddleware({
  target: BACKEND_URL,
  changeOrigin: true,
  pathRewrite: {
    '^/api': '/api',
  },
  onError: (err, req, res) => {
    console.error('API proxy error:', err);
    res.status(502).json({ error: 'Backend service unreachable' });
  }
}));

// All other routes should serve the Angular app (for client-side routing)
app.get('*', (req, res) => {
  res.sendFile(path.join(distFolder, 'index.html'));
});

// Error handling middleware
app.use((err, req, res, next) => {
  console.error('Server Error:', err);
  res.status(500).json({ 
    error: 'Internal Server Error',
    message: process.env.NODE_ENV === 'development' ? err.message : 'Something went wrong'
  });
});

// Start the server
app.listen(PORT, () => {
  console.log('');
  console.log('='.repeat(60));
  console.log('🚀 Hyderabad Urban Realty - Production Server');
  console.log('='.repeat(60));
  console.log('');
  console.log(`✅ Server running on: http://localhost:${PORT}`);
  console.log(`📁 Serving from: ${distFolder}`);
  console.log(`🌍 Environment: ${process.env.NODE_ENV || 'production'}`);
  console.log(`⏰ Started at: ${new Date().toLocaleString()}`);
  console.log('');
  console.log('='.repeat(60));
  console.log('');
});

// Graceful shutdown
process.on('SIGTERM', () => {
  console.log('SIGTERM signal received: closing HTTP server');
  process.exit(0);
});

process.on('SIGINT', () => {
  console.log('\nSIGINT signal received: closing HTTP server');
  process.exit(0);
});
