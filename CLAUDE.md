# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an exam monitoring/proctoring system (考试监控系统) designed for educational institutions. The system consists of:
- **Client**: Monitors student activities during exams, controls Chrome browser, captures screenshots/videos
- **Server**: Receives and displays student status, violation records, and provides web interface for supervisors

## Common Development Commands

### Server Operations
```bash
# Start monitoring server
python server.py

# Start production server with Gunicorn
python start_production_server.py
```

### Client Operations
```bash
# Start exam client
python main.py

# Package client as executable
python package_app.py
```

### Database Operations
```bash
# The system uses MySQL database with connection pooling
# Database schema is defined in database_schema.sql
# Data access is handled through data_access.py with connection pooling
```

## System Architecture

### Client-Side Components
- `main.py`: Main client entry point with login window and monitoring orchestration
- `app_monitor.py`: Monitors foreground applications for unauthorized software
- `chrome_controller.py`: Controls Chrome browser with restricted access
- `screen_recorder.py`: Captures screenshots and screen recordings on violations
- `api_client.py`: Handles communication with monitoring server
- `config_manager.py`: Manages client configuration from config.json

### Server-Side Components
- `server.py`: Flask web server providing API endpoints and web interface
- `data_access.py`: MySQL database operations with connection pooling
- `redis_helper.py`: Redis operations for real-time data and caching
- `merge_manager.py`: Handles merging of screen recordings
- `background_tasks.py`: Asynchronous task processing

### Key Configuration Files
- `config.json`: Main configuration including allowed apps, URLs, server settings
- `requirements.txt`: Python dependencies for both client and server
- `database_schema.sql`: MySQL database structure
- `templates/`: HTML templates for web interface

## Database Architecture

The system uses a hybrid storage approach:
- **Redis**: Real-time data (student status, heartbeats, session management)
- **MySQL**: Persistent data (exam records, student info, violation logs)
- Connection pooling is implemented to handle concurrent access

## Development Guidelines

### Client Development
- The system only monitors foreground applications (`only_monitor_foreground: true`)
- Screenshot capture occurs on violations if enabled in config
- Chrome browser is launched with restricted settings and plugins disabled
- All client activities are logged to `logs/` directory

### Server Development
- Flask application serves both API endpoints and web interface
- Real-time data is cached in Redis for performance
- Historical data is stored in MySQL for reporting and analysis
- Screen recordings are stored in `server_data/recordings/`

### Testing and Deployment
- Test server locally: `python server.py` (runs on http://127.0.0.1:5000)
- Production deployment uses Gunicorn with gevent workers
- Client can be packaged as standalone executable using PyInstaller

## Important Notes

- This is monitoring software designed for educational supervision
- The system is primarily in Chinese language
- Default server IP is configured as '10.188.2.252' in main.py:39
- Chrome driver management is handled automatically through chrome_driver_manager.py
- The system supports up to 400 concurrent client connections based on database_architecture.md