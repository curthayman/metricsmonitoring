# metricsmonitoring.py

**metricsmonitoring.py** is a Python script for monitoring Pantheon site metrics, detecting traffic anomalies, and alerting on low cache efficiency. It sends detailed, actionable Slack notifications to help you quickly identify and address performance issues.

## 📰 Features

- Monitors multiple Pantheon sites for traffic spikes and cache efficiency
- Sends rich Slack alerts with historical trends, performance impact, and improvement tips
- Integrates with Pantheon’s Terminus CLI
- Easy configuration via YAML and environment variables

## 🛠️ Requirements

- Python 3.7+
- [Terminus CLI](https://pantheon.io/docs/terminus)
- Slack webhook URL

**Python dependencies** (install with `pip install -r requirements.txt`):

- pandas
- requests
- pyyaml
- python-dotenv

## ⌨️ Setup

1. **Clone the repository**
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt

## Configure environment variables
Create a **.env** file with your Slack webhook URL:

**SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...**

## Configure monitored sites
- Edit **sites.yaml** to list your Pantheon site names and thresholds.

Should look like this when you setup your sites.yaml file:
```bash
threshold_percent: 25
sites_to_monitor:
  - site1
  - site2
  - site3
```
Ensure Terminus is installed and accessible, if not run this command:
```bash
terminus auth:login
```

If not in your PATH, set the TERMINUS_COMMAND environment variable to the full path. But this script will look for this on initial script run
## 👨🏽‍💻Usage
Run the script to check weekly metrics:

```bash
python metricsmonitoring.py
```

Or for daily metrics:
```bash
python metricsmonitoring.py --day
```

## 🚨 Alerts
Slack alerts include:

- Site name and environment
- Traffic anomaly detection
- Cache efficiency with historical trends and actionable advice
- Direct link to the Pantheon dashboard
