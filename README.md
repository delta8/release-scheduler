# Clinical Analytics Workload Assessment

A Dash-based web application for managing and visualizing clinical workload scheduling.

## Features

- ✅ Multi-select goal filtering
- ✅ Hierarchical Gantt chart visualization with expand/collapse
- ✅ Next Openings calculation (top 3 eligible people)
- ✅ CSV upload support (AHA scheduler + Zendesk tickets)
- ✅ Interactive hover details
- ✅ Color-coded by goal

## Quick Start

### Local Development
```bash
pip install -r requirements.txt
python release_scheduler_v2.py
```

Visit: `http://127.0.0.1:8052`

### Deployment

This app is ready for deployment on Render, Heroku, or similar platforms.

#### Deploy to Render
1. Push code to GitHub
2. Go to [Render.com](https://render.com)
3. Create new Web Service
4. Connect GitHub repo
5. Set build command: `pip install -r requirements.txt`
6. Set start command: `gunicorn release_scheduler_v2:server`
7. Deploy!

## File Structure

- `release_scheduler_v2.py` - Main application
- `requirements.txt` - Python dependencies
- `Procfile` - Deployment configuration
- `.gitignore` - Git ignore rules

## Technology Stack

- **Framework**: Dash (Python web framework)
- **Visualization**: Plotly
- **Data Processing**: Pandas
- **Server**: Gunicorn (production)

## Usage

1. Upload AHA Scheduler CSV
2. Upload Zendesk Tickets CSV
3. Select goals to filter (multi-select)
4. View Gantt chart with Next Openings highlighted

## Environment Variables

None required for basic deployment.

## Support

For issues or questions, check the logs on your hosting platform.
