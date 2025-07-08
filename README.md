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
- [Slack webhook URL](https://api.slack.com/messaging/webhooks)

**Python dependencies** (install with `pip install -r requirements.txt`):

- pandas
- requests
- pyyaml
- python-dotenv
- matplotlib
- pillow

## ⌨️ Setup

1. **Clone the repository**
2. **Install dependencies**
   ```bash
   pip install -r requirements.txt

## Configure environment variables
Create a **.env** file with your Slack webhook URL. There is an example file for this as well, called (_.env.example_):

**SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...**

## Configure monitored sites
- Edit **sites.yaml** to list your Pantheon site names and thresholds.

Should look like this when you setup your sites.yaml file, I have also inlucded an example file as well. (_example.sites.yaml_):
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
## 📝 Notes
When you run this script, it will create a metricsmonitoring.log file that you can use for debugging or just info when it runs.
- When running under cron, the TERMINUS_COMMAND entry might be required. Here is an example below:
```bash
TERMINUS_COMMAND=/usr/local/bin/terminus
```
You may need to adjust that to your path if you running crons

Included in this repo is a **.env.example** file and a **example.sites.yaml** file. Just rename the **.env.example** file to **.env** and the **example.sites.yaml** file to **sites.yaml** and put your own Webhook and sites in.

Make sure you are running a virtual enviroment to run commands like (`pip install -r requirements.txt`). You can run this command if you are on any Linux based platform:

```bash
python3 -m venv venv && source venv/bin/activate'
```

## 🚨 Alerts
Slack alerts include:

- Site name and environment
- Traffic anomaly detection
- Cache efficiency with historical trends and actionable advice
- Direct link to the Pantheon dashboard

## 🏆 Credits
- Curt Hayman
- Terminus
- pandas
- requests
- pyyaml
- python-dotenv
