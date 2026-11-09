# Project Mandates & Conventions

## 1. Company Domain & Email References
- Always reference `blueshoe.io` (e.g., `https://www.blueshoe.io`, `hurricane@blueshoe.io`, `hello@blueshoe.io`) instead of `blueshoe.de`.

## 2. Product Messaging & Positioning
- **Core Value Pillars:** Always anchor marketing, documentation, and release materials on the three core enterprise pillars:
  1. **Rust-Powered HTTP Performance:** Granian core (Hyper/Tokio) for high-throughput, low-latency zero-copy networking outperforming Gunicorn and Tornado.
  2. **Built-in Edge Defense:** Fast-404 dropping automated scanner probes in <0.35µs and token-bucket rate limiting before requests reach Python or database pools.
  3. **Production Health Observability & Traffic Shedding:** Kubernetes/Docker `/startup`, `/alive`, `/ready`, and `/metrics` tied directly to Django application state and backlog depth.
- **Static & Media File Serving:** Never over-emphasize static/media file serving as a primary selling point. Treat it as a convenient bonus ("cherry on the cake") for development, staging, Docker Compose, or small setups where S3/CDN is operational overkill.
