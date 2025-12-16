# Insta Outreach Command Center - Documentation

## Overview
A centralized admin panel for tracking outreach performance and managing the Oracle database.

## Tech Stack
- Python
- Streamlit
- Pandas
- python-oracledb

## Features
- **Tab-based UI**: Organized into "Performance Dashboard", "Lead Management (CRM)", and "Message Log".
- **Dynamic Filtering**:
    - **Group by Operator/Actor**: All performance metrics can be pivoted to show data for the human team member or the Instagram account used.
    - **Filter by Date**: Filter the performance dashboard to show data for "All Time", "Today", "This Week", or "This Month".
- **KPIs & Visualizations**: View key metrics, leaderboards, activity heatmaps, and performance-over-time charts that react to the selected filters.
- **Lead Management**: An interactive CRM grid to edit the 'Status' and 'Notes' for each prospect.
- **On-Demand Sync**: A "Sync Data" button in the header reloads all data from the database.

## Usage
To start the dashboard, navigate to the project root and run:
```bash
streamlit run src/dashboard/app.py
```
All controls for grouping and date filtering are located at the top of the "Performance Dashboard" tab. The global "Sync Data" button is in the top-right of the header.

## Deployment Strategy
Can be hosted on Streamlit Cloud (share repo, exclude sensitive env vars).

## Future Enhancements
- **Granular Filtering**: Future updates will allow for filtering all metrics by **Operator** (to analyze human performance) versus **Actor** (to analyze account performance).
